"""ProAgent minimal agent - Standalone LLM loop with function calling.

For Phase 1 we use our own minimal agent loop instead of Hermes's full
AIAgent. This keeps ProAgent independent of Hermes's entry-point code
(run_agent.py, cli.py) and its wide transitive dependencies.

Supports:
- OpenAI chat completions API (function calling)
- Anthropic messages API (tool use)
- Streaming-free (simple)
- Multi-turn with tool execution
"""

import json
import logging
import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

logger = logging.getLogger(__name__)


@dataclass
class Message:
    role: str                     # system | user | assistant | tool
    content: str = ""
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)
    tool_call_id: str = ""        # For tool-role messages
    name: str = ""                # Tool name (for tool messages)


@dataclass
class ToolDef:
    name: str
    description: str
    parameters: Dict[str, Any]
    handler: Callable[..., str]


class ProAgent:
    """Minimal Agent loop with function calling.

    Usage:
        agent = ProAgent(provider="openai", model="gpt-4.1-mini",
                        system_prompt="...",
                        tools=[...])
        response = agent.chat("检查 CPU 负载")
    """

    MAX_ITERATIONS = 15   # Max tool-calling rounds per user turn

    def __init__(
        self,
        provider: str = "openai",
        model: str = "gpt-4.1-mini",
        system_prompt: str = "",
        tools: Optional[List[ToolDef]] = None,
        api_key: str = "",
        base_url: str = "",
        max_tokens: int = 4096,
    ):
        from proagent.core.providers import resolve_provider

        # Resolve provider to canonical form + default base URL
        profile = resolve_provider(provider)
        if profile:
            self.provider = profile.id
            self.api_mode = profile.api_mode  # "openai" | "anthropic"
            # Use profile base_url if caller didn't specify one
            if not base_url and profile.base_url:
                base_url = profile.base_url
        else:
            self.provider = provider.lower()
            # Fallback: infer api_mode from provider name
            self.api_mode = "anthropic" if "anthropic" in self.provider or "claude" in self.provider else "openai"

        self.model = model
        self.system_prompt = system_prompt
        self.tools = tools or []
        self.max_tokens = max_tokens
        self.messages: List[Message] = []

        # Store API credentials
        self.api_key = api_key or self._resolve_api_key(profile)
        self.base_url = base_url

        # Validate
        if not self.api_key:
            env_var = profile.env_vars[0] if profile and profile.env_vars else "API_KEY"
            raise RuntimeError(
                f"No API key found for provider '{self.provider}'. "
                f"Set {env_var} environment variable."
            )

        self._tool_map = {t.name: t for t in self.tools}

    def _resolve_api_key(self, profile=None) -> str:
        if profile and profile.env_vars:
            for env_var in profile.env_vars:
                val = os.environ.get(env_var, "")
                if val:
                    return val
        # Legacy fallback
        if self.provider == "openai":
            return os.environ.get("OPENAI_API_KEY", "")
        elif self.provider == "anthropic":
            return os.environ.get("ANTHROPIC_API_KEY", "")
        elif self.provider == "minimax-cn":
            return os.environ.get("MINIMAX_CN_API_KEY", "")
        return ""

    def reset(self) -> None:
        """Reset conversation history."""
        self.messages = []

    def chat(self, user_input: str) -> str:
        """Process a user message with tool calling.

        Args:
            user_input: The user's message

        Returns:
            Final assistant response text (after all tool calls resolved)
        """
        # Add user message
        self.messages.append(Message(role="user", content=user_input))

        # Iterate up to MAX_ITERATIONS rounds of tool calls
        for iteration in range(self.MAX_ITERATIONS):
            if self.api_mode == "openai":
                response = self._call_openai()
            elif self.api_mode == "anthropic":
                response = self._call_anthropic()
            else:
                return f"❌ Unsupported api_mode: {self.api_mode}"

            if response.tool_calls:
                # Execute tools, add results to history, loop
                self.messages.append(response)
                for tc in response.tool_calls:
                    result = self._execute_tool(tc)
                    self.messages.append(Message(
                        role="tool",
                        content=result,
                        tool_call_id=tc.get("id", ""),
                        name=tc.get("name", ""),
                    ))
                continue
            else:
                # Final response
                self.messages.append(response)
                return response.content

        return "⚠️ Max tool-calling iterations reached without final answer."

    def _execute_tool(self, tc: Dict[str, Any]) -> str:
        """Execute a single tool call, return result as string."""
        name = tc.get("name", "")
        args_raw = tc.get("arguments", {})

        if isinstance(args_raw, str):
            try:
                args = json.loads(args_raw)
            except json.JSONDecodeError:
                args = {}
        else:
            args = args_raw

        tool = self._tool_map.get(name)
        if not tool:
            return f"❌ Unknown tool: {name}"

        try:
            logger.info("Tool call: %s(%s)", name, json.dumps(args)[:200])
            result = tool.handler(**args)
            # Cap result size
            if len(result) > 20000:
                result = result[:20000] + "\n... [truncated]"
            return result
        except Exception as e:
            logger.exception("Tool %s failed", name)
            return f"❌ Tool error: {e}"

    # ========================================================================
    # OpenAI
    # ========================================================================

    def _call_openai(self) -> Message:
        try:
            from openai import OpenAI
        except ImportError:
            raise RuntimeError("openai package not installed. Run: pip install openai")

        client_kwargs = {"api_key": self.api_key}
        if self.base_url:
            client_kwargs["base_url"] = self.base_url

        client = OpenAI(**client_kwargs)

        # Build messages in OpenAI format
        openai_messages = []
        if self.system_prompt:
            openai_messages.append({"role": "system", "content": self.system_prompt})

        for msg in self.messages:
            if msg.role == "user":
                openai_messages.append({"role": "user", "content": msg.content})
            elif msg.role == "assistant":
                m = {"role": "assistant", "content": msg.content or None}
                if msg.tool_calls:
                    m["tool_calls"] = [
                        {
                            "id": tc.get("id", ""),
                            "type": "function",
                            "function": {
                                "name": tc.get("name", ""),
                                "arguments": json.dumps(tc.get("arguments", {}))
                                if isinstance(tc.get("arguments"), dict)
                                else tc.get("arguments", "{}"),
                            },
                        }
                        for tc in msg.tool_calls
                    ]
                openai_messages.append(m)
            elif msg.role == "tool":
                openai_messages.append({
                    "role": "tool",
                    "tool_call_id": msg.tool_call_id,
                    "content": msg.content,
                })

        # Build tools schema
        openai_tools = None
        if self.tools:
            openai_tools = [
                {
                    "type": "function",
                    "function": {
                        "name": t.name,
                        "description": t.description,
                        "parameters": t.parameters,
                    },
                }
                for t in self.tools
            ]

        resp = client.chat.completions.create(
            model=self.model,
            messages=openai_messages,
            tools=openai_tools,
            max_tokens=self.max_tokens,
        )

        choice = resp.choices[0]
        msg = choice.message

        tool_calls = []
        if msg.tool_calls:
            for tc in msg.tool_calls:
                try:
                    args = json.loads(tc.function.arguments)
                except (json.JSONDecodeError, AttributeError):
                    args = {}
                tool_calls.append({
                    "id": tc.id,
                    "name": tc.function.name,
                    "arguments": args,
                })

        return Message(
            role="assistant",
            content=msg.content or "",
            tool_calls=tool_calls,
        )

    # ========================================================================
    # Anthropic
    # ========================================================================

    def _call_anthropic(self) -> Message:
        try:
            from anthropic import Anthropic
        except ImportError:
            raise RuntimeError("anthropic package not installed. Run: pip install anthropic")

        client_kwargs = {"api_key": self.api_key}
        if self.base_url:
            client_kwargs["base_url"] = self.base_url

        client = Anthropic(**client_kwargs)

        # Build messages in Anthropic format
        anth_messages = []
        for msg in self.messages:
            if msg.role == "user":
                anth_messages.append({"role": "user", "content": msg.content})
            elif msg.role == "assistant":
                content_blocks = []
                if msg.content:
                    content_blocks.append({"type": "text", "text": msg.content})
                for tc in msg.tool_calls:
                    content_blocks.append({
                        "type": "tool_use",
                        "id": tc.get("id", ""),
                        "name": tc.get("name", ""),
                        "input": tc.get("arguments", {}),
                    })
                anth_messages.append({"role": "assistant", "content": content_blocks})
            elif msg.role == "tool":
                anth_messages.append({
                    "role": "user",
                    "content": [{
                        "type": "tool_result",
                        "tool_use_id": msg.tool_call_id,
                        "content": msg.content,
                    }],
                })

        anth_tools = None
        if self.tools:
            anth_tools = [
                {
                    "name": t.name,
                    "description": t.description,
                    "input_schema": t.parameters,
                }
                for t in self.tools
            ]

        resp = client.messages.create(
            model=self.model,
            system=self.system_prompt,
            messages=anth_messages,
            tools=anth_tools,
            max_tokens=self.max_tokens,
        )

        content_text = ""
        tool_calls = []
        for block in resp.content:
            if block.type == "text":
                content_text += block.text
            elif block.type == "tool_use":
                tool_calls.append({
                    "id": block.id,
                    "name": block.name,
                    "arguments": block.input,
                })

        return Message(
            role="assistant",
            content=content_text,
            tool_calls=tool_calls,
        )


