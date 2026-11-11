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

### [2026-11-11 13:50:00 UTC] fix(auth): normalize Auth0 issuer validation and prevent infinite login redirect loops

<!-- changelog-entry-json
{
  "timestamp": "2026-11-11T13:50:00Z",
  "type": "fix",
  "scope": "auth",
  "summary": "normalize Auth0 issuer validation and prevent infinite login redirect loops",
  "affected_files": [
    "backend/app/services/auth0_service.py",
    "backend/tests/test_auth0_rls.py",
    "frontend/src/__tests__/Auth0Integration.test.tsx",
    "frontend/src/app/login/page.tsx",
    "frontend/src/lib/api.ts"
  ],
  "rationale": "The backend rejected valid Auth0 tokens with 'Invalid issuer' when AUTH0_ISSUER in settings lacked the 'https://' scheme, producing 401 errors that bounced between /login and / due to eager redirect on client-side authenticated state.",
  "breaking_changes": false,
  "verification": {
    "command": "PYTHONPATH=backend pytest backend/tests/test_auth0_rls.py && cd frontend && npx vitest run src/__tests__/Auth0Integration.test.tsx",
    "result": "PASSED"
  }
}
-->

- **Type / Scope**: `fix(auth)`
- **Summary**: Normalize Auth0 issuer matching to accept canonical HTTPS formats regardless of configuration prefix, and guard `/login` against redirect loops when session error query parameters are present.
- **Rationale**: When `AUTH0_ISSUER=jayam04.eu.auth0.com` was configured without `https://`, python-jose's issuer validation failed with `Invalid issuer` against the token's `iss: "https://jayam04.eu.auth0.com/"`. This resulted in 401 responses that bounced repeatedly between `/` and `/login` because `LoginPage` redirected eagerly if the Auth0 React SDK was already authenticated.
- **Key Changes**:
  - `backend/app/services/auth0_service.py`: Added automatic scheme and trailing-slash normalization for `AUTH0_ISSUER`, permitting all canonical domain variations (`https://<domain>/`, bare domain).
  - `backend/tests/test_auth0_rls.py`: Added test verifying that tokens with standard HTTPS issuers are accepted when settings contain bare domains.
  - `frontend/src/app/login/page.tsx`: Gated eager auto-redirect on `error` query parameter so session failures display an informative message instead of looping.
  - `frontend/src/lib/api.ts`: Redirects to `/login?error=session_expired` on 401 to prevent automatic re-routing loops.
  - `frontend/src/__tests__/Auth0Integration.test.tsx`: Added test verifying `LoginPage` suppresses auto-redirect when error query parameters are present.
- **Verification**:
  - Command: `PYTHONPATH=backend pytest backend/tests/test_auth0_rls.py && cd frontend && npx vitest run src/__tests__/Auth0Integration.test.tsx`
  - Output: 20/20 backend tests passed; 13/13 frontend Auth0 tests passed.

### [2026-11-11 13:23:00 UTC] feat(db): implement least-privilege DML-only Oracle application user provisioning and schema resolution

<!-- changelog-entry-json
{
  "timestamp": "2026-11-11T13:23:00Z",
  "type": "feat",
  "scope": "db",
  "summary": "implement least-privilege DML-only Oracle application user provisioning and schema resolution",
  "affected_files": [
    ".env.example",
    "backend/app/config.py",
    "backend/app/db/database.py",
    "backend/app/db/migrations.py",
    "backend/scripts/create_db_app_user.py",
    "backend/scripts/setup_app_user.sql",
    "backend/tests/test_oracle_app_user_permissions.py"
  ],
  "rationale": "Allows running Greenline in production with a least-privilege database user (GREENLINE_APP) restricted to DML operations (SELECT, INSERT, UPDATE, DELETE) across all 21 application tables, prohibiting any table creation, alteration, or deletion.",
  "breaking_changes": false,
  "verification": {
    "command": "PYTHONPATH=backend pytest backend/tests/test_oracle_app_user_permissions.py backend/tests/test_auth0_rls.py backend/tests/test_settings.py",
    "result": "PASSED"
  }
}
-->

- **Type / Scope**: `feat(db)`
- **Summary**: Implement least-privilege DML-only Oracle application database user setup scripts, automated provisioning CLI, session `CURRENT_SCHEMA` resolution, and migration resilience.
- **Rationale**: Previously, Greenline connected directly using the schema owner (`ADMIN`), which held full DDL permissions. To adhere to principle of least privilege, a dedicated `GREENLINE_APP` user is created with `CREATE SESSION` and `SELECT, INSERT, UPDATE, DELETE` on all 21 Greenline tables, with zero DDL privileges.
- **Key Changes**:
  - `backend/scripts/setup_app_user.sql`: Standalone SQL script granting DML permissions on all 21 tables in `ADMIN` schema and creating the `CURRENT_SCHEMA = ADMIN` logon trigger.
  - `backend/scripts/create_db_app_user.py`: Python CLI tool to automate provisioning `GREENLINE_APP` using admin credentials, test DML access, and verify DDL prevention (`ORA-01031`).
  - `backend/app/config.py`: Added `ORACLE_SCHEMA: Optional[str]` configuration.
  - `backend/app/db/database.py`: Registered connection event listener to set `ALTER SESSION SET CURRENT_SCHEMA` on new connections when `ORACLE_SCHEMA` is configured.
  - `backend/app/db/migrations.py`: Handled `ORA-01031: insufficient privileges` gracefully during startup migrations so DML-only connections run seamlessly.
  - `backend/tests/test_oracle_app_user_permissions.py`: Added automated test suite verifying settings, migration exception handling, and table coverage.
  - `.env.example`: Documented the least-privilege database user setup.
- **Verification**:
  - Command: `PYTHONPATH=backend pytest backend/tests/test_oracle_app_user_permissions.py backend/tests/test_auth0_rls.py backend/tests/test_settings.py`
  - Output: 23/23 tests passed.

### [2026-11-11 12:55:00 UTC] fix(auth): resolve password hash null constraint on Auth0 user provisioning and gate OAuth callback route mounts

