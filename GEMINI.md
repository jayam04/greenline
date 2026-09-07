# Gemini & Antigravity Agent Guidelines: Greenline

These guidelines apply to Gemini and Antigravity agents working in Greenline. They directly reflect the core repository rules established in [`AGENTS.md`](./AGENTS.md).

---

## 🚨 MANDATORY PROTOCOL: 5-Step Test-First Development (TDD)

When responding to ANY coding task, bug report, or feature implementation:

1. **Requirement / Specification**:
   - Break down user requirements into explicit test cases, contract expectations, and mathematical assertions.
2. **Write Failing Test (Red Phase)**:
   - For backend changes: Write or update test functions in `backend/tests/` using `@pytest.mark.anyio` and in-memory SQLite fixtures. Run the test to confirm it fails.
   - For frontend changes: Write or update component tests (`vitest`) or E2E tests (`playwright`).
3. **Implement (Green Phase)**:
   - Modify only the necessary application files to pass the tests cleanly.
4. **Refactor / Verify**:
   - Run the full verification suite to ensure zero regressions:
     - `PYTHONPATH=backend pytest backend/tests`
     - `cd frontend && npx tsc --noEmit && npm run lint`
   - Always display test execution output in the turn response.
5. **Output Proposed Commit Message**:
   - Whenever repository or workspace files are created, modified, renamed, or deleted, append the proposed commit message as a dedicated trailing block at the very end of your final response:
     ```text
     Commit Message:
     <type>(<scope>): <imperative summary>
     ```
   - Omit this trailer for conversational responses, planning turns before user approval, and read-only operations.
   - Follow Conventional Commits format per [`.agents/skills/conventional-commit/SKILL.md`](.agents/skills/conventional-commit/SKILL.md).
