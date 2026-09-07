---
name: test-first-development
description: Enforces test-driven development (TDD) and test-first verification across all coding, fixing, and refactoring tasks.
trigger: always_on
---

# Test-First Development (TDD) Rule

When performing ANY task that involves creating, modifying, fixing, or refactoring code, follow this authoritative 5-step workflow:

1. **Requirement / Specification**:
   - Translate requirements into explicit test scenarios, input/output contracts, and edge cases.

2. **Write Failing Test (Red Phase)**:
   - Add or update automated unit, integration, or E2E tests **before** touching application logic.
   - Execute the test to confirm it fails, proving the test reproduces the issue or validates the new behavior.

3. **Implement (Green Phase)**:
   - Write the cleanest, most concise implementation code required to make all tests pass.

4. **Refactor & Verify**:
   - Clean up code structure and verify zero regressions by running full test suites and type checks:
     - **Backend**: `PYTHONPATH=backend /home/jayampatel/swe/greenline/backend/.venv/bin/pytest backend/tests`
     - **Frontend**: `cd frontend && npx tsc --noEmit && npm run lint`
   - A task is never complete without displaying clean test execution output.

5. **Output Proposed Commit Message**:
   - Append the proposed commit message trailer at the very end of your final reply per the commit message protocol.

For full test fixtures, scaffolding patterns, and runbooks, refer to [`.agents/skills/test-driven-development/SKILL.md`](../skills/test-driven-development/SKILL.md).
