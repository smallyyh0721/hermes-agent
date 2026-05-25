"""Develop Agent tool declarations."""

from __future__ import annotations

from proagent.core.agent import ToolDef
from proagent.storage.phase5 import WorkItemStore


def get_tools(runtime):
    work_store = WorkItemStore("proagent/storage/work_items.db")
    return [
        ToolDef(
            name="code_read",
            description="Read scoped project files for implementation context.",
            parameters={
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
            },
            handler=lambda path, **_: _read_file(path),
            category="read_only",
        ),
        ToolDef(
            name="code_edit",
            description="Write scoped ProAgent source or docs content for an approved work item.",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "content": {"type": "string"},
                },
                "required": ["path", "content"],
            },
            handler=lambda path, content, **_: _write_scoped_file(path, content),
            category="write_action",
        ),
        ToolDef(
            name="work_item_create",
            description="Create a Phase 5 work item from a requirement, PRD, bug report, or milestone.",
            parameters={
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "kind": {"type": "string"},
                    "requirement_ref": {"type": "string"},
                },
                "required": ["title", "kind", "requirement_ref"],
            },
            handler=lambda title, kind, requirement_ref, **_: (
                "Created work item: "
                + work_store.create_work_item(title, kind, "develop", requirement_ref)
            ),
            category="write_action",
        ),
        ToolDef(
            name="work_item_update",
            description="Update implementation or test status for an existing work item.",
            parameters={
                "type": "object",
                "properties": {
                    "item_id": {"type": "string"},
                    "status": {"type": "string"},
                    "test_status": {"type": "string"},
                },
                "required": ["item_id"],
            },
            handler=lambda item_id, status="", test_status="", **_: _update_work_item(
                work_store, item_id, status, test_status
            ),
            category="write_action",
        ),
        ToolDef(
            name="docs_update",
            description="Record that product documentation must be updated before implementation.",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "summary": {"type": "string"},
                },
                "required": ["path", "summary"],
            },
            handler=lambda path, summary, **_: f"Docs update required: {path}\n{summary}",
            category="write_action",
        ),
        ToolDef(
            name="test_delegate",
            description="Prepare a Test Agent handoff with verification commands and expected behavior.",
            parameters={
                "type": "object",
                "properties": {
                    "changed_files": {"type": "string"},
                    "test_plan": {"type": "string"},
                },
                "required": ["changed_files", "test_plan"],
            },
            handler=lambda changed_files, test_plan, **_: (
                f"Test Agent handoff\nChanged files:\n{changed_files}\n\nTest plan:\n{test_plan}"
            ),
            category="suggest",
        ),
    ]


def _read_file(path: str) -> str:
    from pathlib import Path

    p = Path(path)
    if not p.exists() or not p.is_file():
        return f"File not found: {path}"
    text = p.read_text(encoding="utf-8")
    return text[:20000] + ("\n... [truncated]" if len(text) > 20000 else "")


def _write_scoped_file(path: str, content: str) -> str:
    from pathlib import Path

    p = Path(path)
    allowed_roots = ("proagent", "docs", "AGENTS.md", "Dockerfile.proagent", "docker-compose.proagent.yml")
    if not any(str(p).replace("\\", "/").startswith(root) for root in allowed_roots):
        return f"Denied: path outside Develop Agent scope: {path}"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return f"Wrote {p}"


def _update_work_item(store: WorkItemStore, item_id: str, status: str = "", test_status: str = "") -> str:
    fields = {}
    if status:
        fields["status"] = status
    if test_status:
        fields["test_status"] = test_status
    store.update_work_item(item_id, **fields)
    return f"Updated work item: {item_id}"
