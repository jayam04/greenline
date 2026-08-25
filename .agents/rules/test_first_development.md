---
name: test-first-development
description: Enforces test-driven development (TDD) and test-first generation across all coding, fixing, and refactoring tasks.
trigger: always_on
---

# Test-First Development (TDD) Rule

When performing ANY task that requires creating, modifying, fixing, or refactoring code:

1. **Test-First Requirement**:
   - Write or update automated unit/integration/E2E tests **BEFORE** writing the implementation code.
   - Run the test to demonstrate failure (reproducing the bug or asserting new expected behavior).

2. **Backend Testing Standards**:
   - Location: `backend/tests/test_*.py`
   - Use `@pytest.mark.anyio` and in-memory async SQLite engine (`sqlite+aiosqlite:///:memory:`).
   - Test calculations, edge cases, zero-values, and database constraints.
   - Command: `PYTHONPATH=backend /home/jayampatel/swe/greenline/backend/.venv/bin/pytest backend/tests`

3. **Frontend Testing Standards**:
   - Run TypeScript verification: `npx tsc --noEmit`
   - Component & E2E tests: Ensure UI components render correct monetary values, formatters, and interactions.

4. **Completion Requirement**:
   - A task is NEVER complete until the full test suite runs cleanly with 0 failures.
