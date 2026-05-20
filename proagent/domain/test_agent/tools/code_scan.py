"""code_scan - Scan a project directory for testable modules.

Recursively walks the project tree and identifies:
- Python modules (.py files with functions/classes)
- TypeScript/JavaScript modules (.ts/.tsx/.js/.jsx)
- Go packages (.go)
- Existing test files (so we don't suggest re-testing)

Returns a structured matrix the test agent can use to decide what to test.
"""

import logging
import re
from pathlib import Path
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

# File extensions we consider "testable source"
SOURCE_EXTENSIONS = {
    ".py": "python",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".js": "javascript",
    ".jsx": "javascript",
    ".go": "go",
    ".rs": "rust",
    ".java": "java",
}

# Patterns identifying existing test files (skip these from "needs testing")
TEST_FILE_PATTERNS = [
    re.compile(r"(^|/|\\)test_[^/\\]+\.py$"),
    re.compile(r"(^|/|\\)[^/\\]+_test\.go$"),
    re.compile(r"\.test\.[jt]sx?$"),
    re.compile(r"\.spec\.[jt]sx?$"),
    re.compile(r"(^|/|\\)tests?(/|\\)"),
]

# Directories to always skip
SKIP_DIRS = {
    "node_modules", "__pycache__", ".git", ".venv", "venv", "dist", "build",
    ".next", ".cache", "target", "vendor", ".pytest_cache", ".coverage",
    "site-packages", "egg-info",
}

# Heuristic patterns to detect functions/classes for testability count
PY_FUNC_RE = re.compile(r"^\s*(?:async\s+)?def\s+([a-zA-Z_][\w]*)\s*\(", re.MULTILINE)
PY_CLASS_RE = re.compile(r"^\s*class\s+([A-Z][\w]*)\s*[\(:]", re.MULTILINE)
JS_FUNC_RE = re.compile(r"^\s*(?:export\s+)?(?:async\s+)?function\s+([a-zA-Z_$][\w$]*)\s*\(", re.MULTILINE)
JS_ARROW_RE = re.compile(r"^\s*(?:export\s+)?const\s+([a-zA-Z_$][\w$]*)\s*=\s*(?:async\s+)?\(", re.MULTILINE)
GO_FUNC_RE = re.compile(r"^func\s+(?:\([^)]*\)\s+)?([A-Z][\w]*)\s*\(", re.MULTILINE)


def _is_test_file(rel_path: str) -> bool:
    norm = rel_path.replace("\\", "/")
    return any(p.search(norm) for p in TEST_FILE_PATTERNS)


def _count_testable_units(content: str, language: str) -> int:
    """Quick heuristic: count public functions + classes."""
    if language == "python":
        funcs = [m for m in PY_FUNC_RE.findall(content) if not m.startswith("_")]
        classes = PY_CLASS_RE.findall(content)
        return len(funcs) + len(classes)
    if language in ("typescript", "javascript"):
        funcs = JS_FUNC_RE.findall(content)
        arrows = JS_ARROW_RE.findall(content)
        return len(funcs) + len(arrows)
    if language == "go":
        return len(GO_FUNC_RE.findall(content))
    return 0


def code_scan_handler(
    path: str = ".",
    max_files: int = 200,
    include_tests: bool = False,
    **_kwargs,
) -> str:
    """Scan a project tree and report testable modules.

    Args:
        path: Root directory to scan
        max_files: Cap on number of files to inspect (default 200)
        include_tests: Include existing test files in the report

    Returns:
        Markdown-formatted scan report.
    """
    root = Path(path).resolve()
    if not root.exists():
        return f"❌ Path does not exist: {root}"
    if root.is_file():
        # Single-file scan
        try:
            content = root.read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            return f"❌ Failed to read file: {e}"
        ext = root.suffix.lower()
        lang = SOURCE_EXTENSIONS.get(ext, "unknown")
        return (
            f"# Scan Result: single file\n\n"
            f"**Path**: {root}\n**Language**: {lang}\n"
            f"**Lines**: {len(content.splitlines())}\n"
            f"**Testable units**: {_count_testable_units(content, lang)}\n"
        )

    source_files: List[Dict[str, Any]] = []
    test_files: List[str] = []
    seen = 0

    for p in root.rglob("*"):
        if seen >= max_files:
            break
        if p.is_dir():
            continue
        # Skip vendored / build directories
        parts = set(p.parts)
        if SKIP_DIRS & parts:
            continue
        ext = p.suffix.lower()
        if ext not in SOURCE_EXTENSIONS:
            continue

        rel = p.relative_to(root).as_posix()
        if _is_test_file(rel):
            test_files.append(rel)
            if not include_tests:
                continue

        try:
            content = p.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        units = _count_testable_units(content, SOURCE_EXTENSIONS[ext])
        if units == 0:
            continue
        source_files.append({
            "path": rel,
            "language": SOURCE_EXTENSIONS[ext],
            "lines": len(content.splitlines()),
            "testable_units": units,
        })
        seen += 1

    # Sort by testable_units descending — biggest targets first
    source_files.sort(key=lambda x: x["testable_units"], reverse=True)

    lines = [
        f"# 代码扫描报告",
        f"**根路径**: {root}",
        f"**已扫描文件**: {seen}",
        f"**已存在测试文件**: {len(test_files)}",
        "",
        "## 待测试模块（按可测试单元数降序）",
        "",
        "| 文件 | 语言 | 行数 | 可测试单元 |",
        "|------|------|------|------------|",
    ]
    for f in source_files[:50]:  # cap report at 50 entries
        lines.append(
            f"| {f['path']} | {f['language']} | {f['lines']} | {f['testable_units']} |"
        )
    if len(source_files) > 50:
        lines.append(f"\n*(还有 {len(source_files) - 50} 个文件未列出)*")

    if test_files:
        lines.append("")
        lines.append("## 已存在的测试文件")
        for t in test_files[:30]:
            lines.append(f"- {t}")

    return "\n".join(lines)
