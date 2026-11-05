---
trigger: always_on
description: Mandatory rule requiring AI agents to append structured, machine-parseable changelog entries to .agents/changelog.md whenever repository or workspace files are modified.
---

# Mandatory Changelog Update Rule

## 1. Instruction Precedence

This repository rule is subordinate to and explicitly defers to higher-priority system and developer instructions. It complements standard explanations, verification outputs, and commit messages without replacing them.

---

## 2. Mandatory Protocol: Automated Changelog Maintenance

Whenever an AI agent (Antigravity CLI, IDE, subagents, or automated planners) creates, modifies, deletes, renames, or moves any file in this repository or workspace during a turn, the agent **MUST** update [`.agents/changelog.md`](file:///home/jayampatel/swe/greenline/.agents/changelog.md) before concluding the turn.

### Workflow Sequence

The 6-step engineering protocol for every coding turn modifying repository files is:
1. **Requirement / Specification**: Define explicit test scenarios, input/output contracts, and edge cases.
2. **Failing Test (Red Phase)**: Write or update automated unit/integration tests and verify failure.
3. **Implement (Green Phase)**: Write the cleanest, most concise implementation code to pass tests.
4. **Refactor & Verify**: Execute test suites and linters (`pytest`, `npx tsc --noEmit`, `npm run lint`).
5. **Update `.agents/changelog.md`**: Prepend or insert the detailed, machine-parseable entry at the top of the log section.
6. **Proposed Commit Message**: Output the Conventional Commit message at the very end of the final response.

---

## 3. Strict Scope & Recursion Guard

1. **Trigger Condition (Required)**:
   - Any turn in which repository or workspace files are added, modified, deleted, renamed, or moved (including code, configs, tests, documentation, workflows, or rules).
2. **Trigger Condition (Strictly Omitted)**:
   - Read-only queries, code inspections, and workspace searches.
   - Non-modifying test or verification runs.
   - Planning or discussion turns prior to explicit user approval.
   - Self-referential recursion: Updating `.agents/changelog.md` alone to record a task does NOT trigger another changelog entry.

---

## 4. Machine-Parseable Schema & Formatting Contract

To ensure automated crawlers, webhooks, and time-triggered workflows can ingest changes without scraping ambiguities, every changelog entry must include both human-readable Markdown and an embedded machine-parseable JSON metadata comment block.

### Required Entry Template

```markdown
### [<YYYY-MM-DD HH:MM:SS UTC>] <type>(<scope>): <Title / Imperative Summary>

<!-- changelog-entry-json
{
  "timestamp": "<YYYY-MM-DDTHH:MM:SSZ>",
  "type": "<feat|fix|refactor|test|chore|docs|perf|style|ci|build>",
  "scope": "<domain-scope>",
  "summary": "<short description matching commit header>",
  "affected_files": [
    "<path/to/file1>",
    "<path/to/file2>"
  ],
  "rationale": "<why this change was made>",
  "breaking_changes": false,
  "verification": {
    "command": "<command executed to verify>",
    "result": "PASSED"
  }
}
-->

- **Type / Scope**: `<type>(<scope>)`
- **Summary**: <Short descriptive summary of what was accomplished>
- **Rationale**: <Why this change was implemented or bug was addressed>
- **Key Changes**:
  - `<file_path>`: <Bullet point description of changes made>
- **Verification**:
  - Command: `<verification command executed>`
  - Output: `<summary of passing test results, lint checks, or status>`
```

### JSON Schema Rules:
- The JSON block must immediately follow the Markdown heading as `<!-- changelog-entry-json ... -->`.
- All JSON must be strictly valid JSON (parseable via standard JSON libraries like `json.loads` or `JSON.parse`).
- `timestamp` must be ISO-8601 UTC.
- `affected_files` must list all workspace files touched during the task.