<!-- changelog-entry-json
{
  "timestamp": "2026-11-11T12:55:00Z",
  "type": "fix",
  "scope": "auth",
  "summary": "resolve password hash null constraint on Auth0 user provisioning and gate OAuth callback route mounts",
  "affected_files": [
    "backend/app/config.py",
    "backend/app/db/migrations.py",
    "backend/app/services/auth0_service.py",
    "backend/app/services/auth_service.py",
    "backend/tests/test_auth0_rls.py",
    "frontend/src/__tests__/Auth0Integration.test.tsx",
    "frontend/src/components/AuthProvider.tsx",
    "frontend/src/lib/api.ts",
    "frontend/src/test/setup.ts"
  ],
  "rationale": "Oracle database raised ORA-01400 on auto-provisioning new Auth0 users because password_hash was set to None against a NOT NULL column in Oracle Autonomous DB. Additionally, premature mounting of protected dashboard routes during Auth0 code exchange raised unhandled 401 callback errors.",
  "breaking_changes": false,
  "verification": {
    "command": "PYTHONPATH=backend pytest backend/tests/test_auth0_rls.py && cd frontend && npx vitest run src/__tests__/Auth0Integration.test.tsx && npx tsc --noEmit && npm run lint",
    "result": "PASSED"
  }
}
-->

- **Type / Scope**: `fix(auth)`
- **Summary**: Fix Oracle database `ORA-01400` null constraint error when auto-provisioning new Auth0 users by setting a secure non-null placeholder and running schema relaxation migration; gate Next.js protected route rendering during OAuth code exchange.
- **Rationale**: When a new user logs in via Auth0 (e.g. Google OAuth2), the user has no password. Oracle Autonomous Database enforced a `NOT NULL` constraint on `ADMIN.USERS.PASSWORD_HASH`, which caused `ORA-01400: cannot insert NULL into (\"ADMIN\".\"USERS\".\"PASSWORD_HASH\")`. Setting `password_hash="!auth0_managed_user"` guarantees schema compliance across all database variants while precluding local password authentication, and adding migration `v013_relax_password_hash_nullability` relaxes the column in DDL.
- **Key Changes**:
  - `backend/app/services/auth_service.py`: Set `password_hash="!auth0_managed_user"` on newly auto-provisioned Auth0 users.
  - `backend/app/db/migrations.py`: Added migration `v013_relax_password_hash_nullability` to modify `users.password_hash` to allow NULL.
  - `backend/tests/test_auth0_rls.py`: Added assertion verifying non-null `password_hash` placeholder that securely rejects local password verification attempts.
  - `frontend/src/components/AuthProvider.tsx`: Gated protected children behind `hasCallbackCode` to prevent premature dashboard mounting and unhandled 401 errors.
  - `frontend/src/lib/api.ts`: Refined 401 handling to suppress redirect to `/login` during OAuth callback and throw standard `Unauthorized` error.
- **Verification**:
  - Command: `PYTHONPATH=backend pytest backend/tests/test_auth0_rls.py && cd frontend && npx vitest run src/__tests__/Auth0Integration.test.tsx`
  - Output: 19/19 backend tests passed; 12/12 frontend Auth0 integration tests passed; TypeScript and ESLint checks passed with 0 errors.

### [2026-11-11 12:17:00 UTC] fix(auth): support client ID audience in backend and gate dashboard mount on token resolution

<!-- changelog-entry-json
{
  "timestamp": "2026-11-11T12:17:00Z",
  "type": "fix",
  "scope": "auth",
  "summary": "support client ID audience in backend and gate dashboard mount on token resolution",
  "affected_files": [
    "backend/app/config.py",
    "backend/app/services/auth0_service.py",
    "backend/tests/test_auth0_rls.py",
    "frontend/src/__tests__/Auth0Integration.test.tsx",
    "frontend/src/components/AuthProvider.tsx",
    "frontend/src/test/setup.ts"
  ],
  "rationale": "Resolve 'Unauthorized - authentication callback in progress' error caused by backend rejecting Auth0 tokens issued for Client ID audience and premature API requests before in-memory token resolution",
  "breaking_changes": false,
  "verification": {
    "command": "cd frontend && npx vitest run src/__tests__/Auth0Integration.test.tsx && npx tsc --noEmit && npm run lint && PYTHONPATH=backend /home/jayampatel/swe/greenline/backend/.venv/bin/pytest backend/tests/test_auth0_rls.py",
    "result": "PASSED"
  }
}
-->

- **Type / Scope**: `fix(auth)`
- **Summary**: Allowed both Auth0 API audience and Client ID audience in backend JWT token validation, added ID token fallback in frontend token getter, and held protected dashboard mounts until the token is fully acquired into memory.
- **Rationale**: When users logged in with Auth0, tokens with audience matching the Client ID were rejected with 401 Unauthorized by the backend's strict audience check. Additionally, `AuthSync` mounted protected children before token acquisition resolved, triggering unauthenticated requests and surfacing the callback guard error.
- **Key Changes**:
  - `backend/app/config.py`: Added `AUTH0_CLIENT_ID` configuration setting.
  - `backend/app/services/auth0_service.py`: Accepted both `AUTH0_AUDIENCE` and `AUTH0_CLIENT_ID` in `jwt.decode` audience matching.
  - `backend/tests/test_auth0_rls.py`: Added automated test `test_auth0_client_id_audience_accepted` asserting 200 OK for Client ID audience tokens.
  - `frontend/src/components/AuthProvider.tsx`: Added `tokenReady` gating state before mounting protected routes, added `getIdTokenClaims` fallback in `setTokenGetter`, and added `onRedirectCallback` URL query cleanup.
  - `frontend/src/test/setup.ts`: Updated `@auth0/auth0-react` test mocks with `getIdTokenClaims`.
  - `frontend/src/__tests__/Auth0Integration.test.tsx`: Verified token getter and profile sync with `tokenReady` lifecycle.
- **Verification**:
  - Command: `cd frontend && npx vitest run src/__tests__/Auth0Integration.test.tsx && npx tsc --noEmit && npm run lint && PYTHONPATH=backend /home/jayampatel/swe/greenline/backend/.venv/bin/pytest backend/tests/test_auth0_rls.py`
  - Output: All tests passed (11/11 frontend, 19/19 backend), 0 TypeScript errors, 0 ESLint errors.

### [2026-11-11 11:40:00 UTC] fix(auth): eliminate Auth0 login redirect loop by gating protected route mounts and guarding 401 callback interception

