# Project Guidelines for AI Agents (Antigravity CLI, IDE, Subagents)

Welcome to **Greenline**. Every AI agent interacting with this repository must strictly adhere to the engineering guidelines outlined below.

---

## 1. Core Engineering Principle: Test-First Development (TDD)

All coding tasks, feature implementations, bug fixes, and refactoring **MUST** follow the authoritative 5-step Test-First workflow:

1. **Requirement / Specification**:
   - Before writing or modifying any implementation code, translate user requirements into explicit test scenarios, input/output contracts, and edge cases.
2. **Write Failing Test (Red Phase)**:
   - Create or update automated tests (backend `pytest`, frontend `vitest`/`playwright`) **before** modifying application logic.
   - Run the test to confirm it fails, reproducing the bug or asserting the new capability.
3. **Implement (Green Phase)**:
   - Write the cleanest, most concise implementation code necessary to make all tests pass.
4. **Refactor & Verify (Refactor Phase)**:
   - Run the complete test suite and verification tools to ensure 100% passing tests and zero regressions.
   - Never consider a feature or bug fix complete without dedicated automated test verification and execution output.
5. **Output Proposed Commit Message**:
   - When files have been modified, append the proposed commit message trailer as the final block of the response.

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

## 4. Response Protocol: Proposed Commit Message on File Edits

When repository or workspace files are created, modified, renamed, or deleted during a turn:

1. **Trailer Format & Placement**:
   - Append the proposed commit message as a dedicated trailing block at the very end of your final response:
     ```text
     Commit Message:
     <Commit message to use>
     ```
2. **Formatting Standard**:
   - Follow Conventional Commits format: `<type>(<scope>): <summary>`.
   - Refer to [`.agents/skills/conventional-commit/SKILL.md`](.agents/skills/conventional-commit/SKILL.md) for full types and Greenline domain scopes.
3. **Trigger & Omission**:
   - **Required**: When repository or workspace files are created, modified, renamed, or deleted.
   - **Omitted**: Omit for conversational responses, planning turns before user approval, and read-only operations (searching, code inspection, reading docs).
