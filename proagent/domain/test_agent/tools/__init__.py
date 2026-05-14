"""Test Agent Tools - Self-registering tool set."""

from proagent.core.agent import ToolDef
from proagent.domain.test_agent.tools.code_read import code_read_handler
from proagent.domain.test_agent.tools.test_execute import test_execute_handler
from proagent.domain.test_agent.tools.coverage_read import coverage_read_handler
from proagent.domain.test_agent.tools.report_generate import report_generate_handler


def get_tools(runtime) -> list:
    """Return all tools for the Test Agent domain."""
    return [
        ToolDef(
            name="code_read",
            description=(
                "Read source code files, directories, OpenAPI specs, or git diffs. "
                "Use to understand what needs to be tested before generating test cases. "
                "Set recursive=True to read all files in a directory."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "File path, directory path, or 'git:diff' for current changes",
                    },
                    "recursive": {
                        "type": "boolean",
                        "description": "Read all files in directory recursively",
                        "default": False,
                    },
                    "pattern": {
                        "type": "string",
                        "description": "File pattern filter, e.g. '*.py', '*.ts'",
                        "default": "",
                    },
                    "git_diff": {
                        "type": "boolean",
                        "description": "If True, return git diff instead of file content",
                        "default": False,
                    },
                },
                "required": ["path"],
            },
            handler=code_read_handler,
        ),
        ToolDef(
            name="test_execute",
            description=(
                "Execute test commands and collect results. "
                "Supports pytest, jest, vitest, go test, cargo test, playwright, k6. "
                "Returns structured results with pass/fail counts and failure details. "
                "IMPORTANT: Only trust actual execution results, not predictions."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "Test command to run, e.g. 'pytest tests/ -v --cov=src'",
                    },
                    "cwd": {
                        "type": "string",
                        "description": "Working directory for the command",
                        "default": ".",
                    },
                    "timeout": {
                        "type": "integer",
                        "description": "Maximum execution time in seconds (default 300)",
                        "default": 300,
                    },
                },
                "required": ["command"],
            },
            handler=test_execute_handler,
        ),
        ToolDef(
            name="coverage_read",
            description=(
                "Read and parse test coverage reports. "
                "Supports coverage.xml (pytest-cov), lcov.info (jest/go). "
                "Returns per-file coverage breakdown and identifies low-coverage files."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path to coverage report file (default: coverage.xml)",
                        "default": "coverage.xml",
                    },
                },
                "required": [],
            },
            handler=coverage_read_handler,
        ),
        ToolDef(
            name="report_generate",
            description=(
                "Generate a test report in markdown or HTML format. "
                "Call after test execution to create a human-readable summary."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "results": {
                        "type": "string",
                        "description": "Test results as JSON string or raw output text",
                    },
                    "format": {
                        "type": "string",
                        "description": "Output format: 'markdown' or 'html'",
                        "default": "markdown",
                    },
                    "output": {
                        "type": "string",
                        "description": "Output file path",
                        "default": "test-report.md",
                    },
                    "project": {
                        "type": "string",
                        "description": "Project name for the report header",
                        "default": "",
                    },
                },
                "required": ["results"],
            },
            handler=report_generate_handler,
        ),
    ]