<!-- changelog-entry-json
{
  "timestamp": "2026-11-11T11:40:00Z",
  "type": "fix",
  "scope": "auth",
  "summary": "eliminate Auth0 login redirect loop by gating protected route mounts and guarding 401 callback interception",
  "affected_files": [
    "backend/app/services/auth0_service.py",
    "frontend/src/__tests__/Auth0Integration.test.tsx",
    "frontend/src/components/AuthProvider.tsx",
    "frontend/src/lib/api.ts"
  ],
  "rationale": "Prevent race condition where protected dashboard mounted immediately during Auth0 redirect callback, fired unauthenticated API requests before code exchange finished, and triggered premature 401 redirect back to /login",
  "breaking_changes": false,
  "verification": {
    "command": "cd frontend && npx vitest run src/__tests__/Auth0Integration.test.tsx && npx tsc --noEmit && npm run lint && PYTHONPATH=backend /home/jayampatel/swe/greenline/backend/.venv/bin/pytest backend/tests/test_auth0_rls.py backend/tests/test_e2e_auth0_rls.py backend/tests/test_settings.py",
    "result": "PASSED"
  }
}
-->

- **Type / Scope**: `fix(auth)`
- **Summary**: Resolved race condition where returning from Auth0 login to `/?code=...` caused immediate unauthenticated API requests and an infinite redirect loop back to `/login`.
- **Rationale**: When Auth0 redirected to the root route, the dashboard mounted before Auth0 finished exchanging the code for an access token. Because no token was available yet, requests returned 401 Unauthorized, triggering the API client's hard redirect to `/login` and aborting the OAuth exchange.
- **Key Changes**:
  - `frontend/src/components/AuthProvider.tsx`: In `AuthSync`, gated protected routes behind an authenticating loading screen while `isLoading: true`, and eagerly primed access tokens upon authentication.
  - `frontend/src/lib/api.ts`: Guarded `apiFetch` against executing `window.location.href = "/login"` when the URL contains active OAuth callback parameters (`code=` and `state=`).
  - `backend/app/services/auth0_service.py`: Elevated Auth0 token decode failures and diagnostics from debug to warning level for transparent observability.
  - `frontend/src/__tests__/Auth0Integration.test.tsx`: Added unit test coverage for protected route loading state and OAuth callback 401 suppression.
- **Verification**:
  - Command: `cd frontend && npx vitest run src/__tests__/Auth0Integration.test.tsx && npx tsc --noEmit && npm run lint && PYTHONPATH=backend /home/jayampatel/swe/greenline/backend/.venv/bin/pytest backend/tests/test_auth0_rls.py backend/tests/test_e2e_auth0_rls.py backend/tests/test_settings.py`
  - Output: All tests passed (11/11 frontend, 59/59 backend), 0 TypeScript errors, 0 ESLint errors.

### [2026-11-11 11:18:00 UTC] fix(auth): wire Auth0 environment variables in docker compose and handle unconfigured fallback in AuthProvider

<!-- changelog-entry-json
{
  "timestamp": "2026-11-11T11:18:00Z",
  "type": "fix",
  "scope": "auth",
  "summary": "wire Auth0 environment variables in docker compose and handle unconfigured fallback in AuthProvider",
  "affected_files": [
    "docker-compose.yml",
    "frontend/src/__tests__/Auth0Integration.test.tsx",
    "frontend/src/components/AuthProvider.tsx",
    "frontend/src/test/setup.ts"
  ],
  "rationale": "Fix infinite 'Connecting to Auth0' loading state caused by missing environment variable injection in frontend container and lack of non-loading fallback context in AuthProvider",
  "breaking_changes": false,
  "verification": {
    "command": "cd frontend && npx vitest run src/__tests__/Auth0Integration.test.tsx && npx tsc --noEmit && npm run lint && PYTHONPATH=backend /home/jayampatel/swe/greenline/backend/.venv/bin/pytest backend/tests/test_auth0_rls.py",
    "result": "PASSED"
  }
}
-->

- **Type / Scope**: `fix(auth)`
- **Summary**: Resolved infinite "Connecting to Auth0..." button state on the login page by forwarding Auth0 environment variables to frontend and backend services in docker compose, providing local environment configuration, and rendering a graceful non-loading fallback context in AuthProvider.
- **Rationale**: When Auth0 variables were absent or unpassed, AuthProvider bypassed mounting Auth0Provider, which left @auth0/auth0-react's default initialContext in a perpetual isLoading: true state.
- **Key Changes**:
  - `docker-compose.yml`: Passed `NEXT_PUBLIC_AUTH0_DOMAIN`, `NEXT_PUBLIC_AUTH0_CLIENT_ID`, `NEXT_PUBLIC_AUTH0_AUDIENCE`, and `NEXT_PUBLIC_AUTH0_ENABLED` to `frontend`, and `AUTH0_DOMAIN`, `AUTH0_AUDIENCE`, and `AUTH0_ISSUER` to `backend`.
  - `frontend/src/components/AuthProvider.tsx`: Wrapped unconfigured renders in `Auth0Context.Provider` with `isLoading: false` and a descriptive configuration error handler for `loginWithRedirect`.
  - `frontend/src/test/setup.ts`: Updated `@auth0/auth0-react` test mocks to export `Auth0Context` and `initialContext`.
  - `frontend/src/__tests__/Auth0Integration.test.tsx`: Added unit test coverage verifying that unconfigured environments receive `isLoading: false`.
- **Verification**:
  - Command: `cd frontend && npx vitest run src/__tests__/Auth0Integration.test.tsx && npx tsc --noEmit && npm run lint && PYTHONPATH=backend /home/jayampatel/swe/greenline/backend/.venv/bin/pytest backend/tests/test_auth0_rls.py`
  - Output: All tests passed (9/9 frontend, 19/19 backend), 0 TypeScript errors, 0 ESLint errors.

### [2026-11-11 11:01:00 UTC] feat(settings): add Google Fonts Spline Sans and Spine Sans support to settings and interface typography

