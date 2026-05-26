"""ProAgent Runtime - Core orchestrator that bridges Hermes AIAgent with domain packs.

This is the main entry point for ProAgent. It:
1. Loads configuration (proagent.yaml)
2. Loads the active Domain Pack (knowledge, skills, tools, policy)
3. Establishes SSH connections to target hosts
4. Registers ProAgent-specific tools with Hermes tool registry
5. Configures and runs the Hermes AIAgent with domain-specific system prompt
6. Manages the audit trail
"""

import hashlib
import json
import logging
import os
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

# Ensure parent paths are importable
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from proagent.core.config import ProAgentConfig, load_config, find_config_file
from proagent.core.ssh_pool import SSHPool, TargetHost
from proagent.policy.guard import PolicyGuard, PolicyConfig, Decision, ToolCategory, load_policy
from proagent.policy.audit import AuditStore

logger = logging.getLogger(__name__)


class ProAgentRuntime:
    """Core runtime that orchestrates the ProAgent system.

    Lifecycle:
        1. __init__: Load config, policy, establish connections
        2. register_tools(): Register domain tools with Hermes registry
        3. build_system_prompt(): Assemble domain-specific system prompt
        4. run(): Start the agent loop (CLI or gateway mode)
    """

    def __init__(self, config: ProAgentConfig = None, config_path: Path = None):
        """Initialize the ProAgent runtime.

        Args:
            config: Pre-loaded config. If None, loads from config_path or default locations.
            config_path: Path to proagent.yaml. If None, searches default locations.
        """
        if config is None:
            config = load_config(config_path)
        self.config = config

        # Initialize audit store
        audit_path = Path(config.audit_db)
        if not audit_path.is_absolute():
            audit_path = Path.cwd() / audit_path
        self.audit = AuditStore(audit_path)

        # Load domain pack
        self.domain_dir = self._resolve_domain_dir()
        self.policy = self._load_policy()
        self.system_prompt = self._load_system_prompt()
        self.knowledge_index = self._load_knowledge_index()

        # Initialize SSH pool
        self.ssh_pool = SSHPool(config.targets if self.should_init_ssh() else [])

        # Tool registry for ProAgent-specific tools
        self._tools: Dict[str, Dict[str, Any]] = {}

        logger.info(
            "ProAgent Runtime initialized: domain=%s, targets=%d",
            config.domain,
            len(config.targets),
        )

    def should_init_ssh(self) -> bool:
        """Check if the current domain requires SSH connections."""
        pack = getattr(self, "_domain_pack", None)
        if pack:
            return pack.requires_ssh
        return True  # Default: assume SSH needed

    def get_tools(self) -> list:
        """Get tools from the active domain pack (no hardcoding)."""
        pack = getattr(self, "_domain_pack", None)
        if pack:
            return pack.get_tools(self)
        # Fallback for backward compat
        from proagent.core.agent import build_server_shell_tool
        return [build_server_shell_tool(self)]

    def _resolve_domain_dir(self) -> Path:
        """Find the domain pack directory."""
        from proagent.domain.base import load_pack
        pack = load_pack(self.config.domain)
        if pack:
            self._domain_pack = pack
            return pack.pack_dir

        # Fallback: check relative to project root
        candidates = [
            Path.cwd() / "proagent" / "domain" / self.config.domain.replace("-", "_"),
            Path(__file__).resolve().parents[1] / "domain" / self.config.domain.replace("-", "_"),
        ]
        for candidate in candidates:
            if candidate.exists():
                return candidate

        logger.warning("Domain pack directory not found for '%s'", self.config.domain)
        return candidates[0]

    def _load_policy(self) -> PolicyGuard:
        """Load policy configuration from domain pack."""
        policy_path = self.domain_dir / "policy.yaml"
        policy_config = load_policy(policy_path)
        return PolicyGuard(policy_config, domain=self.config.domain)

    def _load_system_prompt(self) -> str:
        """Load the domain system prompt."""
        prompt_path = self.domain_dir / "system_prompt.md"
        if prompt_path.exists():
            return prompt_path.read_text(encoding="utf-8")

        # Fallback default
        return f"""You are ProAgent, a professional server health inspection agent.
Your domain is: {self.config.domain}
You can ONLY execute read-only commands to inspect server health.
You MUST NEVER execute any command that modifies system state.
Always provide structured, evidence-based analysis."""

    def _load_knowledge_index(self) -> str:
        """Load the knowledge index for context injection."""
        index_path = self.domain_dir / "knowledge" / "index.md"
        if index_path.exists():
            return index_path.read_text(encoding="utf-8")
        return ""

    def connect_targets(self) -> Dict[str, bool]:
        """Connect to all configured target hosts.

        Returns dict of {target_id: success}.
        """
        results = self.ssh_pool.connect_all()
        for target_id, success in results.items():
            self.audit.record_event(
                session_id="system",
                actor="runtime",
                domain=self.config.domain,
                tool="ssh_connect",
                args={"target": target_id},
                decision="allow",
                reason="startup" if success else "connection_failed",
            )
        return results

    def execute_on_target(
        self,
        command: str,
        target_id: str = None,
        timeout: int = 30,
        session_id: str = "",
        actor: str = "agent",
    ) -> Tuple[int, str]:
        """Execute a command on a target host with policy enforcement.

        Args:
            command: Shell command to execute
            target_id: Target host ID (uses default if None)
            timeout: Command timeout in seconds
            session_id: Session ID for audit
            actor: Who initiated the command

        Returns:
            Tuple of (return_code, output)
        """
        if target_id is None:
            target_id = self.config.default_target

        start_time = time.time()

        # Policy check
        decision = self.policy.check_command(command)
        if decision == Decision.DENY:
            self.audit.record_event(
                session_id=session_id,
                actor=actor,
                domain=self.config.domain,
                tool="shell_exec",
                args={"command": command, "target": target_id},
                decision="deny",
                reason="denylist_match",
            )
            return (-1, f"⛔ Command denied by Policy Guard: {command[:80]}")

        # Execute
        rc, output = self.ssh_pool.execute(target_id, command, timeout=timeout)
        latency_ms = int((time.time() - start_time) * 1000)

        # Audit
        self.audit.record_event(
            session_id=session_id,
            actor=actor,
            domain=self.config.domain,
            tool="shell_exec",
            args={"command": command, "target": target_id},
            decision="allow",
            latency_ms=latency_ms,
            result=output[:500] if output else "",
        )

        return (rc, output)

    def build_hermes_system_prompt(self) -> str:
        """Build the full system prompt for the Hermes AIAgent.

        Combines:
        - Domain system prompt
        - Topology (ontology)
        - Knowledge index (condensed)
        - Available targets info
        - Policy summary
        """
        parts = [self.system_prompt]

        # Add topology (ontology)
        from proagent.core.ontology import load_and_render_topology
        topology_text = load_and_render_topology(self.domain_dir)
        if topology_text:
            parts.append(topology_text)

        # Add target info
        targets_info = "\n## Available Targets\n"
        for target in self.config.targets:
            targets_info += f"- `{target.id}`: {target.display_name}"
            if target.role:
                targets_info += f" (role: {target.role})"
            targets_info += "\n"
        if self.config.default_target:
            targets_info += f"\nDefault target: `{self.config.default_target}`\n"
        parts.append(targets_info)

        # Add knowledge index (if not too large)
        if self.knowledge_index and len(self.knowledge_index) < 4000:
            parts.append(f"\n## Domain Knowledge Index\n{self.knowledge_index}")

        pack = getattr(self, "_domain_pack", None)
        if pack:
            skills = pack.get_skills()
            if skills:
                parts.append("\n## Domain Skills\n" + "\n\n---\n\n".join(skills))

        # Add policy summary
        policy_summary = """
## Policy Rules
- You may ONLY execute read-only commands (no writes, no deletes, no restarts)
- All commands are audited
- If a command is denied, explain why and suggest alternatives
- Always provide evidence (command output) with your analysis
"""
        parts.append(policy_summary)

        return "\n\n".join(parts)

    def get_hermes_agent_kwargs(self) -> Dict[str, Any]:
        """Build kwargs for instantiating a Hermes AIAgent.

        Returns a dict suitable for passing to AIAgent(**kwargs).
        """
        model_config = self.config.models.executor

        kwargs = {
            "model": f"{model_config.provider}/{model_config.model}" if model_config.provider else model_config.model,
            "ephemeral_system_prompt": self.build_hermes_system_prompt(),
        }

        # Set provider-specific env vars
        if model_config.api_key:
            if model_config.provider == "openai":
                os.environ.setdefault("OPENAI_API_KEY", model_config.api_key)
            elif model_config.provider == "anthropic":
                os.environ.setdefault("ANTHROPIC_API_KEY", model_config.api_key)

        if model_config.base_url:
            kwargs["base_url"] = model_config.base_url

        return kwargs

    def create_inspection_run(self, target_id: str, kind: str, trigger: str) -> str:
        """Create a new inspection run record. Returns the run ID."""
        run_id = str(uuid.uuid4())[:8]
        self.audit.record_inspection(
            run_id=run_id,
            target=target_id,
            kind=kind,
            trigger=trigger,
        )
        return run_id

    def complete_inspection_run(self, run_id: str, status: str, summary: str = "", report: str = "") -> None:
        """Mark an inspection run as completed."""
        self.audit.complete_inspection(run_id, status, summary, report)
