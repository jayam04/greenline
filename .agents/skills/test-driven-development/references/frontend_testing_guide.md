# Frontend Testing Guide: Component & E2E Testing

## TypeScript Verification

Always run TypeScript compilation check before completing any frontend modification:

```bash
cd frontend && npx tsc --noEmit
```

## Component Testing (Vitest & Testing Library)

```tsx
import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
// import HoldingsTable from '@/components/HoldingsTable';

describe('Holdings Table', () => {
  it('renders merged total cost and current value correctly', () => {
    // render(<HoldingsTable holdings={mockHoldings} />);
    // expect(screen.getByText('Net P&L')).toBeInTheDocument();
  });
});
```

## Playwright E2E Testing Pattern

```typescript
import { test, expect } from '@playwright/test';

test.describe('Greenline Core Workflows', () => {
  test('user can log trade with fees and view updated holdings', async ({ page }) => {
    await page.goto('http://localhost:3000/holdings');
    await expect(page.locator('h1')).toContainText('Holdings');
  });
});
```