<!-- changelog-entry-json
{
  "timestamp": "2026-11-11T11:01:00Z",
  "type": "feat",
  "scope": "settings",
  "summary": "add Google Fonts Spline Sans and Spine Sans support to settings and interface typography",
  "affected_files": [
    "backend/app/api/routers/settings.py",
    "backend/tests/test_settings.py",
    "frontend/src/__tests__/FontProvider.test.tsx",
    "frontend/src/__tests__/SettingsFont.test.tsx",
    "frontend/src/app/globals.css",
    "frontend/src/app/layout.tsx",
    "frontend/src/app/settings/page.tsx",
    "frontend/src/components/FontProvider.tsx",
    "frontend/src/test/setup.ts"
  ],
  "rationale": "Enable users to configure and use Spline Sans (Google Fonts) with Spine Sans aliasing across application typography and settings",
  "breaking_changes": false,
  "verification": {
    "command": "PYTHONPATH=backend /home/jayampatel/swe/greenline/backend/.venv/bin/pytest backend/tests/test_settings.py && cd frontend && npx vitest run src/__tests__/SettingsFont.test.tsx src/__tests__/FontProvider.test.tsx && npx tsc --noEmit && npm run lint",
    "result": "PASSED"
  }
}
-->

- **Type / Scope**: `feat(settings)`
- **Summary**: Added Google Fonts "Spline Sans" (and "Spine Sans" alias) to interface typography settings, font provider, CSS variables, and backend validation.
- **Rationale**: Allow users to select Google Fonts Spline Sans / Spine Sans for clean UI and dashboards from the Settings typography selector.
- **Key Changes**:
  - `backend/app/api/routers/settings.py`: Allowed `spline-sans` and `spine-sans` in `app_font` validation and storage.
  - `backend/tests/test_settings.py`: Added test assertions verifying `spline-sans` and `spine-sans` font updates and persistence.
  - `frontend/src/app/layout.tsx`: Loaded `Spline_Sans` via `next/font/google` (`--font-spline-sans`) and added early client script theme/font synchronization.
  - `frontend/src/app/globals.css`: Added CSS selector rules for `[data-font="spline-sans"]`, `[data-font="spine-sans"]`, `.font-spline-sans`, and `.font-spine-sans`.
  - `frontend/src/components/FontProvider.tsx`: Added `spline-sans` and `spine-sans` to `AppFont` type, validation, class toggling, and localStorage persistence.
  - `frontend/src/app/settings/page.tsx`: Added Spline Sans preset card with Google Font badge, preview, and selection handlers.
  - `frontend/src/test/setup.ts`: Added `Spline_Sans` font mock for Next.js google fonts in unit tests.
  - `frontend/src/__tests__/FontProvider.test.tsx` & `SettingsFont.test.tsx`: Added test coverage verifying Spline Sans / Spine Sans selection, DOM application, and backend persistence.
- **Verification**:
  - Command: `PYTHONPATH=backend /home/jayampatel/swe/greenline/backend/.venv/bin/pytest backend/tests/test_settings.py && cd frontend && npx vitest run src/__tests__/SettingsFont.test.tsx src/__tests__/FontProvider.test.tsx && npx tsc --noEmit && npm run lint`
  - Output: All tests passed, TypeScript compiler passed with 0 errors, ESLint passed with 0 errors.

### [2026-11-06 23:26:40 UTC] fix(security): remediate RLS and backup vulnerabilities across backup, cashflow, discrepancies, and auth0 service

<!-- changelog-entry-json
{
  "timestamp": "2026-11-06T23:26:40Z",
  "type": "fix",
  "scope": "security",
  "summary": "remediate RLS and backup vulnerabilities across backup, cashflow, discrepancies, and auth0 service",
  "affected_files": [
    "backend/app/api/routers/backup.py",
    "backend/app/api/routers/cashflow.py",
    "backend/app/api/routers/discrepancies.py",
    "backend/app/services/auth0_service.py",
    "backend/tests/test_rls_adversarial_challenger.py"
  ],
  "rationale": "Restrict administrative backup endpoints to system admin users, enforce category ownership in cashflow transactions, validate funding account ownership during discrepancy resolution, and reject whitespace-only sub claims in Auth0 token verification",
  "breaking_changes": false,
  "verification": {
    "command": "PYTHONPATH=backend /home/jayampatel/swe/greenline/backend/.venv/bin/pytest backend/tests/test_rls_adversarial_challenger.py backend/tests/test_e2e_auth0_rls.py backend/tests/test_auth0_rls.py backend/tests/test_adversarial_security.py -v",
    "result": "PASSED"
  }
}
-->

- **Type / Scope**: `fix(security)`
- **Summary**: Remediate RLS vulnerabilities and harden backup endpoints, cashflow category linking, discrepancy funding accounts, and Auth0 subject validation.
- **Rationale**: Prevent cross-tenant full database dump leakage, unauthorized data deletion via restore/import, cross-tenant category linking in cashflow items, cross-user funding account exploitation in discrepancy resolution, and whitespace-only token claims.
- **Key Changes**:
  - `backend/app/api/routers/backup.py`: Added `_require_admin_user` check enforcing `current_user.user_id == 0` on `/config`, `/list`, `/create`, `/download/{filename}`, `/restore/{filename}`, `/{filename}` (DELETE), and `/import`. Maintained tenant-scoped `/export`.
  - `backend/app/api/routers/cashflow.py`: Added category ownership validation in `create_cashflow_transaction` and `update_cashflow_transaction`, asserting all line items reference categories owned by system (`user_id == 0`) or current user (`user_id == u_id`).
  - `backend/app/api/routers/discrepancies.py`: Added check verifying `item.funding_account_id` exists and belongs to `current_user.user_id`.
  - `backend/app/services/auth0_service.py`: Updated `verify_auth0_token` to validate `not str(sub).strip()`.
  - `backend/tests/test_rls_adversarial_challenger.py`: Updated backup exfiltration test to assert 403 Forbidden for non-admin tenants, added tests for cashflow update category validation, discrepancy funding account ownership validation, and whitespace-only `sub` rejection.
- **Verification**:
  - Command: `PYTHONPATH=backend pytest backend/tests/test_rls_adversarial_challenger.py backend/tests/test_e2e_auth0_rls.py backend/tests/test_auth0_rls.py backend/tests/test_adversarial_security.py -v`
  - Output: 13 passed in test_rls_adversarial_challenger.py, 118 passed across e2e, auth0, and adversarial security suites (100% pass).

