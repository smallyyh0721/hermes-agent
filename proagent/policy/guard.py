"""Policy Guard - Enforces permission boundaries on tool calls.

The guard operates in denylist mode: any shell command matching a forbidden
pattern is rejected. All other read-only commands are allowed by default.
Write-action tools are blocked entirely in Phase 1.
"""

import logging
import re
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

logger = logging.getLogger(__name__)


class Decision(Enum):
    ALLOW = "allow"
    DENY = "deny"
    APPROVAL_REQUIRED = "approval_required"


class ToolCategory(Enum):
    READ_ONLY = "read_only"
    SUGGEST = "suggest"
    WRITE_ACTION = "write_action"


@dataclass
class AuditEvent:
    ts: float
    session_id: str
    actor: str
    domain: str
    tool: str
    args_hash: str
    decision: str
    reason: str = ""
    latency_ms: int = 0
    result_hash: str = ""


@dataclass
class PolicyConfig:
    """Loaded from domain policy.yaml."""
    denylist_patterns: List[re.Pattern] = field(default_factory=list)
    timeout_sec: int = 30
    max_output_kb: int = 256
    forbidden_tools: List[str] = field(default_factory=list)
    allow_auto: List[str] = field(default_factory=list)
    require_approval: List[str] = field(default_factory=list)
    write_action_whitelist: List[str] = field(default_factory=list)  # Phase 4: per-domain whitelist of allowed write tools


def load_policy(policy_path: Path) -> PolicyConfig:
    """Load policy configuration from a YAML file."""
    if not policy_path.exists():
        logger.warning("Policy file not found: %s, using defaults", policy_path)
        return PolicyConfig()

    with open(policy_path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}

    config = PolicyConfig()

    # Load sandbox denylist patterns
    sandbox = raw.get("sandbox", {})
    shell_config = sandbox.get("shell", {})
    patterns = shell_config.get("denylist_patterns", [])
    for pattern in patterns:
        try:
            config.denylist_patterns.append(re.compile(pattern))
        except re.error as e:
            logger.warning("Invalid denylist pattern '%s': %s", pattern, e)

    config.timeout_sec = sandbox.get("timeout_sec", 30)
    config.max_output_kb = sandbox.get("max_output_kb", 256)

    # Load permission rules
    config.forbidden_tools = raw.get("forbidden", [])
    config.allow_auto = raw.get("allow_auto", [])
    config.require_approval = raw.get("require_approval", [])
    config.write_action_whitelist = raw.get("write_action_whitelist", [])

    return config


class PolicyGuard:
    """Enforces permission boundaries on all tool calls.

    Phase 1 behavior:
    - read_only tools: allowed (subject to denylist pattern check on shell commands)
    - suggest tools: allowed with rate limiting
    - write_action tools: always denied
    """

    def __init__(self, policy_config: PolicyConfig, domain: str = ""):
        self.config = policy_config
        self.domain = domain
        self._audit_log: List[AuditEvent] = []

    def check_command(self, command: str) -> Decision:
        """Check a shell command against the denylist patterns.

        Returns ALLOW if no pattern matches, DENY otherwise.
        """
        for pattern in self.config.denylist_patterns:
            if pattern.search(command):
                logger.warning(
                    "PolicyGuard DENIED command matching pattern '%s': %s",
                    pattern.pattern,
                    command[:100],
                )
                return Decision.DENY
        return Decision.ALLOW

    def check_tool(self, tool_name: str, category: ToolCategory, args: Dict[str, Any] = None) -> Decision:
        """Check whether a tool call is permitted.

        Args:
            tool_name: The tool being called
            category: The tool's permission category
            args: Tool arguments (used for shell command inspection)

        Returns:
            Decision.ALLOW, Decision.DENY, or Decision.APPROVAL_REQUIRED
        """
        # write_action: deny by default, but allow if explicitly whitelisted in policy
        if category == ToolCategory.WRITE_ACTION:
            if tool_name in self.config.write_action_whitelist:
                logger.info(
                    "PolicyGuard ALLOW write_action '%s' (whitelisted in domain '%s')",
                    tool_name, self.domain,
                )
                return Decision.ALLOW
            logger.warning(
                "PolicyGuard DENY write_action '%s' (not in whitelist for domain '%s')",
                tool_name, self.domain,
            )
            return Decision.DENY

        # Check forbidden list
        for forbidden in self.config.forbidden_tools:
            forbidden_re = forbidden.replace("*", ".*")
            if re.match(forbidden_re, tool_name):
                return Decision.DENY

        # For read_only tools with shell commands, check denylist
        if category == ToolCategory.READ_ONLY and args:
            command = args.get("command", "")
            if command:
                return self.check_command(command)

        return Decision.ALLOW

    def audit(self, event: AuditEvent) -> None:
        """Record an audit event."""
        self._audit_log.append(event)
        logger.info(
            "AUDIT [%s] %s -> %s (%s) decision=%s",
            event.domain,
            event.actor,
            event.tool,
            event.args_hash[:8] if event.args_hash else "?",
            event.decision,
        )

    def get_audit_log(self) -> List[AuditEvent]:
        """Return all audit events."""
        return list(self._audit_log)
