# UI Test Execution (Playwright)

## When to use
- User asks to test web UI flows
- Need to verify user journeys (login, create, update, delete)
- Acceptance testing of a deployed application

## Inputs required
- url: Target application URL
- flow: Description of user flow to test
- credentials: (optional) username/password for login

## Procedure

### Step 1: Check Playwright is available
```
test_execute(command="npx playwright --version", cwd="{project_root}")
```

### Step 2: Generate Playwright test script

Use accessibility-first approach (not CSS selectors):
```typescript
import { test, expect } from '@playwright/test';

test('{flow_description}', async ({ page }) => {
  // Navigate
  await page.goto('{url}');
  
  // Use accessibility roles, not CSS selectors
  await page.getByRole('button', { name: 'Login' }).click();
  await page.getByLabel('Email').fill('{email}');
  await page.getByLabel('Password').fill('{password}');
  await page.getByRole('button', { name: 'Sign in' }).click();
  
  // Verify with accessibility snapshot, not visual
  await expect(page.getByRole('heading', { name: 'Dashboard' })).toBeVisible();
  
  // Screenshot as evidence (not for assertion)
  await page.screenshot({ path: 'screenshots/login-success.png' });
});
```

### Step 3: Execute Playwright tests
```
test_execute(command="npx playwright test {test_file} --reporter=list", cwd="{project_root}")
```

### Step 4: Collect evidence
- Screenshots saved to `screenshots/`
- Traces saved to `test-results/`
- Console errors captured

## Stop conditions
- All steps in the flow verified
- Screenshots collected as evidence

## Output format
```
## UI Test: {flow_name}

Status: ✅ PASSED / ❌ FAILED
Steps: {n_steps} ({n_passed} passed)

### Evidence
- Screenshot: screenshots/{name}.png
- Trace: test-results/{name}/trace.zip

### Failures
{failure_details_with_screenshot_reference}
```

## Anti-hallucination rules
- NEVER say "page looks correct" without screenshot evidence
- Use accessibility snapshot for assertions, not visual inspection
- All assertions must be Playwright `expect()` calls that actually ran
- Screenshots are evidence for humans, not for Agent judgment
- If a step fails, report the actual error message from Playwright
