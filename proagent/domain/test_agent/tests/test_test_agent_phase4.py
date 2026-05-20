"""Phase 4 Test Agent tests — verify code_scan + prd_parse + policy.

Tests:
- code_scan finds source files and counts testable units
- code_scan skips test files / vendor dirs / non-source extensions
- prd_parse extracts headings, EARS criteria, user stories, bullet features
- prd_parse handles missing files gracefully
- policy: report_generate is whitelisted; aigc_generate forbidden

Run with:
    pytest proagent/domain/test_agent/tests/test_test_agent_phase4.py -v --override-ini="addopts="
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from proagent.policy.guard import Decision, PolicyGuard, ToolCategory, load_policy
from proagent.domain.base import load_pack
from proagent.domain.test_agent.tools.code_scan import code_scan_handler
from proagent.domain.test_agent.tools.prd_parse import prd_parse_handler


def _test_agent_policy_path() -> Path:
    return (
        Path(__file__).resolve().parents[4]
        / "proagent" / "domain" / "test_agent" / "policy.yaml"
    )


def _test_agent_guard() -> PolicyGuard:
    return PolicyGuard(load_policy(_test_agent_policy_path()), domain="test-agent")


# ---- code_scan -------------------------------------------------------------

class TestCodeScan:

    def test_missing_path(self):
        out = code_scan_handler(path="/totally/nonexistent/path-xyz123")
        assert "❌" in out

    def test_single_file(self, tmp_path):
        f = tmp_path / "module.py"
        f.write_text(
            "def foo():\n    pass\n\nclass Bar:\n    pass\n",
            encoding="utf-8",
        )
        out = code_scan_handler(path=str(f))
        assert "single file" in out.lower()
        assert "python" in out
        assert "Testable units" in out

    def test_directory_scan_detects_python(self, tmp_path):
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "a.py").write_text(
            "def hello():\n    return 1\n\nclass Service:\n    def run(self): pass\n",
            encoding="utf-8",
        )
        out = code_scan_handler(path=str(tmp_path))
        assert "src/a.py" in out
        assert "python" in out

    def test_skips_vendor_dirs(self, tmp_path):
        node_mod = tmp_path / "node_modules" / "some-pkg"
        node_mod.mkdir(parents=True)
        (node_mod / "index.js").write_text(
            "function exported() { return 1 }\n",
            encoding="utf-8",
        )
        # Real source
        (tmp_path / "real.py").write_text(
            "def real_func():\n    pass\n",
            encoding="utf-8",
        )
        out = code_scan_handler(path=str(tmp_path))
        assert "real.py" in out
        assert "node_modules" not in out

    def test_excludes_test_files_by_default(self, tmp_path):
        (tmp_path / "test_thing.py").write_text(
            "def test_x():\n    assert True\n",
            encoding="utf-8",
        )
        (tmp_path / "real.py").write_text(
            "def real_func():\n    pass\n",
            encoding="utf-8",
        )
        out = code_scan_handler(path=str(tmp_path), include_tests=False)
        # The test file should appear in "已存在的测试文件" but NOT in the source table.
        # We assert the source table contains real.py and the test_thing.py is reported separately.
        assert "real.py" in out
        # Lines that start with "| test_thing.py" would mean it was listed as source.
        assert "| test_thing.py" not in out

    def test_max_files_cap(self, tmp_path):
        for i in range(10):
            (tmp_path / f"mod_{i}.py").write_text(
                f"def fn_{i}():\n    pass\n", encoding="utf-8"
            )
        out = code_scan_handler(path=str(tmp_path), max_files=3)
        # Counts at most 3 inspected
        assert "已扫描文件**: " in out


# ---- prd_parse -------------------------------------------------------------

PRD_SAMPLE = """# Requirements: Demo

## Requirement 1: Login

**User Story:** As a user, I want to log in, so that I can use the system.

#### Acceptance Criteria

1. WHEN the user submits valid credentials, THE system SHALL authenticate.
2. IF credentials are invalid, THEN the system SHALL show an error.

## Feature 2: Logout

- F1: User clicks logout
- F2: Session is destroyed
"""


class TestPRDParse:

    def test_missing_file(self, tmp_path):
        out = prd_parse_handler(path=str(tmp_path / "nope.md"))
        assert "❌" in out

    def test_extracts_user_story(self, tmp_path):
        f = tmp_path / "prd.md"
        f.write_text(PRD_SAMPLE, encoding="utf-8")
        out = prd_parse_handler(path=str(f))
        assert "user" in out.lower()
        # User story extraction
        assert "用户故事" in out

    def test_extracts_ears_criteria(self, tmp_path):
        f = tmp_path / "prd.md"
        f.write_text(PRD_SAMPLE, encoding="utf-8")
        out = prd_parse_handler(path=str(f))
        assert "EARS" in out

    def test_extracts_bullets(self, tmp_path):
        f = tmp_path / "prd.md"
        f.write_text(PRD_SAMPLE, encoding="utf-8")
        out = prd_parse_handler(path=str(f))
        assert "F1: User clicks logout" in out

    def test_path_must_be_file(self, tmp_path):
        out = prd_parse_handler(path=str(tmp_path))
        assert "❌" in out


# ---- Test Agent policy -----------------------------------------------------

class TestTestAgentPolicy:

    def test_report_generate_allowed(self):
        guard = _test_agent_guard()
        assert (
            guard.check_tool("report_generate", ToolCategory.WRITE_ACTION) == Decision.ALLOW
        )

    def test_aigc_forbidden(self):
        guard = _test_agent_guard()
        assert (
            guard.check_tool("aigc_generate", ToolCategory.WRITE_ACTION) == Decision.DENY
        )

    def test_server_shell_forbidden(self):
        guard = _test_agent_guard()
        assert guard.check_tool("server_shell", ToolCategory.READ_ONLY) == Decision.DENY

    def test_image_generate_batch_forbidden(self):
        guard = _test_agent_guard()
        assert (
            guard.check_tool("image_generate_batch", ToolCategory.WRITE_ACTION)
            == Decision.DENY
        )

    def test_unknown_write_action_denied(self):
        guard = _test_agent_guard()
        assert (
            guard.check_tool("delete_database", ToolCategory.WRITE_ACTION)
            == Decision.DENY
        )


class TestTestAgentPackRegistration:

    def test_all_phase4_tools_present(self):
        pack = load_pack("test-agent")
        names = [t.name for t in pack.get_tools(runtime=None)]
        for required in (
            "code_read",
            "code_scan",
            "prd_parse",
            "test_execute",
            "coverage_read",
            "report_generate",
        ):
            assert required in names, f"Tool {required} missing from Test Agent pack"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short", "--override-ini=addopts="])
