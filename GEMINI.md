# Gemini & Antigravity Agent Guidelines: Greenline

These guidelines apply to Gemini and Antigravity agents working in Greenline. They directly reflect the core repository rules established in [`AGENTS.md`](./AGENTS.md).

---

## 1. Instruction Precedence

These repository-level guidelines explicitly defer to higher-priority system and developer instructions. They guide development conventions in this codebase without conflicting with or overriding higher-priority instructions.

---

## 2. Mandatory Protocol: 5-Step Test-First Development (TDD)

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
     - `PYTHONPATH=backend /home/jayampatel/swe/greenline/backend/.venv/bin/pytest backend/tests`
     - `cd frontend && npx tsc --noEmit && npm run lint`
   - Always display test execution output in the turn response.
5. **Provide Proposed Commit Message**:
   - When repository or workspace files have been created, modified, deleted, renamed, or moved, append the proposed commit message as a dedicated block at the very end of your final response:
     ```text
     Commit Message:
     <type>(<scope>): <imperative summary>
     ```
   - Omit the proposed commit message for read-only inspection, file searches, non-modifying tests, planning turns before user approval, and purely conversational responses.
   - Follow Conventional Commits format per [`.agents/skills/conventional-commit/SKILL.md`](.agents/skills/conventional-commit/SKILL.md).
