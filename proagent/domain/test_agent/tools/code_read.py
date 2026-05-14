"""code_read - Read source code, test files, OpenAPI specs, PR diffs.

Read-only tool. Supports single files, directories (recursive), and git diffs.
"""

import logging
import os
import subprocess
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

MAX_FILE_SIZE_KB = 512
MAX_DIR_FILES = 50


def code_read_handler(
    path: str,
    recursive: bool = False,
    pattern: str = "",
    git_diff: bool = False,
    **_kwargs,
) -> str:
    """Read source code or directory contents.

    Args:
        path: File path, directory path, or 'git:diff' for PR diff
        recursive: If True and path is a directory, read all matching files
        pattern: File pattern filter (e.g. '*.py', '*.ts')
        git_diff: If True, return git diff instead of file content

    Returns:
        File content or directory listing as string.
    """
    if git_diff:
        return _read_git_diff(path)

    target = Path(path).expanduser()

    if not target.exists():
        return f"❌ Path not found: {path}"

    if target.is_file():
        return _read_file(target)

    if target.is_dir():
        return _read_directory(target, recursive=recursive, pattern=pattern)

    return f"❌ Unknown path type: {path}"


def _read_file(path: Path) -> str:
    """Read a single file with size limit."""
    size_kb = path.stat().st_size / 1024
    if size_kb > MAX_FILE_SIZE_KB:
        return f"⚠️ File too large ({size_kb:.0f}KB > {MAX_FILE_SIZE_KB}KB): {path}\nUse pattern filter to read specific sections."

    try:
        content = path.read_text(encoding="utf-8", errors="replace")
        lines = content.count("\n")
        return f"# {path} ({lines} lines)\n\n```\n{content}\n```"
    except Exception as e:
        return f"❌ Cannot read {path}: {e}"


def _read_directory(path: Path, recursive: bool = False, pattern: str = "") -> str:
    """Read directory contents."""
    if not pattern:
        # Default: common source code extensions
        extensions = {".py", ".ts", ".js", ".go", ".java", ".rs", ".yaml", ".yml", ".json", ".md"}
    else:
        extensions = None

    files = []
    if recursive:
        glob_pattern = f"**/{pattern}" if pattern else "**/*"
        candidates = list(path.glob(glob_pattern))
    else:
        glob_pattern = pattern if pattern else "*"
        candidates = list(path.glob(glob_pattern))

    for f in sorted(candidates):
        if not f.is_file():
            continue
        if extensions and f.suffix not in extensions:
            continue
        # Skip hidden files and common non-source dirs
        if any(part.startswith(".") or part in ("node_modules", "__pycache__", ".git", "dist", "build")
               for part in f.parts):
            continue
        files.append(f)

    if not files:
        return f"No matching files found in {path}"

    if len(files) > MAX_DIR_FILES:
        # Show listing only
        listing = "\n".join(f"  {f.relative_to(path)}" for f in files[:MAX_DIR_FILES])
        return f"# Directory: {path} ({len(files)} files, showing first {MAX_DIR_FILES})\n\n{listing}\n\nUse specific file path or pattern to read content."

    # Read all files
    parts = [f"# Directory: {path} ({len(files)} files)\n"]
    for f in files:
        rel = f.relative_to(path)
        try:
            content = f.read_text(encoding="utf-8", errors="replace")
            parts.append(f"\n## {rel}\n```\n{content}\n```")
        except Exception as e:
            parts.append(f"\n## {rel}\n❌ Cannot read: {e}")

    return "\n".join(parts)


def _read_git_diff(base: str = "HEAD") -> str:
    """Read git diff for current changes."""
    try:
        result = subprocess.run(
            ["git", "diff", base],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode != 0:
            return f"❌ git diff failed: {result.stderr}"
        if not result.stdout.strip():
            return "No changes detected (git diff is empty)"
        return f"# Git Diff ({base})\n\n```diff\n{result.stdout}\n```"
    except FileNotFoundError:
        return "❌ git not found in PATH"
    except subprocess.TimeoutExpired:
        return "❌ git diff timed out"
