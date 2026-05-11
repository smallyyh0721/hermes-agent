"""Audit persistence - SQLite-backed audit trail for all tool calls."""

import hashlib
import json
import logging
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class AuditStore:
    """SQLite-backed audit event storage.

    Thread-safe. Creates tables on first use.
    """

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._init_db()

    def _init_db(self):
        with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            try:
                conn.executescript("""
                    CREATE TABLE IF NOT EXISTS audit_event (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        ts REAL NOT NULL,
                        session_id TEXT,
                        actor TEXT NOT NULL,
                        domain TEXT NOT NULL,
                        tool TEXT NOT NULL,
                        args_hash TEXT NOT NULL,
                        decision TEXT NOT NULL,
                        reason TEXT DEFAULT '',
                        latency_ms INTEGER DEFAULT 0,
                        result_hash TEXT DEFAULT ''
                    );

                    CREATE TABLE IF NOT EXISTS inspection_run (
                        id TEXT PRIMARY KEY,
                        target TEXT NOT NULL,
                        kind TEXT NOT NULL,
                        trigger TEXT NOT NULL,
                        started_at REAL NOT NULL,
                        ended_at REAL,
                        status TEXT NOT NULL,
                        summary TEXT,
                        report_json TEXT
                    );

                    CREATE INDEX IF NOT EXISTS idx_audit_ts ON audit_event(ts);
                    CREATE INDEX IF NOT EXISTS idx_audit_session ON audit_event(session_id);
                    CREATE INDEX IF NOT EXISTS idx_audit_tool ON audit_event(tool);
                    CREATE INDEX IF NOT EXISTS idx_inspection_target ON inspection_run(target);
                    CREATE INDEX IF NOT EXISTS idx_inspection_status ON inspection_run(status);
                """)
                conn.commit()
            finally:
                conn.close()

    def record_event(
        self,
        session_id: str,
        actor: str,
        domain: str,
        tool: str,
        args: Dict[str, Any],
        decision: str,
        reason: str = "",
        latency_ms: int = 0,
        result: str = "",
    ) -> None:
        """Record a single audit event."""
        args_hash = hashlib.sha256(json.dumps(args, sort_keys=True).encode()).hexdigest()[:16]
        result_hash = hashlib.sha256(result.encode()).hexdigest()[:16] if result else ""

        with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            try:
                conn.execute(
                    """INSERT INTO audit_event
                       (ts, session_id, actor, domain, tool, args_hash, decision, reason, latency_ms, result_hash)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (time.time(), session_id, actor, domain, tool, args_hash, decision, reason, latency_ms, result_hash),
                )
                conn.commit()
            finally:
                conn.close()

    def record_inspection(
        self,
        run_id: str,
        target: str,
        kind: str,
        trigger: str,
        status: str = "running",
        summary: str = "",
        report_json: str = "",
    ) -> None:
        """Record or update an inspection run."""
        with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            try:
                conn.execute(
                    """INSERT OR REPLACE INTO inspection_run
                       (id, target, kind, trigger, started_at, ended_at, status, summary, report_json)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (run_id, target, kind, trigger, time.time(), None, status, summary, report_json),
                )
                conn.commit()
            finally:
                conn.close()

    def complete_inspection(self, run_id: str, status: str, summary: str = "", report_json: str = "") -> None:
        """Mark an inspection run as completed."""
        with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            try:
                conn.execute(
                    """UPDATE inspection_run SET ended_at=?, status=?, summary=?, report_json=?
                       WHERE id=?""",
                    (time.time(), status, summary, report_json, run_id),
                )
                conn.commit()
            finally:
                conn.close()

    def get_recent_events(self, limit: int = 50, tool: str = None) -> List[Dict[str, Any]]:
        """Retrieve recent audit events."""
        with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            conn.row_factory = sqlite3.Row
            try:
                if tool:
                    rows = conn.execute(
                        "SELECT * FROM audit_event WHERE tool=? ORDER BY ts DESC LIMIT ?",
                        (tool, limit),
                    ).fetchall()
                else:
                    rows = conn.execute(
                        "SELECT * FROM audit_event ORDER BY ts DESC LIMIT ?",
                        (limit,),
                    ).fetchall()
                return [dict(row) for row in rows]
            finally:
                conn.close()

    def get_recent_inspections(self, target: str = None, limit: int = 20) -> List[Dict[str, Any]]:
        """Retrieve recent inspection runs."""
        with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            conn.row_factory = sqlite3.Row
            try:
                if target:
                    rows = conn.execute(
                        "SELECT * FROM inspection_run WHERE target=? ORDER BY started_at DESC LIMIT ?",
                        (target, limit),
                    ).fetchall()
                else:
                    rows = conn.execute(
                        "SELECT * FROM inspection_run ORDER BY started_at DESC LIMIT ?",
                        (limit,),
                    ).fetchall()
                return [dict(row) for row in rows]
            finally:
                conn.close()