### [2026-11-06 23:10:00 UTC] test(auth): add comprehensive adversarial token and security stress test suite

<!-- changelog-entry-json
{
  "timestamp": "2026-11-06T23:10:00Z",
  "type": "test",
  "scope": "auth",
  "summary": "add comprehensive adversarial token and security stress test suite",
  "affected_files": [
    "backend/tests/test_adversarial_security.py"
  ],
  "rationale": "Empirically stress-test Auth0 token validation, signature forgery resistance, algorithm confusion attacks, claims anomalies, malformed headers, and cross-user RLS boundaries under hostile input vectors",
  "breaking_changes": false,
  "verification": {
    "command": "PYTHONPATH=backend /home/jayampatel/swe/greenline/backend/.venv/bin/pytest backend/tests/test_adversarial_security.py -v",
    "result": "PASSED"
  }
}
-->

- **Type / Scope**: `test(auth)`
- **Summary**: Add comprehensive adversarial token and security stress test suite
- **Rationale**: Implement 60 hostile test scenarios evaluating signature forgery resistance (untrusted keys, bit flips, truncation, stripped signatures), algorithm confusion (none variants, HS256 with public key, switched algorithms), boundary anomalies (expired, future iat/nbf, clock skew, mismatched aud/iss, empty sub), header malformations (null bytes, 64KB tokens, nested prefixes), and cross-user RLS/SQLi injection protections.
- **Key Changes**:
  - `backend/tests/test_adversarial_security.py`: Implemented 60 automated adversarial stress tests organized into 5 security test suites.
- **Verification**:
  - Command: `PYTHONPATH=backend /home/jayampatel/swe/greenline/backend/.venv/bin/pytest backend/tests/test_adversarial_security.py -v`
  - Output: `60 passed in 12.80s` (100% passing, zero 500s).

### [2026-11-06 23:05:00 UTC] test(auth): add empirical adversarial RLS and cross-tenant isolation stress test suite

<!-- changelog-entry-json
{
  "timestamp": "2026-11-06T23:05:00Z",
  "type": "test",
  "scope": "auth",
  "summary": "add empirical adversarial RLS and cross-tenant isolation stress test suite",
  "affected_files": [
    "backend/tests/test_rls_adversarial_challenger.py"
  ],
  "rationale": "Empirically stress-test cross-tenant data isolation, IDOR immunity, cross-user entity creation, backup data leakage, and concurrent user provisioning race conditions under simulated hostile tenant attacks",
  "breaking_changes": false,
  "verification": {
    "command": "PYTHONPATH=backend /home/jayampatel/swe/greenline/backend/.venv/bin/pytest backend/tests/test_rls_adversarial_challenger.py -v",
    "result": "PASSED"
  }
}
-->

- **Type / Scope**: `test(auth)`
- **Summary**: Add empirical adversarial RLS and cross-tenant isolation stress test suite
- **Rationale**: Implement adversarial probes covering IDOR CRUD on accounts, transactions, and cashflows; cross-tenant resource linking; backup exfiltration; and JIT provisioning concurrency stress.
- **Key Changes**:
  - `backend/tests/test_rls_adversarial_challenger.py`: Implemented 11 adversarial attack scenarios evaluating cross-tenant boundary protections.
- **Verification**:
  - Command: `PYTHONPATH=backend /home/jayampatel/swe/greenline/backend/.venv/bin/pytest backend/tests/test_rls_adversarial_challenger.py -v`
  - Output: 9 passing tests confirming IDOR immunity and concurrency safety; 2 empirical failures surfacing critical backup database dump exfiltration and cross-tenant category linking.

### [2026-11-06 22:15:00 UTC] feat(frontend): integrate Auth0 SPA authentication, bearer token injection, and user profile UI

<!-- changelog-entry-json
{
  "timestamp": "2026-11-06T22:15:00Z",
  "type": "feat",
  "scope": "frontend",
  "summary": "integrate Auth0 SPA authentication, bearer token injection, and user profile UI",
  "affected_files": [
    "frontend/package.json",
    "frontend/src/components/AuthProvider.tsx",
    "frontend/src/app/layout.tsx",
    "frontend/src/lib/api.ts",
    "frontend/src/app/login/page.tsx",
    "frontend/src/components/Sidebar.tsx",
    "frontend/src/__tests__/Auth0Integration.test.tsx"
  ],
  "rationale": "Wrap root layout with Auth0 SPA provider in AuthProvider.tsx and layout.tsx, configure centralized token management and automatic Bearer token injection with 401 redirection in api.ts, provide Continue with Auth0 primary login in login/page.tsx, and display authenticated user profile (avatar, name, email) with Auth0 logout in Sidebar.tsx",
  "breaking_changes": false,
  "verification": {
    "command": "cd frontend && npx tsc --noEmit && npm run lint && npx vitest run src/__tests__/Auth0Integration.test.tsx src/__tests__/Sidebar.test.tsx && PYTHONPATH=backend /home/jayampatel/swe/greenline/backend/.venv/bin/pytest backend/tests/test_e2e_auth0_rls.py",
    "result": "PASSED"
  }
}
-->

- **Type / Scope**: `feat(frontend)`
- **Summary**: Integrate Auth0 SPA authentication, automatic Bearer token injection, login page redirect, and dynamic user profile display.
- **Rationale**: Connect the frontend Single Page Application to Auth0 authentication, seamlessly attaching access tokens to all outgoing backend API requests, auto-syncing authenticated user profile data, and providing live user identity rendering with secure logout in the navigation sidebar.
- **Key Changes**:
  - `frontend/package.json`: Add `@auth0/auth0-react` dependency.
  - `frontend/src/components/AuthProvider.tsx`: Implement `AuthProvider` wrapping with Auth0 SDK and inner `AuthSync` to register silent token acquisition and trigger `/api/v1/auth/sync`.
  - `frontend/src/app/layout.tsx`: Wrap body layout children in `<AuthProvider>`.
  - `frontend/src/lib/api.ts`: Add `setTokenGetter`, in-memory token state, automatic bearer token injection into headers, and 401 redirect handling.
  - `frontend/src/app/login/page.tsx`: Add primary "Continue with Auth0" action with `loginWithRedirect()`, loading state, and redirect on authentication.
  - `frontend/src/components/Sidebar.tsx`: Render user avatar, name, and email from Auth0 profile, and wire logout button to Auth0 `logout()`.
  - `frontend/src/__tests__/Auth0Integration.test.tsx`: Comprehensive automated unit tests for token injection, 401 redirects, login redirects, sidebar display, and AuthProvider synchronization.
