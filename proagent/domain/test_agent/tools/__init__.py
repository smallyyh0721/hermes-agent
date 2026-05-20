"""Test Agent Tools - Self-registering tool set."""

from proagent.core.agent import ToolDef
from proagent.domain.test_agent.tools.code_read import code_read_handler
from proagent.domain.test_agent.tools.test_execute import test_execute_handler
from proagent.domain.test_agent.tools.coverage_read import coverage_read_handler
from proagent.domain.test_agent.tools.report_generate import report_generate_handler
from proagent.domain.test_agent.tools.code_scan import code_scan_handler
from proagent.domain.test_agent.tools.prd_parse import prd_parse_handler


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
            category="read_only",
        ),
        ToolDef(
            name="code_scan",
            description=(
                "Scan a project directory and produce a testability matrix. "
                "Returns a list of source files with their language, line count, and "
                "number of testable units (public functions/classes). "
                "Sorted by testable_units descending so the agent knows where to focus first. "
                "Use BEFORE generating tests to understand the project surface."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Project root path to scan (default '.')",
                        "default": ".",
                    },
                    "max_files": {
                        "type": "integer",
                        "description": "Cap on number of files to inspect (default 200)",
                        "default": 200,
                    },
                    "include_tests": {
                        "type": "boolean",
                        "description": "Include existing test files in the source list",
                        "default": False,
                    },
                },
                "required": [],
            },
            handler=code_scan_handler,
            category="read_only",
        ),
        ToolDef(
            name="prd_parse",
            description=(
                "Parse a PRD/markdown product manual and extract testable requirements: "
                "section headings, EARS-style acceptance criteria (WHEN/IF/SHALL), user stories, "
                "and bulleted feature lists. Use to generate tests grounded in product requirements."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path to the markdown PRD file",
                    },
                    "max_items": {
                        "type": "integer",
                        "description": "Cap on extracted items per category (default 50)",
                        "default": 50,
                    },
                },
                "required": ["path"],
            },
            handler=prd_parse_handler,
            category="read_only",
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
            category="read_only",
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
            category="read_only",
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
            category="write_action",
        ),
    ]
