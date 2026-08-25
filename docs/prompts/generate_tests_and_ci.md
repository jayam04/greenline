# Master AI Prompt: Comprehensive Test Suite Generation & GitHub CI

Use the prompt below with any AI coding assistant (or Antigravity CLI / AGY) to generate a complete, production-grade test suite covering backend unit/integration tests, frontend component tests, end-to-end (E2E) browser journeys, and a continuous integration (CI) pipeline on GitHub Actions.

---

```markdown
# TASK: Generate Comprehensive Unit, Integration, and E2E Tests with GitHub CI for Greenline

You are an expert Principal QA and Full-Stack Test Automation Engineer. Your objective is to build a complete, resilient, and fully automated testing suite for this entire application, including backend unit/integration tests, frontend component tests, end-to-end (E2E) Playwright browser tests, and configure a multi-stage GitHub Actions CI workflow.

---

## 1. System Context & Architecture Overview

- **Backend**: FastAPI, Python 3.10+, SQLAlchemy 2.0 (asyncio with `aiosqlite`), Pydantic v2, `pyxirr`, `yfinance`.
  - Database: SQLite with WAL mode.
  - Core Business Engines:
    1. `fifo_engine.py`: First-In, First-Out lot allocation, lot depletion on sales, cost-basis tracking, realized P&L.
    2. `xirr_engine.py`: Cashflow IRR calculations per holding, account, and aggregated portfolio.
    3. `snapshot_engine.py`: Daily & annual historical net worth snapshots, cash balance accumulation, securities valuation across holding (`account_id`) and funding (`funding_account_id`) accounts.
    4. `cashflow_engine.py` & `category_service.py`: 3-root category tree (Income, Discretionary, Essential), transfers, multi-account payment splits, legacy payment sign migration.
    5. `price_engine.py`: Real-time and historical price polling, FX rate caching (`EUR`, `USD`, `INR`, `GBP`, `CAD`, `AUD`, `JPY`, `CHF`, `SGD`).
- **Frontend**: Next.js 16 (App Router), React 19, TypeScript, Tailwind CSS v4, Lucide React, Recharts.
  - Key Views:
    1. `/` (Dashboard): Net worth summary, historical net worth chart with date filters, asset allocation donuts, account cards (cash vs stock breakdown), recent transactions.
    2. `/holdings`: Holdings table with merged Total Cost (Avg Cost subtext), Current Value (Price subtext), Realized P&L, Unrealized P&L, Net P&L, FIFO lots expandable sub-rows.
    3. `/cashflow/transactions`: Unified transaction ledger displaying income, expenses, transfers, stock purchases, sales, dividends, with itemized fee and tax lines.
    4. Modals: Add Transaction, Add Cashflow, Account Modal, Privacy Mode toggle.

---

## 2. Test Requirements Specification

### Phase 1: Backend Unit & Integration Tests (`pytest`, `pytest-asyncio`/`anyio`, `pytest-cov`)
1. **FIFO Lot Engine & Realized P&L**:
   - Buy transactions creating distinct lots with cost basis inclusive of fees/taxes.
   - Partial and full sells depleting lots in strict FIFO chronological order.
   - Realized P&L = `(Sale Price * Qty) - (Cost Basis) - (Sale Fees + Taxes)`.
   - Edge cases: Selling entire position to 0 remaining shares, multi-lot single sale split, re-buying after full exit.
2. **Account Balances & Funding Accounts**:
   - Funded stock purchase: `funding_account_id` debits liquid cash while holding `account_id` receives shares.
   - Account total valuation = `cash_balance + securities_value`.
   - Cashflow transfers between accounts preserving zero-sum net worth change.
   - Verify that fees/taxes are not double-subtracted from funding accounts.
3. **Snapshot Engine & Historical Timelines**:
   - Account timeline start date properly includes earliest trade where account acted as either `account_id` or `funding_account_id`.
   - Aggregated multi-account net worth timeline forward-filling without cliffs or artificial drops.
   - Annual net worth delta and savings calculations.
4. **API Endpoints Coverage**:
   - `/api/v1/accounts` (CRUD, balance breakdown).
   - `/api/v1/transactions` (buy, sell, dividend, deposit, withdrawal).
   - `/api/v1/portfolio/summary` & `/api/v1/portfolio/holdings`.
   - `/api/v1/snapshots`.
   - `/api/v1/cashflow/*` (transactions, categories, summaries, search).

### Phase 2: Frontend Unit & Component Tests (`Vitest`, `@testing-library/react`, `@testing-library/jest-dom`)
1. **Holdings Page (`/holdings`)**:
   - Renders merged Total Cost and Current Value columns.
   - Displays Net P&L column correctly computed as Realized + Unrealized.
   - Expands FIFO lot breakdown sub-rows on row click.
   - Currency switching and column sorting.
2. **Cashflow Ledger (`/cashflow/transactions`)**:
   - Displays itemized rows for stock purchases, sales, dividends, investment fees, and taxes.
   - Filter by date range, account, and category.
3. **Dashboard (`/`)**:
   - Renders net worth cards, privacy mode mask toggles (`••••`), and interactive Recharts components.
4. **Add/Edit Modals**:
   - Form validation: non-zero quantities, valid date, required accounts.
   - Dynamic funding account dropdowns when demat account is selected.

### Phase 3: End-to-End (E2E) Browser Tests (`Playwright`)
1. **Journey 1: Account Creation & Cash Funding**:
   - User creates a Bank account and a Demat account.
   - Logs an opening cash deposit into the Bank account.
   - Verifies dashboard accounts card shows correct cash balance.
2. **Journey 2: Stock Purchase & Holdings Reflection**:
   - User executes a stock buy in Demat account funded by Bank account with fees & taxes.
   - Verifies Bank cash balance decreases by total outlay.
   - Verifies Holdings page shows new asset with lot details, merged cost, and valuation.
3. **Journey 3: Stock Sale & Realized P&L**:
   - User sells 50% of the holding.
   - Verifies remaining lot quantity is halved.
   - Verifies Realized P&L and Net P&L update on both Holdings page and Dashboard summary cards.
4. **Journey 4: Cashflow Tracking & Expense Splits**:
   - User logs a splitwise expense and account transfer.
   - Verifies Cashflow transactions list displays categorized items.
5. **Journey 5: Privacy Mode & Navigation**:
   - Toggle privacy mode -> numbers convert to `••••` across dashboard, holdings, and accounts.

### Phase 4: GitHub Actions CI Pipeline (`.github/workflows/ci.yml`)
Configure a GitHub Actions workflow with the following jobs:
1. **Backend CI**:
   - Python setup (3.10 & 3.11).
   - Install dependencies and run `pytest` with coverage report (`--cov=app --cov-report=xml`).
   - Linting check with `ruff` or `flake8`.
2. **Frontend CI**:
   - Node setup (v20+).
   - `npm ci` (or `npm install`).
   - TypeScript compilation check (`npx tsc --noEmit`).
   - ESLint check (`npm run lint`).
   - Component unit tests (`npm test` / `npx vitest run`).
3. **E2E CI**:
   - Install Playwright browsers (`npx playwright install --with-deps`).
   - Start backend test server and frontend test server in background.
   - Execute Playwright E2E suite headless.
   - Upload Playwright trace and test report artifacts on failure.

---

## 3. Output Expectations

1. Write clean, self-contained test files with clear assertions and descriptive docstrings.
2. Do not use hardcoded sleep intervals; use async waits and deterministic polling.
3. Ensure all tests run with in-memory or ephemeral databases (`sqlite+aiosqlite:///:memory:`) so production database files are untouched.
4. Verify all tests pass locally before completing the task.
```
