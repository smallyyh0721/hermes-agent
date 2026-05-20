"""Phase 4 AIGC Agent tests — verify prompt optimizer, batch generator, history.

Tests:
- prompt_optimize covers all style presets and adds quality boosters
- image_generate_batch caps at 8, records history entries
- image_history_list shows recent entries
- image_feedback validates ratings and persists them
- Policy: aigc_generate / image_generate_batch / image_feedback are whitelisted
- Policy: server_shell remains forbidden in AIGC pack

Run with:
    pytest proagent/domain/test_agent/tests/test_aigc_phase4.py -v --override-ini="addopts="
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# Ensure project root is importable
sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from proagent.policy.guard import Decision, PolicyGuard, ToolCategory, load_policy
from proagent.domain.base import load_pack
from proagent.domain.aigc_creator.tools.prompt_optimize import (
    prompt_optimize_handler,
    STYLE_PRESETS,
    QUALITY_BOOSTERS,
    DEFAULT_NEGATIVE,
)
from proagent.domain.aigc_creator.tools import image_batch
from proagent.domain.aigc_creator.tools.image_batch import (
    image_generate_batch_handler,
    image_history_list_handler,
    image_feedback_handler,
    MAX_IMAGES,
)


def _aigc_policy_path() -> Path:
    return (
        Path(__file__).resolve().parents[4]
        / "proagent" / "domain" / "aigc_creator" / "policy.yaml"
    )


def _aigc_guard() -> PolicyGuard:
    return PolicyGuard(load_policy(_aigc_policy_path()), domain="aigc-creator")


# ---- prompt_optimize --------------------------------------------------------

class TestPromptOptimize:

    def test_returns_quality_boosters(self):
        out = prompt_optimize_handler(idea="a cat on a sofa")
        assert QUALITY_BOOSTERS in out
        assert DEFAULT_NEGATIVE in out

    @pytest.mark.parametrize("style", list(STYLE_PRESETS.keys()))
    def test_each_style_preset_applies_segment(self, style):
        out = prompt_optimize_handler(idea="a robot", style=style)
        # The style segment must appear in the output
        assert STYLE_PRESETS[style] in out

    def test_unknown_style_falls_back_to_auto(self):
        out = prompt_optimize_handler(idea="x", style="not-a-real-style")
        assert STYLE_PRESETS["auto"] in out

    def test_extra_hints_included(self):
        out = prompt_optimize_handler(
            idea="a sunset",
            extra_hints="warm orange and pink palette",
        )
        assert "warm orange and pink palette" in out

    def test_aspect_ratio_passed_through(self):
        out = prompt_optimize_handler(idea="x", aspect_ratio="16:9")
        assert "16:9" in out


# ---- image_generate_batch + history ----------------------------------------

class TestImageBatchHistory:

    @pytest.fixture(autouse=True)
    def isolate_history_db(self, tmp_path, monkeypatch):
        # Redirect HISTORY_DB to a per-test sqlite file
        db_file = tmp_path / "aigc_history.db"
        monkeypatch.setattr(image_batch, "HISTORY_DB", db_file)
        yield db_file

    def test_batch_caps_at_max_images(self, isolate_history_db):
        with patch.object(
            image_batch,
            "aigc_generate_handler",
            return_value="✅ 生成成功！\n文件: /tmp/fake.png\n命令: mock",
        ):
            out = image_generate_batch_handler(
                prompt="a robot", count=20, aspect_ratio="1:1"
            )
        assert f"({MAX_IMAGES}/{MAX_IMAGES} 成功)" in out
        # Verify exactly MAX_IMAGES rows in history
        conn = sqlite3.connect(str(isolate_history_db))
        rows = conn.execute("SELECT COUNT(*) FROM aigc_history").fetchone()
        conn.close()
        assert rows[0] == MAX_IMAGES

    def test_batch_floors_at_one(self, isolate_history_db):
        with patch.object(
            image_batch,
            "aigc_generate_handler",
            return_value="✅ 生成成功！\n文件: /tmp/x.png",
        ):
            out = image_generate_batch_handler(prompt="x", count=0)
        assert "(1/1 成功)" in out

    def test_failed_generation_still_recorded(self, isolate_history_db):
        with patch.object(
            image_batch,
            "aigc_generate_handler",
            return_value="❌ API rate limit exceeded",
        ):
            out = image_generate_batch_handler(prompt="x", count=2)
        assert "(0/2 成功)" in out
        conn = sqlite3.connect(str(isolate_history_db))
        rows = conn.execute(
            "SELECT success, error FROM aigc_history ORDER BY id"
        ).fetchall()
        conn.close()
        assert all(r[0] == 0 for r in rows)
        assert "API rate limit" in rows[0][1]

    def test_history_list_returns_recent(self, isolate_history_db):
        with patch.object(
            image_batch,
            "aigc_generate_handler",
            return_value="✅ 生成成功！\n文件: /tmp/z.png",
        ):
            image_generate_batch_handler(prompt="abc", count=3)
        listed = image_history_list_handler(limit=10)
        assert "abc" in listed
        # Each row has a unique id
        assert listed.count("✅") == 3

    def test_feedback_invalid_rating(self, isolate_history_db):
        out = image_feedback_handler(image_id=999, rating="awesome")
        assert "❌" in out

    def test_feedback_unknown_id(self, isolate_history_db):
        out = image_feedback_handler(image_id=99999, rating="best")
        assert "未找到" in out

    def test_feedback_records_rating(self, isolate_history_db):
        with patch.object(
            image_batch,
            "aigc_generate_handler",
            return_value="✅ 生成成功！\n文件: /tmp/x.png",
        ):
            image_generate_batch_handler(prompt="seed", count=1)
        # Read back the inserted id
        conn = sqlite3.connect(str(isolate_history_db))
        rid = conn.execute("SELECT id FROM aigc_history").fetchone()[0]
        conn.close()
        out = image_feedback_handler(image_id=rid, rating="best")
        assert "✅" in out
        conn = sqlite3.connect(str(isolate_history_db))
        rating = conn.execute(
            "SELECT rating FROM aigc_history WHERE id = ?", (rid,)
        ).fetchone()[0]
        conn.close()
        assert rating == "best"


# ---- AIGC policy ------------------------------------------------------------

class TestAIGCPolicy:

    def test_aigc_generate_allowed(self):
        guard = _aigc_guard()
        assert guard.check_tool("aigc_generate", ToolCategory.WRITE_ACTION) == Decision.ALLOW

    def test_image_generate_batch_allowed(self):
        guard = _aigc_guard()
        assert (
            guard.check_tool("image_generate_batch", ToolCategory.WRITE_ACTION)
            == Decision.ALLOW
        )

    def test_image_feedback_allowed(self):
        guard = _aigc_guard()
        assert (
            guard.check_tool("image_feedback", ToolCategory.WRITE_ACTION) == Decision.ALLOW
        )

    def test_server_shell_forbidden(self):
        # AIGC pack must not be able to call server_shell at all.
        guard = _aigc_guard()
        assert guard.check_tool("server_shell", ToolCategory.READ_ONLY) == Decision.DENY

    def test_unknown_write_action_denied(self):
        guard = _aigc_guard()
        assert (
            guard.check_tool("delete_user_data", ToolCategory.WRITE_ACTION)
            == Decision.DENY
        )


# ---- pack registration -----------------------------------------------------

class TestAIGCPackRegistration:

    def test_phase4_tools_present(self):
        pack = load_pack("aigc-creator")
        names = [t.name for t in pack.get_tools(runtime=None)]
        for required in (
            "prompt_optimize",
            "image_generate_batch",
            "image_history_list",
            "image_feedback",
            "aigc_generate",
        ):
            assert required in names, f"Tool {required} missing from AIGC pack"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short", "--override-ini=addopts="])
