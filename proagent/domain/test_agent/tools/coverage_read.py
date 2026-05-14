"""coverage_read - Read and parse test coverage reports."""

import logging
import re
import xml.etree.ElementTree as ET
from pathlib import Path

logger = logging.getLogger(__name__)


def coverage_read_handler(path: str = "coverage.xml", **_kwargs) -> str:
    """Read a coverage report and return a structured summary.

    Supports: coverage.xml (pytest-cov), lcov.info, go cover output.

    Args:
        path: Path to coverage report file

    Returns:
        Structured coverage summary with per-file breakdown.
    """
    target = Path(path).expanduser()

    if not target.exists():
        # Try common locations
        for candidate in ["coverage.xml", "coverage/coverage.xml", "htmlcov/coverage.xml",
                          ".coverage", "lcov.info", "coverage/lcov.info"]:
            if Path(candidate).exists():
                target = Path(candidate)
                break
        else:
            return f"❌ Coverage report not found at {path}\nRun tests with coverage first:\n  pytest --cov=src --cov-report=xml"

    suffix = target.suffix.lower()

    if suffix == ".xml" or target.name == "coverage.xml":
        return _parse_cobertura_xml(target)
    elif target.name == "lcov.info" or suffix == ".info":
        return _parse_lcov(target)
    else:
        # Try to read as text
        try:
            content = target.read_text(encoding="utf-8")[:5000]
            return f"# Coverage Report: {target}\n\n```\n{content}\n```"
        except Exception as e:
            return f"❌ Cannot read coverage report: {e}"


def _parse_cobertura_xml(path: Path) -> str:
    """Parse Cobertura XML format (pytest-cov output)."""
    try:
        tree = ET.parse(str(path))
        root = tree.getroot()

        # Overall coverage
        line_rate = float(root.get("line-rate", 0)) * 100
        branch_rate = float(root.get("branch-rate", 0)) * 100

        lines = [f"# Coverage Report: {path}",
                 f"\n## Overall",
                 f"- Line coverage: **{line_rate:.1f}%**",
                 f"- Branch coverage: **{branch_rate:.1f}%**",
                 "\n## Per-File Coverage"]

        # Per-file breakdown
        low_coverage = []
        for pkg in root.findall(".//package"):
            for cls in pkg.findall(".//class"):
                filename = cls.get("filename", "?")
                file_rate = float(cls.get("line-rate", 0)) * 100
                missed = sum(1 for line in cls.findall(".//line") if line.get("hits", "0") == "0")
                total = len(cls.findall(".//line"))

                status = "✅" if file_rate >= 80 else ("⚠️" if file_rate >= 60 else "❌")
                lines.append(f"- {status} `{filename}`: {file_rate:.0f}% ({total - missed}/{total} lines)")

                if file_rate < 80:
                    low_coverage.append((filename, file_rate, missed))

        if low_coverage:
            lines.append("\n## Low Coverage Files (< 80%)")
            for fname, rate, missed in sorted(low_coverage, key=lambda x: x[1]):
                lines.append(f"- `{fname}`: {rate:.0f}% ({missed} uncovered lines)")

        return "\n".join(lines)

    except ET.ParseError as e:
        return f"❌ Cannot parse coverage XML: {e}"
    except Exception as e:
        return f"❌ Coverage read error: {e}"


def _parse_lcov(path: Path) -> str:
    """Parse LCOV format (go cover, jest --coverage)."""
    try:
        content = path.read_text(encoding="utf-8")
        files = {}
        current_file = None
        total_lines = 0
        covered_lines = 0

        for line in content.splitlines():
            if line.startswith("SF:"):
                current_file = line[3:]
                files[current_file] = {"total": 0, "covered": 0}
            elif line.startswith("DA:") and current_file:
                _, hits = line[3:].split(",", 1)
                files[current_file]["total"] += 1
                total_lines += 1
                if int(hits.split(",")[0]) > 0:
                    files[current_file]["covered"] += 1
                    covered_lines += 1

        overall = (covered_lines / total_lines * 100) if total_lines > 0 else 0
        lines = [f"# Coverage Report: {path}",
                 f"\n## Overall: {overall:.1f}% ({covered_lines}/{total_lines} lines)"]

        for fname, data in sorted(files.items()):
            rate = (data["covered"] / data["total"] * 100) if data["total"] > 0 else 0
            status = "✅" if rate >= 80 else ("⚠️" if rate >= 60 else "❌")
            lines.append(f"- {status} `{fname}`: {rate:.0f}%")

        return "\n".join(lines)

    except Exception as e:
        return f"❌ LCOV parse error: {e}"
