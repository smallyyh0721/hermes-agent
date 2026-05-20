"""Server Health Inspector Tools - Self-registering tool set.

Phase 4: Adds two whitelisted write_action tools (diagnosis + inspection reports).
All other write actions remain blocked by Policy Guard.
"""

from proagent.core.agent import ToolDef, build_server_shell_tool
from proagent.domain.server_health_inspector.tools.write_report import (
    write_diagnosis_report_handler,
    write_inspection_report_handler,
)


def get_tools(runtime) -> list:
    """Return all tools for the SRE domain."""
    return [
        build_server_shell_tool(runtime),
        ToolDef(
            name="write_diagnosis_report",
            description=(
                "Write a fault diagnosis report to proagent/storage/reports/. "
                "Use this AFTER you have completed root cause analysis with read-only tools. "
                "This is one of only TWO write operations the SRE agent is allowed to perform. "
                "Provide concise summary, raw evidence (command output excerpts), and suggested "
                "remediation steps (suggestions only — they will NOT be executed automatically)."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "target": {
                        "type": "string",
                        "description": "Target host or system being diagnosed (e.g. 'web-01', 'ceph-cluster')",
                    },
                    "summary": {
                        "type": "string",
                        "description": "One-paragraph summary of the issue and root cause hypothesis",
                    },
                    "evidence": {
                        "type": "string",
                        "description": "Raw evidence: relevant log lines, command outputs, metric values",
                        "default": "",
                    },
                    "severity": {
                        "type": "string",
                        "description": "Severity level: low | medium | high | critical",
                        "default": "medium",
                    },
                    "suggested_steps": {
                        "type": "string",
                        "description": "Numbered list of suggested remediation steps (text only — not executed)",
                        "default": "",
                    },
                },
                "required": ["target", "summary"],
            },
            handler=write_diagnosis_report_handler,
            category="write_action",
        ),
        ToolDef(
            name="write_inspection_report",
            description=(
                "Write a health inspection report to proagent/storage/reports/. "
                "Use this AFTER completing a quick or full inspection. "
                "This is the second of only TWO write operations the SRE agent is allowed to perform. "
                "Summarize findings, include key metrics snapshots, and list issues found (or 'none')."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "target": {
                        "type": "string",
                        "description": "Target host (e.g. 'web-01' or 'local')",
                    },
                    "kind": {
                        "type": "string",
                        "description": "Inspection kind: 'quick' | 'full' | 'scheduled'",
                    },
                    "summary": {
                        "type": "string",
                        "description": "One-paragraph health summary",
                    },
                    "metrics": {
                        "type": "string",
                        "description": "Plain-text key metrics: CPU/memory/disk/network snapshots",
                        "default": "",
                    },
                    "issues": {
                        "type": "string",
                        "description": "Issues found, one per line, or 'none' if healthy",
                        "default": "none",
                    },
                },
                "required": ["target", "kind", "summary"],
            },
            handler=write_inspection_report_handler,
            category="write_action",
        ),
    ]
