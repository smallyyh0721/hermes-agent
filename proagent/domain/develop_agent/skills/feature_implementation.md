# Feature Implementation

## When to use
- Implementing a scoped feature from a validated requirement.

## Procedure
1. Write or update tests first.
2. Implement the smallest production change that satisfies the tests.
3. Run focused tests, then relevant regression tests.
4. Update docs and work item status.
5. Hand off to Test Agent.

## Stop conditions
- Requirement is unclear.
- The change needs secrets, destructive git operations, or production writes.
