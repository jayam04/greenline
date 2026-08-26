# Gemini & Antigravity Agent Guidelines: Greenline

## 🚨 MANDATORY PROTOCOL: Test-First Development (TDD)

When responding to ANY coding task, bug report, or feature request:
1. **Analyze Requirements**: Break down the prompt into explicit test cases.
2. **Write Tests First**:
   - For backend changes: Write or update test functions in `backend/tests/` using `@pytest.mark.anyio` and in-memory SQLite. Run the test to confirm it fails (Red).
   - For frontend changes: Write or update component tests (`vitest`) or E2E tests (`playwright`).
3. **Implement Changes**: Modify only the necessary application files to pass the tests (Green).
4. **Full Test & Build Verification**:
   - Always run `PYTHONPATH=backend pytest backend/tests`
   - Always run `npx tsc --noEmit` in `frontend/`
5. **Never finish a task without showing test execution output.**
6. **Mandatory Commit Message Trailer**:
   - If ANY file in the workspace was created, modified, or deleted during the turn, your reply MUST terminate with:
     ```
     Commit Message:
     <Commit message to use>
     ```
     (using Conventional Commits format, e.g. `feat(...)`, `fix(...)`, `test(...)`).