def build_server_shell_tool(runtime) -> ToolDef:
    """Build the server_shell ToolDef bound to a ProAgent runtime."""
    def handler(command: str, target: str = "", **_kwargs) -> str:
        rc, output = runtime.execute_on_target(
            command=command,
            target_id=target if target else None,
            timeout=30,
            session_id="interactive",
            actor="agent",
        )
        if rc == -1 and (output.startswith("⛔") or "denied" in output.lower()):
            return output
        if rc != 0:
            return f"[exit code: {rc}]\n{output}"
        return output or "[empty output]"

    return ToolDef(
        name="server_shell",
        description=(
            "Execute a read-only shell command on a target server for health inspection. "
            "Only diagnostic/monitoring commands are allowed. "
            "Write operations (rm, kill, systemctl restart, etc.) are blocked by policy. "
            "Use this to check CPU, memory, disk, network, processes, services, and logs."
        ),
        parameters={
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": (
                        "Shell command to execute. Must be read-only. "
                        "Examples: 'free -m', 'df -hT', "
                        "'ps aux --sort=-%cpu | head -20', 'systemctl --failed'"
                    ),
                },
                "target": {
                    "type": "string",
                    "description": "Target server ID. Leave empty for default.",
                    "default": "",
                },
            },
            "required": ["command"],
        },
        handler=handler,
    )
