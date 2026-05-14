# Test Failure Diagnosis

## When to use
- Tests are failing and root cause is unclear
- CI pipeline is red
- User asks "why is this test failing?"

## Inputs required
- test_output: Failed test output (stdout/stderr)
- source_path: (optional) path to source code being tested
- recent_changes: (optional) recent git diff

## Procedure

### Step 1: Parse the failure
Identify from test output:
- Which test(s) failed
- Error type (AssertionError, ImportError, TimeoutError, etc.)
- Error message and stack trace
- Line number in test and source

### Step 2: Categorize the failure

| Category | Symptoms | Action |
|----------|---------|--------|
| **Test bug** | Assertion wrong, wrong expected value | Fix the test |
| **Code bug** | Logic error in source | Fix the source (report to developer) |
| **Environment** | Import error, missing dependency | Fix environment |
| **Flaky test** | Passes sometimes, fails sometimes | Add retry or fix timing |
| **Data dependency** | Relies on specific DB state | Add fixtures/mocks |
| **Config error** | Wrong URL, missing env var | Fix configuration |

### Step 3: Read relevant source code (if needed)
```
code_read(path="{source_path}")
```

### Step 4: Check recent changes (if available)
```
code_read(path=".", git_diff=True)
```

### Step 5: Generate diagnosis report

Structure:
```
## Failure Diagnosis: {test_name}

### Error
{error_type}: {error_message}
Location: {file}:{line}

### Root Cause Analysis
Category: {category}
Explanation: {explanation}

### Evidence
{relevant_code_snippet}

### Fix Suggestion
{specific_fix_with_code_example}

### Risk Assessment
- Is this a regression? {yes/no/unknown}
- Affected functionality: {description}
- Blocking? {yes/no}
```

## Stop conditions
- Root cause identified with evidence
- Fix suggestion provided
- If cannot determine root cause, clearly state what additional info is needed

## Anti-hallucination rules
- Root cause must be supported by actual error output
- Do NOT say "probably" or "might be" without evidence
- If uncertain, say "possible causes" and list them with evidence for each
- Fix suggestions must reference actual code, not generic advice
- Never say "the test is correct" without verifying the assertion logic
