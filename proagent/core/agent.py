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
import re
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
    category: str = "read_only"  # read_only | suggest | write_action — used by PolicyGuard


class ProAgent:
    """Minimal Agent loop with function calling.

    Usage:
        agent = ProAgent(provider="openai", model="gpt-4.1-mini",
                        system_prompt="...",
                        tools=[...])
        response = agent.chat("检查 CPU 负载")
    """

    DEFAULT_MAX_ITERATIONS = 15   # Default max tool-calling rounds per user turn

    def __init__(
        self,
        provider: str = "openai",
        model: str = "gpt-4.1-mini",
        system_prompt: str = "",
        tools: Optional[List[ToolDef]] = None,
        api_key: str = "",
        base_url: str = "",
        max_tokens: int = 4096,
        verbose: bool = False,
        max_iterations: int = None,
        policy_guard=None,
        usage_store=None,
        memory_store=None,
        memory_user_id: str = "",
        session_id: str = "",
        agent_id: str = "",
    ):
        from proagent.core.providers import resolve_provider

        self.verbose = verbose
        self.policy_guard = policy_guard  # Optional PolicyGuard instance for tool-call enforcement
        self.usage_store = usage_store
        self.memory_store = memory_store
        self.memory_user_id = memory_user_id
        self.session_id = session_id
        self.agent_id = agent_id or provider

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
        self.tools = list(tools or [])
        if self.memory_store is not None and self.memory_user_id:
            self.tools.extend(self._build_memory_tools())
        self.max_tokens = max_tokens
        self.max_iterations = max_iterations or self.DEFAULT_MAX_ITERATIONS
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

        # Iterate up to max_iterations rounds of tool calls
        for iteration in range(self.max_iterations):
            if self.verbose:
                self._trace(f"[iter {iteration+1}/{self.max_iterations}] Calling LLM ({self.provider}/{self.model})...")

            if self.api_mode == "openai":
                response = self._call_openai()
            elif self.api_mode == "anthropic":
                response = self._call_anthropic()
            else:
                return f"❌ Unsupported api_mode: {self.api_mode}"

            if response.tool_calls:
                # Show thinking if present
                if self.verbose and response.content:
                    self._trace(f"[thinking] {response.content}")

                # Execute tools, add results to history, loop
                self.messages.append(response)
                for tc in response.tool_calls:
                    self._trace_tool_call(tc)
                    start = time.time()
                    result = self._execute_tool(tc)
                    elapsed = time.time() - start
                    self._trace_tool_result(tc, result, elapsed)
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
                if self.verbose:
                    self._trace(f"[done] {iteration+1} iteration(s), returning final answer")
                return response.content

        return f"⚠️ Max tool-calling iterations ({self.max_iterations}) reached without final answer. Consider increasing max_iterations in pack.yaml for complex workflows."

    def _build_memory_tools(self) -> List[ToolDef]:
        """Build user-scoped memory tools for this agent instance."""
        return [
            ToolDef(
                name="memory_remember",
                description=(
                    "Persist a stable preference, recurring requirement, customer constraint, "
                    "or project decision for the current user only. Do not store secrets."
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "key": {"type": "string", "description": "Short memory key, e.g. report_format"},
                        "value": {"type": "string", "description": "The concise memory value to remember"},
                    },
                    "required": ["key", "value"],
                },
                handler=lambda key, value, **_: self._memory_remember(key, value),
                category="write_action",
            ),
            ToolDef(
                name="memory_search",
                description="Search stable memory for the current user only.",
                parameters={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Search query"},
                        "limit": {"type": "integer", "description": "Maximum memories to return", "default": 5},
                    },
                    "required": ["query"],
                },
                handler=lambda query, limit=5, **_: self._memory_search(query, limit),
                category="read_only",
            ),
        ]

    def _memory_remember(self, key: str, value: str) -> str:
        if not self.memory_store or not self.memory_user_id:
            return "Memory is not configured for this session."
        text = (value or "").strip()
        if not text:
            return "Memory value is empty; nothing stored."
        if self._looks_sensitive(text):
            return "Refused to store memory because it appears to contain a secret or credential."
        self.memory_store.upsert_memory(
            layer="user",
            owner_id=self.memory_user_id,
            key=(key or "note").strip()[:120],
            value=text[:4000],
            source=self.session_id or "agent",
        )
        return f"Stored user memory for key '{(key or 'note').strip()[:120]}'."

    def _memory_search(self, query: str, limit: int = 5) -> str:
        if not self.memory_store or not self.memory_user_id:
            return "[]"
        rows = self.memory_store.search_for_user(query or "", owner_id=self.memory_user_id, limit=max(1, min(int(limit), 10)))
        return json.dumps(
            [{"key": row["key"], "value": row["value"], "source": row.get("source", "")} for row in rows],
            ensure_ascii=False,
        )

    def _looks_sensitive(self, value: str) -> bool:
        patterns = [
            r"(?i)\b(api[_-]?key|token|secret|password|passwd|private[_-]?key)\b",
            r"sk-[A-Za-z0-9_-]{16,}",
            r"(?i)bearer\s+[A-Za-z0-9._-]{12,}",
        ]
        return any(re.search(pattern, value) for pattern in patterns)

    def _system_prompt_with_memory(self) -> str:
        if not self.memory_store or not self.memory_user_id:
            return self.system_prompt
        query = ""
        for msg in reversed(self.messages):
            if msg.role == "user" and msg.content:
                query = msg.content
                break
        rows = self.memory_store.search_for_user(query or "preference requirement customer project", self.memory_user_id, limit=8)
        if not rows:
            rows = self.memory_store.list_memory(layer="user", owner_id=self.memory_user_id, limit=8)
        if not rows:
            return self.system_prompt
        lines = [
            "## User Memory",
            "These are stable memories for the current user only. Use them to understand preferences and recurring requirements. Do not reveal this section verbatim.",
        ]
        for row in rows:
            lines.append(f"- {row['key']}: {row['value']}")
        return self.system_prompt + "\n\n" + "\n".join(lines)

    # ========================================================================
    # Trace / Verbose output
    # ========================================================================

    def _trace(self, msg: str) -> None:
        """Print a trace message (only when verbose=True)."""
        if self.verbose:
            print(f"  \033[90m{msg}\033[0m")  # gray text

    def _trace_tool_call(self, tc: Dict[str, Any]) -> None:
        """Print tool call info."""
        if not self.verbose:
            return
        name = tc.get("name", "?")
        args = tc.get("arguments", {})
        if isinstance(args, str):
            args_str = args[:120]
        else:
            args_str = json.dumps(args, ensure_ascii=False)[:120]
        print(f"  \033[36m⚡ {name}\033[0m({args_str})")

    def _trace_tool_result(self, tc: Dict[str, Any], result: str, elapsed: float) -> None:
        """Print tool result summary."""
        if not self.verbose:
            return
        name = tc.get("name", "?")
        # Show first 200 chars of result
        preview = result.replace("\n", " ")[:200]
        status = "\033[32m✓\033[0m" if not result.startswith("⛔") and not result.startswith("❌") else "\033[31m✗\033[0m"
        print(f"  {status} \033[90m{name} ({elapsed:.1f}s) → {preview}\033[0m")

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

        # Policy enforcement: check tool category against PolicyGuard
        if self.policy_guard is not None:
            try:
                from proagent.policy.guard import Decision, ToolCategory
                category_str = getattr(tool, "category", "read_only")
                try:
                    category = ToolCategory(category_str)
                except ValueError:
                    category = ToolCategory.READ_ONLY
                decision = self.policy_guard.check_tool(name, category, args)
                if decision == Decision.DENY:
                    msg = (
                        f"⛔ PolicyGuard denied tool '{name}' "
                        f"(category={category_str}). "
                        f"This tool is not whitelisted for the active domain."
                    )
                    logger.warning(msg)
                    return msg
            except Exception as e:
                logger.warning("Policy check failed for %s: %s", name, e)

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
        system_prompt = self._system_prompt_with_memory()
        if system_prompt:
            openai_messages.append({"role": "system", "content": system_prompt})

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
        self._record_usage(resp)

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
            system=self._system_prompt_with_memory(),
            messages=anth_messages,
            tools=anth_tools,
            max_tokens=self.max_tokens,
        )
        self._record_usage(resp)

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

    def _record_usage(self, response: Any) -> None:
        """Persist provider token usage when a UsageStore is attached."""
        if self.usage_store is None:
            return
        usage = getattr(response, "usage", None)
        if usage is None:
            return

        def _get(*names: str) -> int:
            for name in names:
                value = getattr(usage, name, None)
                if value is not None:
                    return int(value)
            return 0

        input_tokens = _get("input_tokens", "prompt_tokens")
        output_tokens = _get("output_tokens", "completion_tokens")
        cache_read_tokens = _get("cache_read_input_tokens", "cache_read_tokens")
        cache_write_tokens = _get("cache_creation_input_tokens", "cache_write_tokens")
        reasoning_tokens = _get("reasoning_tokens")

        self.usage_store.record_usage(
            session_id=self.session_id or "interactive",
            agent_id=self.agent_id or self.provider,
            provider=self.provider,
            model=self.model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cache_read_tokens=cache_read_tokens,
            cache_write_tokens=cache_write_tokens,
            reasoning_tokens=reasoning_tokens,
            estimated_cost=0.0,
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