- **Verification**:
  - Command: `cd frontend && npx tsc --noEmit && npm run lint && npx vitest run src/__tests__/Auth0Integration.test.tsx src/__tests__/Sidebar.test.tsx && PYTHONPATH=backend /home/jayampatel/swe/greenline/backend/.venv/bin/pytest backend/tests/test_e2e_auth0_rls.py`
  - Output: 0 TypeScript errors, 0 ESLint errors, 12 passing Vitest unit tests, 40 passing backend E2E RLS tests.

### [2026-11-06 21:18:00 UTC] test(auth): add offline test scaffolding, multi-user pytest fixtures, Auth0 RLS test suite, and env docs

<!-- changelog-entry-json
{
  "timestamp": "2026-11-06T21:18:00Z",
  "type": "test",
  "scope": "auth",
  "summary": "add offline test scaffolding, multi-user pytest fixtures, Auth0 RLS test suite, and env docs",
  "affected_files": [
    "backend/tests/conftest.py",
    "backend/tests/test_auth0_rls.py",
    "frontend/src/test/setup.ts",
    ".env.example"
  ],
  "rationale": "Provide in-memory 2048-bit RSA keypairs and mock JWKS provider for 100% offline testing against Oracle Free 23ai (FREEPDB1), export multi-user fixtures (auth0_client_user_a, auth0_client_user_b, auth0_client_unauthenticated) and mint_auth0_token helper in conftest.py, implement comprehensive test suite in test_auth0_rls.py covering token rejections, JIT user syncing, and RLS isolation, mock @auth0/auth0-react and Figtree in frontend setup.ts, and document Auth0 environment variables in .env.example",
  "breaking_changes": false,
  "verification": {
    "command": "PYTHONPATH=backend /home/jayampatel/swe/greenline/backend/.venv/bin/pytest backend/tests/test_auth0_rls.py backend/tests/test_e2e_auth0_rls.py && cd frontend && npx tsc --noEmit && npm run lint",
    "result": "PASSED"
  }
}
-->

- **Type / Scope**: `test(auth)`
- **Summary**: Add offline test scaffolding, multi-user pytest fixtures, dedicated Auth0 & RLS test suite, frontend vitest mocks, and Auth0 env docs.
- **Rationale**: Ensure 100% offline verification of Auth0 token validation, user profile synchronization, and Row-Level Security isolation across accounts, cashflows, stock transactions, and backups without requiring external live Auth0 tenant credentials.
- **Key Changes**:
  - `backend/tests/conftest.py`: Added in-memory 2048-bit RSA keypairs, `TEST_JWKS`, `ATTACKER_JWKS`, autouse `mock_auth0_jwks` fixture, `mint_auth0_token` custom token minting helper, `auth0_client_user_a`, `auth0_client_user_b`, and `auth0_client_unauthenticated` AsyncClient fixtures while preserving default User 0 `client` fixture for regression-free test execution.
  - `backend/tests/test_auth0_rls.py`: Created dedicated 18-test suite asserting 401 on missing/malformed/expired/tampered/wrong-audience/wrong-issuer tokens, verifying JIT user provisioning and `/auth/sync` profile updates, and validating multi-user RLS isolation across accounts, transactions, cashflows, and backups.
  - `frontend/src/test/setup.ts`: Added global mocks for `@auth0/auth0-react` (`useAuth0` and `Auth0Provider`) and `Figtree` font from `next/font/google`.
  - `.env.example`: Documented backend (`AUTH0_DOMAIN`, `AUTH0_AUDIENCE`, `AUTH0_ISSUER`, `AUTH0_ALGORITHMS`, `AUTH0_TEST_MODE`) and frontend (`NEXT_PUBLIC_AUTH0_DOMAIN`, `NEXT_PUBLIC_AUTH0_CLIENT_ID`, `NEXT_PUBLIC_AUTH0_AUDIENCE`, `NEXT_PUBLIC_AUTH0_REDIRECT_URI`) environment configuration.
- **Verification**:
  - Command: `PYTHONPATH=backend /home/jayampatel/swe/greenline/backend/.venv/bin/pytest backend/tests/test_auth0_rls.py backend/tests/test_e2e_auth0_rls.py && cd frontend && npx tsc --noEmit && npm run lint`
  - Output: 58 passed in backend pytest (18 in test_auth0_rls.py, 40 in test_e2e_auth0_rls.py); 0 errors in frontend TypeScript type check (`tsc --noEmit`) and ESLint (`npm run lint`).

### [2026-11-06 20:38:00 UTC] feat(auth): implement Auth0 RS256 token verification, JIT user injection, profile sync, and RLS hardening

<!-- changelog-entry-json
{
  "timestamp": "2026-11-06T20:38:00Z",
  "type": "feat",
  "scope": "auth",
  "summary": "implement Auth0 RS256 token verification, JIT user injection, profile sync, and RLS hardening",
  "affected_files": [
    "backend/app/config.py",
    "backend/app/services/auth0_service.py",
    "backend/app/api/deps.py",
    "backend/app/api/routers/auth.py",
    "backend/app/api/routers/mcp_router.py",
    "backend/app/api/routers/backup.py",
    "backend/app/schemas/schemas.py",
    "backend/tests/test_row_level_security.py",
    "backend/tests/test_mcp_api_and_keys.py",
    "backend/tests/test_mcp_stock_endpoints.py"
  ],
  "rationale": "Implement Auth0 RS256 token validation against public JWKS with TTL caching and key rotation, wire get_current_user to authenticate Bearer tokens and auto-sync users, add /auth/sync and /auth/me user profile endpoints, and harden query scoping in mcp_router and backup endpoints with user_id",
  "breaking_changes": false,
  "verification": {
    "command": "PYTHONPATH=backend /home/jayampatel/swe/greenline/backend/.venv/bin/pytest backend/tests/test_e2e_auth0_rls.py backend/tests/test_user_persistence.py backend/tests/test_row_level_security.py backend/tests/test_migrations.py backend/tests/test_mcp_api_and_keys.py backend/tests/test_mcp_stock_endpoints.py",
    "result": "PASSED"
  }
}
-->

