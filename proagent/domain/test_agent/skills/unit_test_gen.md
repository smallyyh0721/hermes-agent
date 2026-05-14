# Unit Test Generation

## When to use
- User asks to generate unit tests for a function/module
- PR diff shows new code without tests
- Coverage report shows low-coverage files

## Inputs required
- source_path: Path to source file(s)
- language: python | typescript | go | java | rust
- framework: pytest | jest | vitest | go test | junit | cargo test
- existing_tests_path: (optional) path to existing tests for style reference

## Procedure

### Step 1: Read source code
```
code_read(path="{source_path}")
```

### Step 2: Read existing tests for style reference (if available)
```
code_read(path="{existing_tests_path}", recursive=True, pattern="test_*.py")
```

### Step 3: Analyze and propose test cases (present to user before generating code)

For each function/method, identify:
- **Happy path**: normal inputs → expected output
- **Error paths**: invalid inputs, exceptions, edge cases
- **Boundary values**: 0, -1, None, empty string, max value
- **External dependencies**: what needs to be mocked

Present the list to user:
```
Proposed test cases for {module}:
1. [P0] test_{func}_normal_case - {description}
2. [P0] test_{func}_empty_input - {description}
3. [P1] test_{func}_invalid_type_raises - {description}
...
Confirm to generate code? [Y/n]
```

### Step 4: Generate test code (after user confirmation)

Rules:
- Follow the style of existing tests
- Use meaningful test names: `test_{function}_{scenario}`
- Include docstring explaining what is being tested
- Use precise assertions (not `assert result is not None`)
- Mock external dependencies (DB, HTTP, filesystem)
- One assertion per test (or closely related assertions)

### Step 5: Execute tests to verify they run
```
test_execute(command="{test_command} {test_file} -v", cwd="{project_root}")
```

### Step 6: Read coverage to check improvement
```
coverage_read(path="coverage.xml")
```

## Stop conditions
- All proposed test cases generated and passing
- User rejects remaining cases
- Coverage target reached

## Output format
```
## Unit Tests Generated: {module}

Generated {n} test cases in {test_file}:
- {n_passed} passing ✅
- {n_failed} failing ❌ (need investigation)

Coverage: {before}% → {after}%

### Failing Tests
{failure_analysis}

### Next Steps
- Review generated tests in {test_file}
- Run: {test_command}
```

## Anti-hallucination checklist
- [ ] All assertions use specific expected values
- [ ] No `assert result is not None` style assertions
- [ ] Mocks are realistic (not mocking the function under test)
- [ ] Tests actually run (verified by test_execute)
- [ ] Coverage numbers come from coverage_read, not estimates
