"""Phase 5 SQLite stores for productized ProAgent runtime state."""

from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
import re
from typing import Any, Dict, List, Optional


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    return conn


def _rows(cursor: sqlite3.Cursor) -> List[Dict[str, Any]]:
    return [dict(row) for row in cursor.fetchall()]


class SessionHistoryStore:
    """Durable session, message, and tool-event history."""

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self._init_db()

    def _init_db(self) -> None:
        with _connect(self.db_path) as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    agent_id TEXT NOT NULL,
                    channel_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    source TEXT NOT NULL,
                    status TEXT NOT NULL,
                    summary TEXT NOT NULL DEFAULT '',
                    started_at TEXT NOT NULL,
                    ended_at TEXT
                );
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(session_id) REFERENCES sessions(session_id)
                );
                CREATE TABLE IF NOT EXISTS tool_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    tool_name TEXT NOT NULL,
                    args_json TEXT NOT NULL,
                    result TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(session_id) REFERENCES sessions(session_id)
                );
                """
            )

    def start_session(
        self,
        agent_id: str,
        channel_id: str,
        user_id: str,
        source: str,
        status: str = "running",
        session_id: Optional[str] = None,
    ) -> str:
        sid = session_id or str(uuid.uuid4())
        with _connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO sessions
                    (session_id, agent_id, channel_id, user_id, source, status, started_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (sid, agent_id, channel_id, user_id, source, status, _utc_now()),
            )
        return sid

    def add_message(self, session_id: str, role: str, content: str) -> None:
        with _connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO messages (session_id, role, content, created_at) VALUES (?, ?, ?, ?)",
                (session_id, role, content, _utc_now()),
            )

    def add_tool_event(self, session_id: str, tool_name: str, args: Any, result: str) -> None:
        import json

        with _connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO tool_events (session_id, tool_name, args_json, result, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (session_id, tool_name, json.dumps(args, ensure_ascii=False), result, _utc_now()),
            )

    def finish_session(self, session_id: str, status: str, summary: str = "") -> None:
        with _connect(self.db_path) as conn:
            conn.execute(
                "UPDATE sessions SET status = ?, summary = ?, ended_at = ? WHERE session_id = ?",
                (status, summary, _utc_now(), session_id),
            )

    def list_sessions(self, limit: int = 50, agent_id: str = "") -> List[Dict[str, Any]]:
        with _connect(self.db_path) as conn:
            if agent_id:
                return _rows(
                    conn.execute(
                        "SELECT * FROM sessions WHERE agent_id = ? ORDER BY started_at DESC LIMIT ?",
                        (agent_id, limit),
                    )
                )
            return _rows(conn.execute("SELECT * FROM sessions ORDER BY started_at DESC LIMIT ?", (limit,)))

    def get_messages(self, session_id: str) -> List[Dict[str, Any]]:
        with _connect(self.db_path) as conn:
            return _rows(
                conn.execute(
                    "SELECT * FROM messages WHERE session_id = ? ORDER BY id ASC",
                    (session_id,),
                )
            )

    def get_tool_events(self, session_id: str) -> List[Dict[str, Any]]:
        with _connect(self.db_path) as conn:
            return _rows(
                conn.execute(
                    "SELECT * FROM tool_events WHERE session_id = ? ORDER BY id ASC",
                    (session_id,),
                )
            )


class WorkItemStore:
    """Feature, bugfix, and test handoff work items."""

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self._init_db()

    def _init_db(self) -> None:
        with _connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS work_items (
                    item_id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    agent_id TEXT NOT NULL,
                    requirement_ref TEXT NOT NULL,
                    status TEXT NOT NULL,
                    test_status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )

    def create_work_item(
        self,
        title: str,
        kind: str,
        agent_id: str,
        requirement_ref: str,
        status: str = "planned",
        test_status: str = "not_run",
    ) -> str:
        item_id = str(uuid.uuid4())
        now = _utc_now()
        with _connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO work_items
                    (item_id, title, kind, agent_id, requirement_ref, status, test_status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (item_id, title, kind, agent_id, requirement_ref, status, test_status, now, now),
            )
        return item_id

    def update_work_item(self, item_id: str, **fields: str) -> None:
        allowed = {"title", "kind", "agent_id", "requirement_ref", "status", "test_status"}
        updates = [(k, v) for k, v in fields.items() if k in allowed]
        if not updates:
            return
        set_clause = ", ".join(f"{k} = ?" for k, _ in updates) + ", updated_at = ?"
        values = [v for _, v in updates] + [_utc_now(), item_id]
        with _connect(self.db_path) as conn:
            conn.execute(f"UPDATE work_items SET {set_clause} WHERE item_id = ?", values)

    def list_work_items(self, limit: int = 100) -> List[Dict[str, Any]]:
        with _connect(self.db_path) as conn:
            return _rows(conn.execute("SELECT * FROM work_items ORDER BY updated_at DESC LIMIT ?", (limit,)))


class UsageStore:
    """Token usage and estimated cost records."""

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self._init_db()

    def _init_db(self) -> None:
        with _connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS usage_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    agent_id TEXT NOT NULL,
                    provider TEXT NOT NULL,
                    model TEXT NOT NULL,
                    input_tokens INTEGER NOT NULL DEFAULT 0,
                    output_tokens INTEGER NOT NULL DEFAULT 0,
                    cache_read_tokens INTEGER NOT NULL DEFAULT 0,
                    cache_write_tokens INTEGER NOT NULL DEFAULT 0,
                    reasoning_tokens INTEGER NOT NULL DEFAULT 0,
                    estimated_cost REAL NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL
                )
                """
            )

    def record_usage(
        self,
        session_id: str,
        agent_id: str,
        provider: str,
        model: str,
        input_tokens: int = 0,
        output_tokens: int = 0,
        cache_read_tokens: int = 0,
        cache_write_tokens: int = 0,
        reasoning_tokens: int = 0,
        estimated_cost: float = 0.0,
    ) -> None:
        with _connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO usage_records
                    (session_id, agent_id, provider, model, input_tokens, output_tokens,
                     cache_read_tokens, cache_write_tokens, reasoning_tokens, estimated_cost, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    agent_id,
                    provider,
                    model,
                    input_tokens,
                    output_tokens,
                    cache_read_tokens,
                    cache_write_tokens,
                    reasoning_tokens,
                    estimated_cost,
                    _utc_now(),
                ),
            )

    def list_usage(self, limit: int = 100) -> List[Dict[str, Any]]:
        with _connect(self.db_path) as conn:
            return _rows(conn.execute("SELECT * FROM usage_records ORDER BY id DESC LIMIT ?", (limit,)))

    def daily_totals(self) -> Dict[str, Any]:
        with _connect(self.db_path) as conn:
            row = conn.execute(
                """
                SELECT
                    COALESCE(SUM(input_tokens), 0) AS input_tokens,
                    COALESCE(SUM(output_tokens), 0) AS output_tokens,
                    COALESCE(SUM(cache_read_tokens), 0) AS cache_read_tokens,
                    COALESCE(SUM(cache_write_tokens), 0) AS cache_write_tokens,
                    COALESCE(SUM(reasoning_tokens), 0) AS reasoning_tokens,
                    COALESCE(SUM(estimated_cost), 0) AS estimated_cost
                FROM usage_records
                WHERE substr(created_at, 1, 10) = substr(?, 1, 10)
                """,
                (_utc_now(),),
            ).fetchone()
        return dict(row)