- **Type / Scope**: `feat(auth)`
- **Summary**: Implement Auth0 RS256 token validation against public JWKS with TTL caching and key rotation, wire `get_current_user` to authenticate Bearer tokens and auto-sync users, add `/auth/sync` and `/auth/me` user profile endpoints, and harden query scoping in `mcp_router` and `backup` endpoints with `user_id`.
- **Rationale**: Complete Milestone 2 of Auth0 production authentication and Row-Level Security, satisfying contracts in `PROJECT.md` and enabling multi-tenant isolation.
- **Key Changes**:
  - `backend/app/config.py`: Added `AUTH0_DOMAIN`, `AUTH0_AUDIENCE`, `AUTH0_ISSUER`, `AUTH0_ALGORITHMS`, and `AUTH0_TEST_MODE` configuration settings.
  - `backend/app/services/auth0_service.py`: Implemented `fetch_jwks`, `get_jwks` with in-memory TTL caching (24h) and single-retry cache-busting, and `verify_auth0_token` verifying RS256 signatures, audience, issuer, expiry, and not-before claims.
  - `backend/app/api/deps.py`: Updated `get_current_user` to validate Auth0 RS256 Bearer tokens, invoke `get_or_sync_auth0_user`, maintain token session cache, and reject unauthenticated or invalid tokens with HTTP 401 Unauthorized.
  - `backend/app/api/routers/auth.py`: Added `POST /api/v1/auth/sync` profile synchronization endpoint and updated `UserResponse` with Auth0 profile fields.
  - `backend/app/schemas/schemas.py`: Updated `UserResponse` with `auth0_sub`, `email`, `name`, `picture`, `updated_at` and defined `UserSyncRequest`.
  - `backend/app/api/routers/mcp_router.py`: Hardened categories, cashflows, and stock queries with `user_id` filtering.
  - `backend/app/api/routers/backup.py`: Scoped `/export` table queries by `current_user.user_id`.
- **Verification**:
  - Command: `PYTHONPATH=backend /home/jayampatel/swe/greenline/backend/.venv/bin/pytest backend/tests/test_e2e_auth0_rls.py backend/tests/test_user_persistence.py backend/tests/test_row_level_security.py backend/tests/test_migrations.py backend/tests/test_mcp_api_and_keys.py backend/tests/test_mcp_stock_endpoints.py`
  - Output: 54 passed, 4 warnings in 36.33s.

### [2026-11-06 20:05:00 UTC] feat(db): implement Auth0 user persistence, schema migration v012, and dividend scoping

<!-- changelog-entry-json
{
  "timestamp": "2026-11-06T20:05:00Z",
  "type": "feat",
  "scope": "db",
  "summary": "implement Auth0 user persistence, schema migration v012, and dividend scoping",
  "affected_files": [
    "backend/app/db/models.py",
    "backend/app/db/migrations.py",
    "backend/app/db/schemas/seed.sql",
    "backend/app/services/auth_service.py",
    "backend/app/services/dividend_engine.py",
    "backend/tests/test_migrations.py",
    "backend/tests/test_user_persistence.py"
  ],
  "rationale": "Add Auth0 profile fields to User model, register migration v012 with Oracle compatibility, implement get_or_sync_auth0_user helper for JIT provisioning and profile synchronization, and fix ExpectedDividend user_id scoping",
  "breaking_changes": false,
  "verification": {
    "command": "PYTHONPATH=backend /home/jayampatel/swe/greenline/backend/.venv/bin/pytest backend/tests/test_migrations.py backend/tests/test_row_level_security.py backend/tests/test_user_persistence.py",
    "result": "PASSED"
  }
}
-->

- **Type / Scope**: `feat(db)`
- **Summary**: Implement Auth0 user persistence, schema migration v012, and dividend scoping.
- **Rationale**: Support production Auth0 authentication and user identity persistence in Oracle database while maintaining 100% backward compatibility for integer primary keys across 16 referencing tables.
- **Key Changes**:
  - `backend/app/db/models.py`: Evolve `User` model with `auth0_sub`, `email`, `name`, `picture`, `updated_at`, relaxed `password_hash` nullability, and flexible `user_id` generation.
  - `backend/app/db/migrations.py`: Register migration `v012_auth0_user_persistence` to relax `password_hash` NOT NULL on Oracle and backfill `updated_at`.
  - `backend/app/db/schemas/seed.sql`: Update `CREATE TABLE users` with Auth0 columns, timestamps, and indexes (`ix_users_auth0_sub`, `ix_users_email`).
  - `backend/app/services/auth_service.py`: Add `get_or_sync_auth0_user` helper supporting lookup by `sub`, account linking by email, profile change synchronization, and concurrent race-condition handling.
  - `backend/app/services/dividend_engine.py`: Scope `ExpectedDividend` creation to `account.user_id`.
  - `backend/tests/test_migrations.py`: Add assertion for `v012_auth0_user_persistence` in migration idempotency test.
  - `backend/tests/test_user_persistence.py`: Add comprehensive unit test suite for User model fields, migration v012, JIT provisioning lifecycle, and ExpectedDividend user scoping.
- **Verification**:
  - Command: `PYTHONPATH=backend /home/jayampatel/swe/greenline/backend/.venv/bin/pytest backend/tests/test_migrations.py backend/tests/test_row_level_security.py backend/tests/test_user_persistence.py`
  - Output: 10 passed in 15.44s.

### [2026-11-06 19:52:00 UTC] test(auth): implement comprehensive 4-tier E2E test suite for Auth0 authentication and Row-Level Security

<!-- changelog-entry-json
{
  "timestamp": "2026-11-06T19:52:00Z",
  "type": "test",
  "scope": "auth",
  "summary": "implement comprehensive 4-tier E2E test suite for Auth0 authentication and Row-Level Security",
  "affected_files": [
    "TEST_INFRA.md",
    "TEST_READY.md",
    "backend/tests/test_e2e_auth0_rls.py"
  ],
  "rationale": "Provide opaque-box test infrastructure and 40 automated tests across 4 tiers verifying Auth0 JWT token validation, user auto-provisioning, and Row-Level Security isolation 100% offline using mock RSA/JWKS against Oracle 23ai",
  "breaking_changes": false,
  "verification": {
    "command": "PYTHONPATH=backend pytest backend/tests/test_e2e_auth0_rls.py --collect-only",
    "result": "PASSED"
  }
}
-->

