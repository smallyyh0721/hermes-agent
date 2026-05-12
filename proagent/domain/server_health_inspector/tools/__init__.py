"""Server Health Inspector Tools - Self-registering tool set."""

from proagent.core.agent import ToolDef, build_server_shell_tool


def get_tools(runtime) -> list:
    """Return all tools for the SRE domain."""
    return [build_server_shell_tool(runtime)]
