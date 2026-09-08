# Project Guidelines for AI Agents (Antigravity CLI, IDE, Subagents)

Welcome to **Greenline**. Every AI agent interacting with this repository must adhere to the engineering guidelines outlined below.

---

## 1. Instruction Precedence

These repository-level guidelines and rules are subordinate to and explicitly defer to higher-priority system and developer instructions. They guide development conventions in this codebase without conflicting with or overriding higher-priority instructions.

---

## 2. Core Engineering Principle: Test-First Development (TDD)

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
5. **Provide Proposed Commit Message**:
   - When repository or workspace files have been created, modified, deleted, renamed, or moved, provide a proposed Conventional Commit message at the very end of your final response.

For complete fixtures, scaffolding patterns, and runbooks, refer to [`.agents/skills/test-driven-development/SKILL.md`](.agents/skills/test-driven-development/SKILL.md).

---

## 3. Testing Stack & Conventions

- **Backend**:
  - Test runner: `pytest` with `@pytest.mark.anyio`
  - In-memory database fixture: `sqlite+aiosqlite:///:memory:`
  - Run command: `PYTHONPATH=backend /home/jayampatel/swe/greenline/backend/.venv/bin/pytest backend/tests`
- **Frontend**:
  - Type checking: `npx tsc --noEmit`
  - Linting: `npm run lint`
  - Component tests: `npx vitest run` / `@testing-library/react`
  - E2E tests: `npx playwright test`

---

## 4. Financial Computation Integrity

- **Precision**: Store and calculate monetary amounts with 2 decimal places precision (`round(x, 2)`).
- **FIFO Engine**: When processing sells, always deplete open lots in chronological order (earliest `buy_date` first).
- **Fees & Taxes**:
  - Stock P&L must incorporate purchase fees/taxes (cost basis) and sale fees/taxes.
  - Cash deductions on funded transactions must avoid double-counting fees/taxes when `total_amount` is already net.
- **Account Valuations**: Demat accounts must reflect total valuation (`cash_balance + securities_value`).

---

## 5. Response Protocol: Proposed Commit Message on Repository Modifications

When repository or workspace files are created, modified, deleted, renamed, or moved during a turn:

1. **Format & Placement**:
   - Include the proposed commit message as a dedicated block at the very end of your final response:
     ```text
     Commit Message:
     <type>(<scope>): <short imperative description>
     ```
2. **Formatting Standard**:
   - Follow Conventional Commits format: `<type>(<scope>): <summary>`.
   - Refer to [`.agents/skills/conventional-commit/SKILL.md`](.agents/skills/conventional-commit/SKILL.md) for authoritative types and Greenline domain scopes.
3. **When the Requirement Applies**:
   - **Required**: Whenever the agent actually creates, modifies, deletes, renames, or moves a file, or otherwise makes a repository/workspace change.
   - **Omitted**: Strictly omit for read-only inspection, searches, tests or commands that do not modify repository files, planning turns before user approval, and purely conversational answers.
