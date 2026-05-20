"""Phase 4 GUI smoke tests.

We can't fully spin up Streamlit in a unit test, but we CAN verify:
- The GUI module is importable
- AGENT_DISPLAY contains the three Phase 4 agents
- The CLI dispatches the 'gui' command correctly (delegates to streamlit run)
- _list_reports / _list_aigc_history work with empty state

Run with:
    pytest proagent/domain/test_agent/tests/test_gui.py -v --override-ini="addopts="
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))


# Streamlit is required for the GUI module to import. If not installed, skip.
streamlit = pytest.importorskip("streamlit")


class TestGUIImports:

    def test_app_module_imports(self):
        # Just importing should not raise even without a Streamlit context
        from proagent.gui import app
        assert hasattr(app, "main")
        assert hasattr(app, "AGENT_DISPLAY")

    def test_three_agents_in_display_map(self):
        from proagent.gui.app import AGENT_DISPLAY
        for required in (
            "server-health-inspector",
            "aigc-creator",
            "test-agent",
        ):
            assert required in AGENT_DISPLAY
            label, desc = AGENT_DISPLAY[required]
            assert label and desc


class TestGUIHelpers:

    def test_list_reports_handles_missing_dir(self, tmp_path, monkeypatch):
        from proagent.gui import app
        # Point REPORTS_DIR at a non-existent path
        monkeypatch.setattr(app, "REPORTS_DIR", tmp_path / "nonexistent")
        assert app._list_reports() == []

    def test_list_reports_returns_md_files(self, tmp_path, monkeypatch):
        from proagent.gui import app
        monkeypatch.setattr(app, "REPORTS_DIR", tmp_path)
        (tmp_path / "diagnosis-2026-01-01_120000-web01.md").write_text("# diag")
        (tmp_path / "inspection-quick-2026-01-02_120000-web01.md").write_text("# insp")
        (tmp_path / "ignore.txt").write_text("not markdown")
        reports = app._list_reports()
        names = [r.name for r in reports]
        assert "diagnosis-2026-01-01_120000-web01.md" in names
        assert "inspection-quick-2026-01-02_120000-web01.md" in names
        assert "ignore.txt" not in names

    def test_list_aigc_history_empty_when_no_db(self, tmp_path, monkeypatch):
        from proagent.gui import app
        monkeypatch.setattr(app, "AIGC_HISTORY_DB", tmp_path / "no-such.db")
        assert app._list_aigc_history() == []

    def test_list_aigc_history_reads_rows(self, tmp_path, monkeypatch):
        import sqlite3
        from proagent.gui import app

        db = tmp_path / "aigc_history.db"
        conn = sqlite3.connect(str(db))
        conn.execute(
            """
            CREATE TABLE aigc_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts INTEGER,
                prompt TEXT,
                aspect_ratio TEXT,
                variant_index INTEGER,
                output_path TEXT,
                success INTEGER,
                error TEXT,
                rating TEXT
            )
            """
        )
        conn.execute(
            "INSERT INTO aigc_history (ts, prompt, aspect_ratio, variant_index, output_path, success, error, rating) "
            "VALUES (1700000000, 'a cat', '1:1', 1, '/tmp/cat.png', 1, '', 'good')"
        )
        conn.commit()
        conn.close()

        monkeypatch.setattr(app, "AIGC_HISTORY_DB", db)
        history = app._list_aigc_history(limit=10)
        assert len(history) == 1
        h = history[0]
        assert h["prompt"] == "a cat"
        assert h["success"] is True
        assert h["rating"] == "good"


class TestCLIGuiCommand:
    """Verify the CLI 'gui' command dispatches to streamlit run."""

    def test_cmd_gui_invokes_streamlit(self, monkeypatch, tmp_path, capsys):
        import argparse
        from proagent.cli.main import cmd_gui

        called = {}

        def fake_run(cmd, check=False):
            called["cmd"] = cmd
            class _Result: returncode = 0
            return _Result()

        monkeypatch.setattr("subprocess.run", fake_run)

        args = argparse.Namespace(port=8501, host="localhost")
        cmd_gui(args)
        out = capsys.readouterr().out
        assert "启动 ProAgent GUI" in out
        # Streamlit invoked with the app path and the right flags
        cmd = called.get("cmd", [])
        assert any(part.endswith("streamlit") or part == "streamlit" for part in cmd)
        assert "--server.port" in cmd
        assert "8501" in cmd


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short", "--override-ini=addopts="])