class SkillDraftStore:
    """Draft-first skill lifecycle store."""

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self._init_db()

    def _init_db(self) -> None:
        with _connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS skill_drafts (
                    draft_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT NOT NULL,
                    owner_agent TEXT NOT NULL,
                    content TEXT NOT NULL,
                    evidence TEXT NOT NULL,
                    tests TEXT NOT NULL,
                    status TEXT NOT NULL,
                    enabled_path TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )

    def create_draft(
        self,
        name: str,
        description: str,
        owner_agent: str,
        content: str,
        evidence: str,
        tests: str,
    ) -> str:
        draft_id = str(uuid.uuid4())
        now = _utc_now()
        with _connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO skill_drafts
                    (draft_id, name, description, owner_agent, content, evidence, tests, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (draft_id, name, description, owner_agent, content, evidence, tests, "draft", now, now),
            )
        return draft_id

    def update_status(self, draft_id: str, status: str, enabled_path: str = "") -> None:
        with _connect(self.db_path) as conn:
            conn.execute(
                """
                UPDATE skill_drafts
                SET status = ?, enabled_path = COALESCE(NULLIF(?, ''), enabled_path), updated_at = ?
                WHERE draft_id = ?
                """,
                (status, enabled_path, _utc_now(), draft_id),
            )

    def get_draft(self, draft_id: str) -> Dict[str, Any]:
        with _connect(self.db_path) as conn:
            row = conn.execute("SELECT * FROM skill_drafts WHERE draft_id = ?", (draft_id,)).fetchone()
        if row is None:
            raise KeyError(f"Unknown skill draft: {draft_id}")
        return dict(row)

    def list_drafts(self, limit: int = 100, status: str = "") -> List[Dict[str, Any]]:
        with _connect(self.db_path) as conn:
            if status:
                return _rows(
                    conn.execute(
                        "SELECT * FROM skill_drafts WHERE status = ? ORDER BY updated_at DESC LIMIT ?",
                        (status, limit),
                    )
                )
            return _rows(conn.execute("SELECT * FROM skill_drafts ORDER BY updated_at DESC LIMIT ?", (limit,)))


