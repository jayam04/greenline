---
name: changelog-update
description: Guidelines and machine-parseable contract for maintaining .agents/changelog.md across all AI agent tasks, including crawler ingestion specs and validation utilities.
---

# Changelog Maintenance Skill

This skill defines the requirements, structure, and machine-ingestion contracts for [`.agents/changelog.md`](file:///home/jayampatel/swe/greenline/.agents/changelog.md).

---

## 1. Purpose & Crawler Integration

The Greenline changelog serves two critical roles:
1. **Developer & Agent Audit Trail**: Complete human-readable record of what changed, why, what files were affected, and how it was verified.
2. **Automated Crawler & Trigger Trigger Engine**: A machine-readable event stream consumed by time-triggered crons, background crawlers, deployment hooks, and webhook dispatchers.

---

## 2. Machine-Readable Schema

Every entry in [`.agents/changelog.md`](file:///home/jayampatel/swe/greenline/.agents/changelog.md) MUST have an embedded HTML comment block containing valid JSON:

```markdown
<!-- changelog-entry-json
{
  "timestamp": "2026-11-05T01:50:00Z",
  "type": "feat",
  "scope": "agents",
  "summary": "automate agents changelog tracking with machine parseable entries",
  "affected_files": [
    ".agents/changelog.md",
    ".agents/rules/changelog_update_requirement.md",
    ".agents/skills/changelog-update/SKILL.md",
    "AGENTS.md",
    "GEMINI.md"
  ],
  "rationale": "Enable automated crawlers and time-triggered workflows to parse project changes reliably without ambiguous scraping.",
  "breaking_changes": false,
  "verification": {
    "command": "python3 -c \"import re, json; ...\"",
    "result": "PASSED"
  }
}
-->
```

### JSON Fields Specification

| Field | Type | Description |
| :--- | :--- | :--- |
| `timestamp` | `string` | ISO-8601 UTC timestamp of change completion (`YYYY-MM-DDTHH:MM:SSZ`). |
| `type` | `string` | Conventional commit type: `feat`, `fix`, `refactor`, `test`, `chore`, `docs`, `perf`, `style`, `ci`, `build`. |
| `scope` | `string` | Greenline domain scope (e.g., `agents`, `db`, `portfolio`, `cashflow`, `auth`, `mcp`, `frontend`). |
| `summary` | `string` | Concise imperative summary of the change. |
| `affected_files` | `string[]` | Array of relative file paths modified or created. |
| `rationale` | `string` | Detailed technical reason for the modification. |
| `breaking_changes` | `boolean` | True if this change introduces breaking API or schema modifications. |
| `verification` | `object` | Contains `command` (execution string) and `result` (`PASSED` or status). |

---

## 3. Crawler Ingestion Snippets

### Python Crawler Example
```python
import re
import json
from pathlib import Path

def extract_changelog_entries(changelog_path: str = ".agents/changelog.md"):
    content = Path(changelog_path).read_text(encoding="utf-8")
    pattern = r"<!--\s*changelog-entry-json\s*(\{.*?\})\s*-->"
    matches = re.findall(pattern, content, re.DOTALL)
    entries = [json.loads(m) for m in matches]
    return entries

if __name__ == "__main__":
    entries = extract_changelog_entries()
    print(f"Loaded {len(entries)} changelog events for processing.")
```

### Node.js Crawler Example
```javascript
import fs from 'node:fs';

export function extractChangelogEntries(changelogPath = '.agents/changelog.md') {
  const content = fs.readFileSync(changelogPath, 'utf-8');
  const regex = /<!--\s*changelog-entry-json\s*(\{[\s\S]*?\})\s*-->/g;
  const entries = [];
  let match;
  while ((match = regex.exec(content)) !== null) {
    entries.push(JSON.parse(match[1]));
  }
  return entries;
}
```

---

## 4. Verification Check

Before concluding any turn modifying `.agents/changelog.md`, verify that all entries are valid JSON:

```bash
python3 -c '
import re, json, sys
content = open(".agents/changelog.md").read()
matches = re.findall(r"<!--\s*changelog-entry-json\s*(\{.*?\})\s*-->", content, re.DOTALL)
if not matches:
    print("Error: No changelog JSON blocks found!", file=sys.stderr)
    sys.exit(1)
for i, m in enumerate(matches):
    try:
        json.loads(m)
    except Exception as e:
        print(f"Error parsing entry {i}: {e}", file=sys.stderr)
        sys.exit(1)
print(f"Changelog verification PASSED: {len(matches)} valid entries parsed.")
'
```
