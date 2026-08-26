---
name: commit-message-requirement
description: Enforces appending a proposed git commit message at the end of every reply that modifies workspace files.
trigger: always_on
---

# Mandatory Commit Message Output Rule

Whenever ANY tool call in the current turn creates, modifies, renames, or deletes one or more files in the workspace:

You **MUST** end your final response with the following trailer:

```
Commit Message:
<Commit message to use>
```

### Guidelines:
1. **Format**: Follow Conventional Commits format (`<type>(<scope>): <imperative summary>`).
   - `feat(...)`: New feature or user-facing capability.
   - `fix(...)`: Bug fix or calculation error correction.
   - `test(...)`: Adding or updating test suites.
   - `refactor(...)`: Code refactoring without behavioral change.
   - `docs(...)`: Documentation, skills, or guidelines updates.
   - `chore(...)`: Maintenance or configuration updates.
2. **Placement**: Always positioned at the very end of your response as the final text block.
3. **Condition**: Only omit when NO files were created or modified during the turn (e.g. conversational replies, planning mode before approval, pure research/Q&A).