- **Type / Scope**: `test(auth)`
- **Summary**: Implement comprehensive 4-tier E2E test suite for Auth0 authentication and Row-Level Security.
- **Rationale**: Establish authoritative, opaque-box test infrastructure with 40 requirement-driven tests covering Auth0 RS256 token verification, user profile persistence, and multi-tenant RLS scoping without live external network dependencies.
- **Key Changes**:
  - `TEST_INFRA.md`: Document 4-tier methodology, offline mock RSA/JWKS architecture, multi-tenant isolation harness, and execution runbook.
  - `backend/tests/test_e2e_auth0_rls.py`: Implement 40 executable pytest tests across Tier 1 (Feature Coverage), Tier 2 (Boundaries), Tier 3 (Interactions), and Tier 4 (Real-world scenarios) with offline RSA keypair generator and mock JWKS provider.
  - `TEST_READY.md`: Certify test suite inventory, traceability matrix against requirements R1-R4, and baseline test results.
- **Verification**:
  - Command: `PYTHONPATH=backend /home/jayampatel/swe/greenline/backend/.venv/bin/pytest backend/tests/test_e2e_auth0_rls.py --collect-only`
  - Output: 40 tests collected in 0.28s; baseline execution passes 12 rejection/boundary tests against Oracle Free 23ai (`FREEPDB1`).

### [2026-11-06 18:48:21 UTC] docs(agents): create Archify ERDs for investing and cashflow reporting schemas

<!-- changelog-entry-json
{
  "timestamp": "2026-11-06T18:48:21Z",
  "type": "docs",
  "scope": "agents",
  "summary": "create Archify ERDs for investing and cashflow reporting schemas",
  "affected_files": [
    ".agents/changelog.md",
    ".archify/erd-greenline-schema-20261106-1828/candidate.json",
    ".archify/erd-greenline-schema-20261106-1828/cashflow-candidate.json",
    ".archify/erd-greenline-schema-20261106-1828/cashflow-review-2/greenline-cashflow.browser-check.json",
    ".archify/erd-greenline-schema-20261106-1828/cashflow-review-2/greenline-cashflow.finalize-summary.json",
    ".archify/erd-greenline-schema-20261106-1828/cashflow-review-2/greenline-cashflow.finalize.json",
    ".archify/erd-greenline-schema-20261106-1828/cashflow-review-3/greenline-cashflow.browser-check.json",
    ".archify/erd-greenline-schema-20261106-1828/cashflow-review-3/greenline-cashflow.finalize-summary.json",
    ".archify/erd-greenline-schema-20261106-1828/cashflow-review-3/greenline-cashflow.finalize.json",
    ".archify/erd-greenline-schema-20261106-1828/greenline-cashflow.browser-check.json",
    ".archify/erd-greenline-schema-20261106-1828/greenline-cashflow.delivery.json",
    ".archify/erd-greenline-schema-20261106-1828/greenline-cashflow.finalize-summary.json",
    ".archify/erd-greenline-schema-20261106-1828/greenline-cashflow.finalize.json",
    ".archify/erd-greenline-schema-20261106-1828/greenline-cashflow.html",
    ".archify/erd-greenline-schema-20261106-1828/greenline-erd.delivery-pending.json",
    ".archify/erd-greenline-schema-20261106-1828/greenline-erd.finalize-summary.json",
    ".archify/erd-greenline-schema-20261106-1828/greenline-erd.finalize.json",
    ".archify/erd-greenline-schema-20261106-1828/greenline-investing.browser-check.json",
    ".archify/erd-greenline-schema-20261106-1828/greenline-investing.delivery.json",
    ".archify/erd-greenline-schema-20261106-1828/greenline-investing.finalize-summary.json",
    ".archify/erd-greenline-schema-20261106-1828/greenline-investing.finalize.json",
    ".archify/erd-greenline-schema-20261106-1828/greenline-investing.html",
    ".archify/erd-greenline-schema-20261106-1828/greenline-schema.browser-check.json",
    ".archify/erd-greenline-schema-20261106-1828/greenline-schema.delivery-pending.json",
    ".archify/erd-greenline-schema-20261106-1828/greenline-schema.delivery.json",
    ".archify/erd-greenline-schema-20261106-1828/greenline-schema.finalize-summary.json",
    ".archify/erd-greenline-schema-20261106-1828/greenline-schema.finalize.json",
    ".archify/erd-greenline-schema-20261106-1828/greenline-schema.html",
    ".archify/erd-greenline-schema-20261106-1828/investing-candidate.json",
    ".archify/erd-greenline-schema-20261106-1828/review-2/greenline-schema.finalize-summary.json",
    ".archify/erd-greenline-schema-20261106-1828/review-2/greenline-schema.finalize.json",
    ".archify/erd-greenline-schema-20261106-1828/review-3/greenline-schema.finalize-summary.json",
    ".archify/erd-greenline-schema-20261106-1828/review-3/greenline-schema.finalize.json"
  ],
  "rationale": "Provide navigable, source-backed entity relationship diagrams for all Greenline ORM tables while splitting the large schema into readable domain pages.",
  "breaking_changes": false,
  "verification": {
    "command": "Archify finalize erd (investing and cashflow/reporting); parse all changelog-entry-json blocks with Python json.loads",
    "result": "PASSED"
  }
}
-->

- **Type / Scope**: `docs(agents)`
- **Summary**: Create source-backed investing and cashflow/reporting ERD pages covering all ORM tables and columns.
- **Rationale**: Split the full schema across readable domain diagrams while keeping foreign-key targets and source column comments available.
- **Key Changes**: Added Archify candidates, delivered HTML pages, and verification receipts under `.archify/erd-greenline-schema-20261106-1828/`.
- **Verification**: Both final Archify runs passed validation, delivery, strict check, and browser-check; changelog metadata JSON verified.


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
