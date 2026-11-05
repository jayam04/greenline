# Project Changelog

This document maintains an automated, continuous, and machine-parseable log of all engineering changes made to the Greenline repository by AI agents and developers.

---

## Machine Readability Specification for Automated Crawlers

Every entry in this changelog contains both human-readable Markdown and an embedded machine-parseable JSON metadata block formatted as follows:

```
<!-- changelog-entry-json
{
  "timestamp": "ISO-8601 UTC timestamp",
  "type": "feat|fix|refactor|test|chore|docs|perf|style|ci|build",
  "scope": "domain-scope",
  "summary": "imperative summary",
  "affected_files": ["relative/path/1", "relative/path/2"],
  "rationale": "explanation of why the change was made",
  "breaking_changes": false,
  "verification": {
    "command": "verification command",
    "result": "PASSED"
  }
}
-->
```

External scripts, cron jobs, time-triggered workflows, and crawlers can extract all events reliably using regex: `<!--\s*changelog-entry-json\s*(\{[\s\S]*?\})\s*-->`.

---

## Log of Changes

### [2026-11-05 17:15:00 UTC] fix(frontend): resolve Failed to fetch by integrating local Oracle container and SSR api resolution

<!-- changelog-entry-json
{
  "timestamp": "2026-11-05T17:15:00Z",
  "type": "fix",
  "scope": "frontend",
  "summary": "resolve Failed to fetch by integrating local Oracle container and SSR api resolution",
  "affected_files": [
    "docker-compose.yml",
    "frontend/src/lib/api.ts",
    "scripts/migrate_sqlite_to_oracle.py"
  ],
  "rationale": "Resolve backend crash loop from cloud Oracle listener refusal by embedding local Oracle 23ai in docker compose, routing SSR API calls to internal backend host, and hydrating records from legacy SQLite store.",
  "breaking_changes": false,
  "verification": {
    "command": "PYTHONPATH=backend pytest backend/tests && cd frontend && npm run build && npm run lint",
    "result": "PASSED"
  }
}
-->