def enable_skill_draft(store: SkillDraftStore, draft_id: str, pack_dir: str | Path) -> Path:
    """Enable an approved skill draft by writing it into a domain pack skills directory."""
    draft = store.get_draft(draft_id)
    skills_dir = Path(pack_dir) / "skills"
    skills_dir.mkdir(parents=True, exist_ok=True)
    slug = re.sub(r"[^a-z0-9]+", "_", draft["name"].lower()).strip("_") or "generated_skill"
    target = skills_dir / f"{slug}.md"
    content = draft["content"]
    if "## Generated from" not in content:
        content = (
            content.rstrip()
            + "\n\n## Generated from\n"
            + f"- draft_id: {draft_id}\n"
            + f"- owner_agent: {draft['owner_agent']}\n"
            + f"- evidence: {draft['evidence']}\n"
            + f"- tests: {draft['tests']}\n"
        )
    target.write_text(content + "\n", encoding="utf-8")
    store.update_status(draft_id, "enabled", str(target))
    return target


class LayeredMemoryStore:
    """Layered memory for user, lab, target, and agent knowledge."""

    VALID_LAYERS = {"user", "lab", "target", "agent"}

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self._init_db()

    def _init_db(self) -> None:
        with _connect(self.db_path) as conn:
            existing_columns = set()
            existing = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='memory_items'"
            ).fetchone()
            if existing:
                existing_columns = {
                    row["name"] for row in conn.execute("PRAGMA table_info(memory_items)").fetchall()
                }
                if "owner_id" not in existing_columns or self._has_legacy_memory_unique_key(conn):
                    self._rebuild_memory_table(conn)
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS memory_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    layer TEXT NOT NULL,
                    owner_id TEXT NOT NULL DEFAULT '',
                    scope_id TEXT NOT NULL DEFAULT '',
                    key TEXT NOT NULL,
                    value TEXT NOT NULL,
                    source TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(layer, owner_id, scope_id, key)
                )
                """
            )

    def _has_legacy_memory_unique_key(self, conn: sqlite3.Connection) -> bool:
        for index in conn.execute("PRAGMA index_list(memory_items)").fetchall():
            if not index["unique"]:
                continue
            cols = [row["name"] for row in conn.execute(f"PRAGMA index_info({index['name']})").fetchall()]
            if cols == ["layer", "key"]:
                return True
        return False

    def _rebuild_memory_table(self, conn: sqlite3.Connection) -> None:
        conn.execute("ALTER TABLE memory_items RENAME TO memory_items_legacy")
        conn.execute(
            """
            CREATE TABLE memory_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                layer TEXT NOT NULL,
                owner_id TEXT NOT NULL DEFAULT '',
                scope_id TEXT NOT NULL DEFAULT '',
                key TEXT NOT NULL,
                value TEXT NOT NULL,
                source TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(layer, owner_id, scope_id, key)
            )
            """
        )
        legacy_columns = {
            row["name"] for row in conn.execute("PRAGMA table_info(memory_items_legacy)").fetchall()
        }
        owner_expr = "owner_id" if "owner_id" in legacy_columns else "''"
        scope_expr = "scope_id" if "scope_id" in legacy_columns else "''"
        conn.execute(
            f"""
            INSERT OR IGNORE INTO memory_items (id, layer, owner_id, scope_id, key, value, source, updated_at)
            SELECT id, layer, {owner_expr}, {scope_expr}, key, value, source, updated_at
            FROM memory_items_legacy
            """
        )
        conn.execute("DROP TABLE memory_items_legacy")

    def upsert_memory(
        self,
        layer: str,
        key: str,
        value: str,
        source: str = "",
        owner_id: str = "",
        scope_id: str = "",
    ) -> None:
        if layer not in self.VALID_LAYERS:
            raise ValueError(f"Invalid memory layer: {layer}")
        with _connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO memory_items (layer, owner_id, scope_id, key, value, source, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(layer, owner_id, scope_id, key) DO UPDATE SET
                    value = excluded.value,
                    source = excluded.source,
                    updated_at = excluded.updated_at
                """,
                (layer, owner_id, scope_id, key, value, source, _utc_now()),
            )

    def list_memory(
        self,
        layer: str = "",
        limit: int = 100,
        owner_id: Optional[str] = None,
        scope_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        filters = []
        values: List[Any] = []
        if layer:
            filters.append("layer = ?")
            values.append(layer)
        if owner_id is not None:
            filters.append("owner_id = ?")
            values.append(owner_id)
        if scope_id is not None:
            filters.append("scope_id = ?")
            values.append(scope_id)
        where = " WHERE " + " AND ".join(filters) if filters else ""
        values.append(limit)
        with _connect(self.db_path) as conn:
            return _rows(
                conn.execute(
                    f"SELECT * FROM memory_items{where} ORDER BY updated_at DESC LIMIT ?",
                    values,
                )
            )

    def search(
        self,
        query: str,
        layer: str = "",
        limit: int = 20,
        owner_id: Optional[str] = None,
        scope_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        pattern = f"%{query.lower()}%"
        filters = ["(lower(key) LIKE ? OR lower(value) LIKE ?)"]
        values: List[Any] = [pattern, pattern]
        if layer:
            filters.append("layer = ?")
            values.append(layer)
        if owner_id is not None:
            filters.append("owner_id = ?")
            values.append(owner_id)
        if scope_id is not None:
            filters.append("scope_id = ?")
            values.append(scope_id)
        where = " AND ".join(filters)
        values.append(limit)
        with _connect(self.db_path) as conn:
            return _rows(
                conn.execute(
                    f"SELECT * FROM memory_items WHERE {where} ORDER BY updated_at DESC LIMIT ?",
                    values,
                )
            )

    def search_for_user(self, query: str, owner_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Return only personal memory for a user id."""
        if not owner_id:
            return []
        return self.search(query=query, layer="user", owner_id=owner_id, limit=limit)
