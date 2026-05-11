"""server_shell - Execute read-only shell commands on target servers.

This tool is the primary interface for the Server Health Inspector agent
to interact with target servers. All commands are subject to Policy Guard
denylist enforcement.

Registers with Hermes tool registry as 'server_shell' in toolset 'proagent'.
"""

import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict

# Ensure proagent is importable
sys.path.insert(0, str(Path(__file__).resolve().parents[5]))

from tools.registry import registry

logger = logging.getLogger(__name__)

# Module-level reference to the runtime (set by ProAgent startup)
_runtime = None


def set_runtime(runtime) -> None:
    """Set the ProAgent runtime reference for tool execution."""
    global _runtime
    _runtime = runtime


def _server_shell_handler(command: str, target: str = "", **kwargs) -> str:
    """Execute a read-only shell command on a target server.

    Args:
        command: The shell command to execute (must be read-only)
        target: Target server ID. If empty, uses the configured default target.

    Returns:
        Command output as a string, or error message if denied/failed.
    """
    if _runtime is None:
        return "❌ ProAgent runtime not initialized. Run `proagent run` first."

    target_id = target if target else None
    session_id = kwargs.get("session_id", "interactive")

    rc, output = _runtime.execute_on_target(
        command=command,
        target_id=target_id,
        timeout=30,
        session_id=session_id,
        actor="agent",
    )

    if rc == -1 and output.startswith("⛔"):
        # Policy denied
        return output

    if rc == -1:
        return f"❌ Command failed: {output}"

    # Format output with return code info
    if rc != 0:
        return f"[exit code: {rc}]\n{output}"

    return output


def check_proagent_available() -> bool:
    """Check if ProAgent runtime is available."""
    return _runtime is not None


# Register with Hermes tool registry
registry.register(
    name="server_shell",
    toolset="proagent",
    schema={
        "name": "server_shell",
        "description": (
            "Execute a read-only shell command on a target server for health inspection. "
            "Only diagnostic/monitoring commands are allowed. "
            "Write operations (rm, kill, systemctl restart, etc.) are blocked by policy. "
            "Use this to check CPU, memory, disk, network, processes, services, and logs."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": (
                        "Shell command to execute. Must be read-only. "
                        "Examples: 'free -m', 'df -hT', 'ps aux --sort=-%cpu | head -20', "
                        "'systemctl --failed', 'journalctl --since \"1 hour ago\" -p err --no-pager | tail -50'"
                    ),
                },
                "target": {
                    "type": "string",
                    "description": (
                        "Target server ID to execute on. "
                        "Leave empty to use the default target. "
                        "Use 'local' for the local machine."
                    ),
                    "default": "",
                },
            },
            "required": ["command"],
        },
    },
    handler=_server_shell_handler,
    check_fn=check_proagent_available,
    requires_env=[],
    is_async=False,
    description="Execute read-only shell commands on target servers for health inspection",
    emoji="🔍",
)