- **Type / Scope**: `fix(frontend)`
- **Summary**: Fixed `TypeError: Failed to fetch` by embedding local Oracle Free 23ai in `docker-compose.yml`, establishing SSR fallback to internal Docker network host in `apiFetch`, and hydrating 13 accounts, 81 transactions, and 53 lots into Oracle.
- **Rationale**: Backend was failing during startup because the remote cloud Oracle ADB listener was refusing connections. Additionally, SSR renders within Docker containers needed to route to `http://backend:8000` rather than `localhost:8000`.
- **Key Changes**:
  - [`docker-compose.yml`](file:///home/jayampatel/swe/greenline/docker-compose.yml): Added `oracle` service with `gvenzl/oracle-free:slim-faststart`, persistent volume, and healthcheck; configured backend to depend on healthy Oracle and provided `INTERNAL_API_URL` to frontend.
  - [`frontend/src/lib/api.ts`](file:///home/jayampatel/swe/greenline/frontend/src/lib/api.ts): Updated `getApiBase()` to use `INTERNAL_API_URL` / `http://backend:8000` during server-side execution and `http://localhost:8000` in the browser.
  - [`scripts/migrate_sqlite_to_oracle.py`](file:///home/jayampatel/swe/greenline/scripts/migrate_sqlite_to_oracle.py): Migrated legacy data from `data/investments.db` into Oracle Database and recalculated FIFO lots and net worth snapshots.
- **Verification**:
  - Backend pytest suite: 118 passed against Oracle `FREEPDB1`.
  - Frontend production build & lint: Zero errors.
  - Container health checks: All 3 containers (`greenline-oracle`, `greenline-backend-1`, `greenline-frontend-1`) healthy and serving requests.

### [2026-11-05 01:50:00 UTC] feat(agents): automate changelog tracking with machine-parseable schema

<!-- changelog-entry-json
{
  "timestamp": "2026-11-05T01:50:00Z",
  "type": "feat",
  "scope": "agents",
  "summary": "automate agents changelog tracking with machine parseable entries",
  "affected_files": [
    ".agents/changelog.md",
    ".agents/rules/changelog_update_requirement.md",
    ".agents/rules/test_first_development.md",
    ".agents/skills/changelog-update/SKILL.md",
    "AGENTS.md",
    "GEMINI.md"
  ],
  "rationale": "Enforce automated updates to .agents/changelog.md on every repository modification so time-triggered workflows and crawlers can reliably ingest project updates.",
  "breaking_changes": false,
  "verification": {
    "command": "python3 -c 'import re, json...'",
    "result": "PASSED"
  }
}
-->

- **Type / Scope**: `feat(agents)`
- **Summary**: Establish automated changelog updating rule, skill guidelines, machine-parseable JSON contract, and update the 6-step agent workflow.
- **Rationale**: Allow external crawlers, automated time-triggered workflows, and team members to consume repository updates directly from `.agents/changelog.md` without unstructured scraping.
- **Key Changes**:
  - [`.agents/rules/changelog_update_requirement.md`](file:///home/jayampatel/swe/greenline/.agents/rules/changelog_update_requirement.md): Created rule with `trigger: always_on` mandating that agents update `changelog.md` on all turns that modify workspace files.
  - [`.agents/skills/changelog-update/SKILL.md`](file:///home/jayampatel/swe/greenline/.agents/skills/changelog-update/SKILL.md): Defined machine schema, crawler code examples (Python/Node.js), and verification commands.
  - [`AGENTS.md`](file:///home/jayampatel/swe/greenline/AGENTS.md) & [`GEMINI.md`](file:///home/jayampatel/swe/greenline/GEMINI.md): Expanded TDD protocol from 5 steps to 6 steps to formally mandate changelog updating as Step 5 before the commit message.
  - [`.agents/rules/test_first_development.md`](file:///home/jayampatel/swe/greenline/.agents/rules/test_first_development.md): Updated TDD rule to match the 6-step workflow.
  - [`.agents/changelog.md`](file:///home/jayampatel/swe/greenline/.agents/changelog.md): Initialized log with specifications and historical entries.
- **Verification**:
  - Validated JSON parsing of all changelog blocks.

### [2026-11-05 00:03:00 UTC] feat(ai): remove AI import pipeline and frontend section in favor of MCP tool

<!-- changelog-entry-json
{
  "timestamp": "2026-11-05T00:03:00Z",
  "type": "feat",
  "scope": "ai",
  "summary": "remove frontend AI import section and backend pipelines in favor of MCP tool",
  "affected_files": [
    "backend/app/api/v1/import_endpoints.py",
    "backend/app/api/v1/router.py",
    "backend/app/models/import_batch.py",
    "backend/app/models/staged_record.py",
    "backend/app/models/__init__.py",
    "backend/app/services/ai/",
    "frontend/src/app/import/",
    "frontend/src/components/layout/Sidebar.tsx"
  ],
  "rationale": "Transition AI integration to MCP tools only, removing legacy frontend import wizard and backend AI document parsing pipelines.",
  "breaking_changes": true,
  "verification": {
    "command": "PYTHONPATH=backend pytest backend/tests && cd frontend && npx tsc --noEmit && npm run lint",
    "result": "PASSED"
  }
}
-->

- **Type / Scope**: `feat(ai)`
- **Summary**: Removed AI import frontend pages, navigation items, tests, and backend import models/services while preserving FastMCP AI tools.
- **Rationale**: Streamline AI integration around MCP server endpoints rather than manual UI import wizards.
- **Key Changes**:
  - Removed `frontend/src/app/import/` and sidebar navigation links.
  - Removed backend models `ImportBatch`, `StagedRecord` and routers in `backend/app/api/v1/import_endpoints.py`.
  - Retained FastMCP tool capabilities in `backend/app/mcp/`.
- **Verification**:
  - Backend tests: 118 passed.
  - Frontend TypeScript & ESLint: Clean pass.

### [2026-11-04 21:50:00 UTC] refactor(db): completely remove SQLite support and standardize on Oracle Free 23ai

<!-- changelog-entry-json
{
  "timestamp": "2026-11-04T21:50:00Z",
  "type": "refactor",
  "scope": "db",
  "summary": "remove SQLite database support and standardize test suite on local Oracle 23ai FREEPDB1",
  "affected_files": [
    "backend/app/core/config.py",
    "backend/app/core/database.py",
    "backend/tests/conftest.py",
    "docker-compose.test.yml",
    "docker-compose.yml"
  ],
  "rationale": "Eliminate dialect mismatch discrepancies between SQLite and Oracle production database, utilizing Docker-based Oracle Free 23ai for all backend test runs.",
  "breaking_changes": false,
  "verification": {
    "command": "PYTHONPATH=backend pytest backend/tests",
    "result": "PASSED"
  }
}
-->

- **Type / Scope**: `refactor(db)`
- **Summary**: Removed all SQLite fallback and dialects from `config.py` and `database.py`. Switched test fixtures in `conftest.py` to target local Oracle 23ai (`FREEPDB1`).
- **Rationale**: Ensure full parity between testing and production database engines.
- **Key Changes**:
  - Enforced `oracle+oracledb://` connection strings across all environments.
  - Configured `conftest.py` with multi-session safety, table truncations, and User 0 persistence.
- **Verification**:
  - All 118 backend tests passed against Oracle 23ai.
