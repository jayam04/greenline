---
name: commit-message-requirement
description: Enforces providing a proposed git commit message at the end of every reply that modifies repository or workspace files.
trigger: always_on
---

# Proposed Commit Message Rule

## Instruction Precedence

This repository rule is subordinate to and explicitly defers to higher-priority system and developer instructions. It complements standard explanations and verification outputs without replacing them or conflicting with higher-priority instructions.

## Requirement

When repository or workspace files are created, modified, deleted, renamed, or moved during a turn, you must include a proposed git commit message at the very end of your final response.

```text
Commit Message:
<type>(<scope>): <imperative summary>
```

### Protocol Guidelines:

1. **When the Requirement Applies**:
   - **Required**: Whenever any file in the repository or workspace is actually created, modified, deleted, renamed, or moved, or any repository/workspace change is made.
   - **Omitted**: Strictly omit when no repository or workspace files are modified, such as read-only inspection, searching, reading documentation, running tests that do not modify files, planning turns before user approval, or purely conversational responses.

2. **Placement**:
   - The proposed commit message must appear at the very end of the agent's final response as a dedicated block.
   - It complements standard markdown explanations, test results, and file links without replacing them.

3. **Format**:
   - Follow Conventional Commits format: `<type>(<scope>): <imperative summary>`.
   - See [`.agents/skills/conventional-commit/SKILL.md`](../skills/conventional-commit/SKILL.md) for the authoritative list of types, Greenline domain scopes, and formatting conventions.
