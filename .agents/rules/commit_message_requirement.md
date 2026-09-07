---
name: commit-message-requirement
description: Enforces appending a proposed git commit message at the end of every reply that modifies repository or workspace files.
trigger: always_on
---

# Mandatory Commit Message Output Rule

When repository or workspace files are created, modified, renamed, or deleted during a turn, you must include a proposed git commit message in your final response.

```text
Commit Message:
<type>(<scope>): <imperative summary>
```

### Protocol Guidelines:

1. **Trigger Condition**:
   - **Required**: Whenever any file in the repository or workspace is actually created, modified, renamed, or deleted.
   - **Omitted**: Strictly omit for conversational responses, planning turns before user approval, and read-only operations (such as viewing files, searching, reading documentation, or running read-only diagnostic checks).

2. **Placement**:
   - The commit message trailer must appear at the very end of the agent's final response as a dedicated trailing block.
   - It complements standard markdown explanations, test results, and file links without replacing them or interfering with system or developer instructions.

3. **Format**:
   - Follow Conventional Commits format: `<type>(<scope>): <imperative summary>`.
   - See [`.agents/skills/conventional-commit/SKILL.md`](../skills/conventional-commit/SKILL.md) for the authoritative list of types, Greenline domain scopes, and formatting conventions.
