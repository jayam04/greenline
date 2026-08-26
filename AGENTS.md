# Project Guidelines for AI Agents (Antigravity CLI, IDE, Subagents)

Welcome to **Greenline**. Every AI agent interacting with this repository must strictly adhere to the engineering guidelines outlined below.

---

## 1. Core Engineering Principle: Test-First Development (TDD)

All coding tasks, feature implementations, bug fixes, and refactoring **MUST** follow a strict Test-First protocol:

1. **Extract Requirements & Test Scenarios**:
   - Before writing or modifying any implementation code, translate the user requirements into clear, explicit test scenarios.
2. **Write Failing Tests First (Red Phase)**:
   - Create or update the corresponding unit tests (backend `pytest`, frontend `vitest`) or End-to-End tests (`playwright`) **BEFORE** modifying application logic.
   - Run the test to confirm that it fails on missing features or reproduces the reported bug.
3. **Implement Minimal Code (Green Phase)**:
   - Write the cleanest, most concise implementation code necessary to make all tests pass.
4. **Refactor & Verify Zero Regression (Refactor Phase)**:
   - Run the complete test suite (`PYTHONPATH=backend pytest backend/tests`, `npx tsc --noEmit`, frontend test suites) to ensure 100% test passing and zero regressions.
5. **No Production Edits Without Tests**:
   - Never consider a feature or bug fix complete without dedicated automated test verification.

---

## 2. Testing Stack & Conventions

- **Backend**:
  - Test runner: `pytest` with `@pytest.mark.anyio`
  - In-memory database fixture: `sqlite+aiosqlite:///:memory:`
  - Run command: `PYTHONPATH=backend pytest backend/tests`
- **Frontend**:
  - Type checking: `npx tsc --noEmit`
  - Linting: `npm run lint`
  - Component tests: `npx vitest run` / `@testing-library/react`
  - E2E tests: `npx playwright test`

---

## 3. Financial Computation Integrity

- **Precision**: Store and calculate monetary amounts with 2 decimal places precision (`round(x, 2)`).
- **FIFO Engine**: When processing sells, always deplete open lots in chronological order (earliest `buy_date` first).
- **Fees & Taxes**:
  - Stock P&L must incorporate purchase fees/taxes (cost basis) and sale fees/taxes.
  - Cash deductions on funded transactions must avoid double-counting fees/taxes when `total_amount` is already net.
- **Account Valuations**: Demat accounts must reflect total valuation (`cash_balance + securities_value`).

---

## 4. Response Protocol: Mandatory Commit Message on File Edits

Whenever you create, modify, rename, or delete ANY file in the workspace during a turn:

1. **Mandatory Trailer**:
   - You **MUST** end your final reply with the following trailer:
     ```
     Commit Message:
     <Commit message to use>
     ```
2. **Formatting**:
   - Follow Conventional Commits format: `<type>(<scope>): <summary>` (e.g., `feat(investments): ...`, `fix(cashflow): ...`, `test(portfolio): ...`, `refactor(accounts): ...`).
   - Keep the message concise, imperative, and descriptive of the exact changes made in the turn.
3. **Condition**:
   - MUST be present whenever at least one file was created or modified.
   - Omit ONLY if no files were touched in the turn (e.g., pure Q&A or planning mode).
