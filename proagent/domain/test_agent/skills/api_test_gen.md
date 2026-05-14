# API Test Generation

## When to use
- User asks to test REST/gRPC API endpoints
- OpenAPI spec is available
- Need to verify error handling, auth, rate limiting

## Inputs required
- api_spec: Path to OpenAPI/Swagger spec (openapi.yaml / swagger.json)
- base_url: API base URL (e.g. http://localhost:8080)
- auth_token: (optional) Bearer token or API key
- framework: pytest+httpx (default) | postman | schemathesis

## Procedure

### Step 1: Read API spec
```
code_read(path="{api_spec}")
```

### Step 2: Identify test scenarios per endpoint

For each endpoint, generate:
- **Happy path**: valid request → expected response code + body schema
- **Auth tests**: missing token → 401, invalid token → 401/403
- **Validation tests**: missing required fields → 422, invalid types → 422
- **Business logic**: unauthorized resource → 403, not found → 404
- **Rate limiting**: exceed quota → 429

### Step 3: Generate pytest+httpx test code

Template:
```python
import pytest
import httpx

BASE_URL = "{base_url}"
HEADERS = {"Authorization": "Bearer {token}"}

class TestEndpointName:
    def test_success(self):
        response = httpx.post(f"{BASE_URL}/v1/endpoint", 
                              json={"valid": "payload"},
                              headers=HEADERS)
        assert response.status_code == 200
        data = response.json()
        assert "expected_field" in data
        assert data["expected_field"] == expected_value
    
    def test_unauthorized(self):
        response = httpx.post(f"{BASE_URL}/v1/endpoint",
                              json={"valid": "payload"})
        assert response.status_code == 401
        assert response.json()["error"] == "UNAUTHORIZED"
```

### Step 4: Execute API tests
```
test_execute(command="pytest {test_file} -v", cwd="{project_root}")
```

## Stop conditions
- All P0 endpoints tested
- User confirms coverage is sufficient

## Output format
```
## API Tests: {api_name}

Endpoints tested: {n}
Test cases: {total} ({passed} passed, {failed} failed)

### Coverage by Endpoint
- GET /v1/models: ✅ 3/3 cases
- POST /v1/chat/completions: ❌ 2/4 cases (streaming test failing)

### Failures
{failure_details}
```

## Anti-hallucination checklist
- [ ] Tests use actual HTTP calls (not mocked responses)
- [ ] Status codes are exact (200, not 2xx)
- [ ] Response body assertions check specific fields
- [ ] Auth tests verify the actual error response format
- [ ] All tests executed and results verified
