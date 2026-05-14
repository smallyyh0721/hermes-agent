"""test_execute - Execute tests and collect results.

Supports: pytest, jest/vitest, go test, cargo test, playwright, k6/locust.
All execution is local (no SSH). Results include stdout, exit code, and parsed summary.
"""

import json
import logging
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Supported test runners and their result parsers
RUNNERS = {
    "pytest": {"detect": ["pytest", "python -m pytest"], "result_format": "pytest"},
    "jest": {"detect": ["npx jest", "npm test"], "result_format": "jest"},
    "vitest": {"detect": ["npx vitest", "vitest"], "result_format": "vitest"},
    "go": {"detect": ["go test"], "result_format": "go"},
    "cargo": {"detect": ["cargo test"], "result_format": "cargo"},
    "playwright": {"detect": ["npx playwright test", "playwright test"], "result_format": "playwright"},
    "k6": {"detect": ["k6 run"], "result_format": "k6"},
}


def test_execute_handler(
    command: str,
    cwd: str = ".",
    timeout: int = 300,
    env_vars: dict = None,
    **_kwargs,
) -> str:
    """Execute a test command and return structured results.

    Args:
        command: Test command to run (e.g. 'pytest tests/ -v --cov=src')
        cwd: Working directory for the command
        timeout: Maximum execution time in seconds (default 300s = 5min)
        env_vars: Additional environment variables

    Returns:
        Structured test results with pass/fail counts and failure details.
    """
    work_dir = Path(cwd).expanduser().resolve()
    if not work_dir.exists():
        return f"❌ Working directory not found: {cwd}"

    # Build environment
    env = os.environ.copy()
    if env_vars:
        env.update(env_vars)

    logger.info("Executing test: %s (cwd=%s)", command, work_dir)

    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(work_dir),
            env=env,
        )

        output = result.stdout
        if result.stderr:
            output += "\n[stderr]\n" + result.stderr

        # Truncate very long output
        if len(output) > 50000:
            output = output[:25000] + "\n\n... [output truncated, showing last 5000 chars] ...\n\n" + output[-5000:]

        # Parse summary
        summary = _parse_summary(command, output, result.returncode)

        return f"""## Test Execution Result

**Command**: `{command}`
**Exit Code**: {result.returncode} {'✅' if result.returncode == 0 else '❌'}
**Status**: {'PASSED' if result.returncode == 0 else 'FAILED'}

### Summary
{summary}

### Full Output
```
{output}
```"""

    except subprocess.TimeoutExpired:
        return f"❌ Test execution timed out after {timeout}s\nCommand: {command}"
    except Exception as e:
        return f"❌ Test execution error: {e}\nCommand: {command}"


def _parse_summary(command: str, output: str, returncode: int) -> str:
    """Parse test output to extract pass/fail counts."""
    lines = []

    # pytest
    if "pytest" in command or "py.test" in command:
        # Look for: "5 passed, 2 failed, 1 error in 3.45s"
        match = re.search(r"(\d+ passed)?[,\s]*(\d+ failed)?[,\s]*(\d+ error)?[,\s]*(\d+ warning)?.*in ([\d.]+)s", output)
        if match:
            parts = [p for p in match.groups()[:4] if p]
            duration = match.group(5)
            lines.append(f"Results: {', '.join(parts)} in {duration}s")

        # Coverage
        cov_match = re.search(r"TOTAL\s+\d+\s+\d+\s+(\d+)%", output)
        if cov_match:
            lines.append(f"Coverage: {cov_match.group(1)}%")

    # jest/vitest
    elif "jest" in command or "vitest" in command or "npm test" in command:
        match = re.search(r"Tests:\s+(\d+ failed,\s*)?(\d+ passed),\s*(\d+ total)", output)
        if match:
            lines.append(f"Results: {match.group(0)}")

    # go test
    elif "go test" in command:
        if "PASS" in output:
            lines.append("Status: PASS")
        elif "FAIL" in output:
            fails = re.findall(r"--- FAIL: (\S+)", output)
            lines.append(f"Status: FAIL ({len(fails)} failures: {', '.join(fails[:5])})")

    # playwright
    elif "playwright" in command:
        match = re.search(r"(\d+) passed.*?(\d+) failed", output)
        if match:
            lines.append(f"Results: {match.group(1)} passed, {match.group(2)} failed")

    if not lines:
        lines.append(f"Exit code: {returncode} ({'success' if returncode == 0 else 'failure'})")

    return "\n".join(lines)
