# Test Agent Knowledge Index

## Test Commands by Language

### Python (pytest)
```bash
# Run all tests with coverage
pytest tests/ -v --cov=src --cov-report=xml --cov-report=term

# Run specific test file
pytest tests/test_billing.py -v

# Run tests matching pattern
pytest tests/ -k "test_calculate" -v

# Run with JUnit XML output (for CI)
pytest tests/ --junitxml=junit.xml
```

### TypeScript/JavaScript (jest/vitest)
```bash
# Jest
npx jest --coverage --coverageReporters=lcov

# Vitest
npx vitest run --coverage

# Specific file
npx jest tests/billing.test.ts
```

### Go
```bash
# All tests with coverage
go test ./... -cover -coverprofile=coverage.out

# Specific package
go test ./billing/... -v

# Convert to lcov
go tool cover -html=coverage.out -o coverage.html
```

### Playwright (UI tests)
```bash
# Run all UI tests
npx playwright test

# Run specific test file
npx playwright test tests/ui/login.spec.ts

# Run with trace (for debugging)
npx playwright test --trace on

# Show report
npx playwright show-report
```

### k6 (performance tests)
```bash
# Run performance test
k6 run tests/perf/load-test.js

# With output
k6 run --out json=results.json tests/perf/load-test.js
```

## Test File Conventions

| Language | Test file pattern | Test function pattern |
|----------|------------------|----------------------|
| Python | `test_*.py` or `*_test.py` | `def test_*():` |
| TypeScript | `*.test.ts` or `*.spec.ts` | `it('...')` or `test('...')` |
| Go | `*_test.go` | `func Test*(t *testing.T)` |
| Java | `*Test.java` | `@Test void test*()` |
| Rust | same file | `#[test] fn test_*()` |

## Good vs Bad Assertions

### Python (pytest)
```python
# ❌ BAD - meaningless
assert result is not None
assert len(result) > 0

# ✅ GOOD - specific
assert result == {"status": "ok", "tokens": 100}
assert response.status_code == 200
assert "error_code" not in response.json()
assert billing.amount == Decimal("1.50")
```

### TypeScript (jest)
```typescript
// ❌ BAD
expect(result).toBeTruthy()
expect(result).toBeDefined()

// ✅ GOOD
expect(result.status).toBe(200)
expect(result.data.tokens).toBe(100)
expect(result.error).toBeUndefined()
```

## Mock Patterns

### Python - mock external HTTP
```python
from unittest.mock import patch, MagicMock

@patch('src.billing.http_client.post')
def test_billing_api(mock_post):
    mock_post.return_value = MagicMock(
        status_code=200,
        json=lambda: {"amount": 1.50}
    )
    result = billing.calculate(tokens=100)
    assert result.amount == 1.50
```

### Python - mock database
```python
@pytest.fixture
def mock_db(monkeypatch):
    db = MagicMock()
    db.query.return_value = [{"id": 1, "tokens": 100}]
    monkeypatch.setattr("src.billing.get_db", lambda: db)
    return db
```

## Coverage Targets

| Module type | Minimum coverage |
|-------------|-----------------|
| Core business logic (billing, auth) | 90% |
| API handlers | 80% |
| Utilities | 70% |
| Configuration | 60% |

## Anti-Hallucination Rules

1. **Execute before reporting**: Never report test results without running `test_execute`
2. **Evidence required**: Every pass/fail claim needs actual command output
3. **No predictions**: Don't say "this test should pass" — run it and report what happened
4. **Exact values**: Use specific expected values in assertions, not generic checks
5. **Mutation test**: If coverage looks suspiciously high, suggest running mutation tests
6. **Human confirmation**: Billing/security/auth test results require human sign-off
