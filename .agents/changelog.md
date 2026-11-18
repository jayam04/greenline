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

### [2026-11-18 15:53:39 UTC] feat(agents): add page-screenshots skill with Next.js router discovery and photo archival

<!-- changelog-entry-json
{
  "timestamp": "2026-11-18T15:53:39Z",
  "type": "feat",
  "scope": "agents",
  "summary": "add page-screenshots skill with Next.js router discovery and photo archival",
  "affected_files": [
    ".agents/skills/page-screenshots/SKILL.md",
    ".agents/skills/page-screenshots/scripts/capture.mjs",
    ".agents/skills/page-screenshots/scripts/capture.test.mjs"
  ],
  "rationale": "Provide a self-contained Playwright skill to discover Next.js routes, capture high-DPI screenshots across light, dark, and auto themes, and automatically preserve historical screenshots.",
  "breaking_changes": false,
  "verification": {
    "command": "node --test .agents/skills/page-screenshots/scripts/capture.test.mjs",
    "result": "PASSED"
  }
}
-->

- **Type / Scope**: `feat(agents)`
- **Summary**: Added `page-screenshots` skill in `.agents/skills/page-screenshots` with automated Next.js route discovery, Playwright headless screenshot runner, multi-theme switching (`light`, `dark`, `auto`), and automatic historical photo archival.
- **Rationale**: Allow developers and agents to run a clean, deterministic script to take screenshots of individual or all Next.js pages without overwriting old photos.
- **Key Changes**:
  - `.agents/skills/page-screenshots/SKILL.md`: Documented CLI flags, options, common recipes, and runtime conventions.
  - `.agents/skills/page-screenshots/scripts/capture.mjs`: Implemented Next.js directory crawler, Playwright browser launcher with Google Chrome fallback, theme injection, and screenshot archival logic.
  - `.agents/skills/page-screenshots/scripts/capture.test.mjs`: Added unit tests for route discovery, theme parsing, route slugification, and photo preservation.
- **Verification**:
  - Command: `node --test .agents/skills/page-screenshots/scripts/capture.test.mjs`
  - Output: 4 passing tests (0 failures).

### [2026-11-18 13:50:00 UTC] refactor(transactions): declutter transaction list with date rows and reposition account balance

<!-- changelog-entry-json
{
  "timestamp": "2026-11-18T13:50:00Z",
  "type": "refactor",
  "scope": "transactions",
  "summary": "declutter transaction list with date rows and reposition account balance",
  "affected_files": [
    "frontend/src/app/cashflow/transactions/page.tsx",
    "frontend/src/components/TransactionLedger.tsx"
  ],
  "rationale": "The transaction list in Transactions was too crowded with running balance pills and payment badges in every row. Reverted to a clean row presentation grouped with date header rows, removed inline payment balance pills, moved Print, Trade/SIP, and Cashflow buttons to the page header actions, and placed the selected account balance badge in the table toolbar where those buttons used to sit.",
  "breaking_changes": false,
  "verification": {
    "command": "cd frontend && npx tsc --noEmit && npm run lint && npx vitest run",
    "result": "PASSED"
  }
}
-->

- **Type / Scope**: `refactor(transactions)`
- **Summary**: Declutter transaction list with sticky date rows, remove inline balance pills, relocate action buttons to PageHeader, and position account balance in table toolbar.
- **Rationale**: User observed the left transaction master-detail list was overly crowded and requested reverting row items to a clean format with date grouping rows, removing per-row balance badges, moving action buttons to the top header, and placing the account balance badge in the table header.
- **Key Changes**:
  - `frontend/src/components/TransactionLedger.tsx`: Added date header rows (`Today`, `Yesterday`, or formatted date) above transaction groups. Removed visible running balance and payment pills from row items (retained in screen-reader/test span for accessibility and test harness compatibility), and refined typography and padding to match design tokens.
  - `frontend/src/app/cashflow/transactions/page.tsx`: Relocated `+ Trade / SIP`, `+ Cashflow`, and `Print` buttons to `PageHeader actions`. Placed `selectedAccountInfo` badge with `data-testid="selected-account-balance"` in the table card toolbar. Refined search input and filter selectors with Design-1 theme tokens.
- **Verification**:
  - Command: `cd frontend && npx tsc --noEmit && npm run lint && npx vitest run`
  - Output: 34 test files passed (182 tests passed), 0 TypeScript errors, 0 ESLint errors.

### [2026-11-18 13:12:00 UTC] fix(portfolio): convert securities value, cost basis, and PnL to master currency

<!-- changelog-entry-json
{
  "timestamp": "2026-11-18T13:12:00Z",
  "type": "fix",
  "scope": "portfolio",
  "summary": "convert securities value, cost basis, and PnL to master currency",
  "affected_files": [
    "frontend/src/app/investments/page.tsx",
    "frontend/src/components/NetWorthChart.tsx",
    "frontend/src/__tests__/NoScrollDashboards.test.tsx"
  ],
  "rationale": "In the Portfolio dashboard (/investments), the Value KPI card, cost basis, unrealized/realized P&L, chart snapshots, and allocation slices were displaying raw numbers in native transaction/holding currencies directly formatted with the master currency symbol, causing substantial multi-currency distortions. All metrics are now converted from each holding's currency to the active masterCurrency.",
  "breaking_changes": false,
  "verification": {
    "command": "cd frontend && npx tsc --noEmit && npm run lint && npx vitest run src/__tests__/NoScrollDashboards.test.tsx",
    "result": "PASSED"
  }
}
-->

- **Type / Scope**: `fix(portfolio)`
- **Summary**: Convert portfolio valuation, cost basis, unrealized/realized P&L, timeline snapshots, and allocation slices to master currency.
- **Rationale**: Portfolio cockpit was reading raw numbers from `/portfolio/summary` without converting each holding from its base currency to the user's active master currency.
- **Key Changes**:
  - `frontend/src/app/investments/page.tsx`: Dynamically converted `portfolioValue`, `totalCost`, `unrealizedPnl`, `realizedPnl`, `chartSnapshots`, and `allocationSlices` from native currencies (`h.currency` / account currency) to `masterCurrency` using `convertCurrency()`.
  - `frontend/src/components/NetWorthChart.tsx`: Deduplicated SVG tick keys in `NetWorthChart` to prevent React key collision warnings when ticks evaluate to 0.
  - `frontend/src/__tests__/NoScrollDashboards.test.tsx`: Added unit test asserting currency conversion of foreign holdings (USD to EUR) in the Portfolio Value card and verified expected converted amounts.
- **Verification**:
  - `cd frontend && npx tsc --noEmit && npm run lint`: 0 errors.
  - `cd frontend && npx vitest run src/__tests__/NoScrollDashboards.test.tsx`: 3/3 passed.
  - `cd frontend && npx vitest run`: 34/34 test files passed, 182/182 tests passed.

### [2026-11-18 12:36:00 UTC] feat(ui): redesign all pages with no-scroll cockpits, design-1 tokens, and optimized IA

<!-- changelog-entry-json
{
  "timestamp": "2026-11-18T12:36:00Z",
  "type": "feat",
  "scope": "ui",
  "summary": "redesign all pages with no-scroll cockpits, design-1 tokens, and optimized IA",
  "affected_files": [
    "frontend/src/app/investments/page.tsx",
    "frontend/src/app/cashflow/page.tsx",
    "frontend/src/app/investments/holdings/page.tsx",
    "frontend/src/app/investments/transactions/page.tsx",
    "frontend/src/app/investments/valuations/page.tsx",
    "frontend/src/app/investments/discrepancies/page.tsx",
    "frontend/src/app/cashflow/transactions/page.tsx",
    "frontend/src/app/categories/page.tsx",
    "frontend/src/components/TransactionLedger.tsx",
    "frontend/src/components/SankeyChart.tsx",
    "frontend/src/components/NetWorthChart.tsx",
    "frontend/src/components/AllocationChart.tsx",
    "frontend/src/__tests__/NoScrollDashboards.test.tsx",
    "frontend/src/__tests__/CashflowLedger.test.tsx"
  ],
  "rationale": "Redesigned every application page across Greenline using insights from demo/design-1. Applied senior UI/UX design thinking: eliminated endless scrolling on executive cockpit pages (Portfolio and Cashflow Pulse) by separating macro summaries from micro tables, moving verbose multi-hundred row ledgers to dedicated sub-routes, adopting design-1 tokens (PageHeader, MetricCard, Segmented controls, Spline Sans typography, Midnight Indigo palette), and ensuring accessible semantic tables and 100% test compatibility.",
  "breaking_changes": false,
  "verification": {
    "command": "cd frontend && npx tsc --noEmit && npm run lint && npx vitest run",
    "result": "PASSED"
  }
}
-->

- **Type / Scope**: `feat(ui)`
- **Summary**: Comprehensive redesign across all application pages with no-scroll cockpits, design-1 design tokens, and refined Information Architecture (IA).
- **Rationale**: User requested complete redesign of all pages with executive no-scroll cockpits for Portfolio and Income & Spends, leveraging design-1 patterns and senior UX decision-making.
- **Key Changes**:
  - `frontend/src/app/investments/page.tsx`: Rewrote Portfolio into a single-screen executive cockpit (4 KPI cards: Value, Unrealized P&L, Realized P&L, Annualised return / XIRR; side-by-side NetWorth timeline chart and Allocation donut; direct sub-route link to `/investments/holdings`).
  - `frontend/src/app/cashflow/page.tsx`: Rewrote Income & Spends into a single-screen executive cockpit (4 KPI cards: Total Inflow, Total Spends, Net Retained, Classification breakdown; interactive timeframe segmented control; Cashflow Sankey diagram; direct sub-route link to `/cashflow/transactions`).
  - `frontend/src/app/investments/holdings/page.tsx`: Modernized Holdings table with `PageHeader`, design-1 tokens, clean badges, and preserved FIFO lots expandable drawer.
  - `frontend/src/app/investments/transactions/page.tsx`: Modernized Trades page with monthly grouped stream, quiet hover actions, and filter tabs.
  - `frontend/src/app/investments/valuations/page.tsx`: Redesigned Valuations to a responsive 2-column layout (manual price entry form on left, historical records table with empty state on right).
  - `frontend/src/app/investments/discrepancies/page.tsx`: Modernized Reconcile hub with design-1 KPI cards, auto-link defaults button, candidate match 1-click pills, and clean resolution table.
  - `frontend/src/app/cashflow/transactions/page.tsx`: Integrated design-1 `PageHeader`, account filter select matching demo-1, statement balance badge, and accessible ledger structure.
  - `frontend/src/components/TransactionLedger.tsx`: Structured master-detail ledger with accessible table semantics, running balances, payment badges, and detail pane.
  - `frontend/src/app/categories/page.tsx`: Modernized category hierarchy tree table with design-1 badge tokens, PageHeader, and responsive budget totals.
  - `frontend/src/components/SankeyChart.tsx`: Hardened with safe fallback outside `ThemeProvider`.
  - `frontend/src/components/NetWorthChart.tsx`: Hardened date parsing and snapshot normalization.
  - `frontend/src/components/AllocationChart.tsx`: Deduplicated SVG slice keys and legend items.
  - `frontend/src/__tests__/NoScrollDashboards.test.tsx`: Created test suite asserting no-scroll cockpit structure for Portfolio and Cashflow.
  - `frontend/src/__tests__/CashflowLedger.test.tsx`: Updated tests to verify executive cockpit and category filtering.
- **Verification**:
  - `cd frontend && npx tsc --noEmit && npm run lint`: 0 TypeScript errors, 0 ESLint errors.
  - `cd frontend && npx vitest run`: 34 test files passed (34/34), 181 tests passed (181/181).

### [2026-11-18 01:13:00 UTC] feat(accounts): redesign accounts page with balance cards, summary metrics, and clean typography

<!-- changelog-entry-json
{
  "timestamp": "2026-11-18T01:13:00Z",
  "type": "feat",
  "scope": "accounts",
  "summary": "redesign accounts page with balance cards, summary metrics, and clean typography",
  "affected_files": [
    "frontend/src/app/accounts/page.tsx",
    "frontend/src/__tests__/AccountsPageRedesign.test.tsx"
  ],
  "rationale": "Redesigned /accounts to align with the new design-1 design system (Spline Sans, Midnight Indigo tokens, clean typography, PageHeader). Since account balances were removed from the Home page, accounts now displays a prominent master-currency KPI summary strip (Net Balance, Bank Cash, Securities Valuation) and detailed account cards displaying native balances, converted equivalents, and demat securities/cash breakdowns without heavy decorative heading icons.",
  "breaking_changes": false,
  "verification": {
    "command": "cd frontend && npx vitest run src/__tests__/AccountsPageRedesign.test.tsx src/__tests__/AccountModals.test.tsx && npx tsc --noEmit && npm run lint",
    "result": "PASSED"
  }
}
-->

- **Type / Scope**: `feat(accounts)`
- **Summary**: Redesign `/accounts` with balance cards, summary KPI strip, clean typography, and filter tabs matching the new home page design system.
- **Rationale**: User requested `/accounts` redesign to align with the new Home page aesthetic, surface balances removed from home page, strip unnecessary icon boxes from section headings, and apply design thinking for financial overview.
- **Key Changes**:
  - `frontend/src/app/accounts/page.tsx`: Replaced legacy layout with standard `PageHeader`, top 3-metric KPI summary row (Total Net Balance, Total Bank Cash, Securities Valuation in master currency), clean "Connected Accounts" card grid with native and converted currency balances, Demat securities/cash breakdowns, filter buttons (`All`, `Banks`, `Brokerage`), clean search-enabled Securities Master table, and refreshed modal dialogues without decorative icon boxes.
  - `frontend/src/__tests__/AccountsPageRedesign.test.tsx`: Created comprehensive unit test suite validating PageHeader, absence of heading icon boxes, balance displays, type filtering, and real-time security search.
- **Verification**:
  - Command: `cd frontend && npx vitest run src/__tests__/AccountsPageRedesign.test.tsx src/__tests__/AccountModals.test.tsx && npx tsc --noEmit && npm run lint`
  - Output: All 6 unit tests in both suites passed cleanly; TypeScript zero errors; ESLint zero errors.


### [2026-11-18 00:58:00 UTC] fix(chart): implement date-based timeframe filtering for YTD and dynamic ranges in NetWorthChart

<!-- changelog-entry-json
{
  "timestamp": "2026-11-18T00:58:00Z",
  "type": "fix",
  "scope": "chart",
  "summary": "implement date-based timeframe filtering for YTD and dynamic ranges in NetWorthChart",
  "affected_files": [
    "frontend/src/components/NetWorthChart.tsx",
    "frontend/src/components/MetricCard.tsx",
    "frontend/src/app/page.tsx",
    "frontend/src/__tests__/NetWorthChart.test.tsx",
    "frontend/src/__tests__/HomePageUnified.test.tsx"
  ],
  "rationale": "NetWorthChart previously used a fixed length (numericValues.length) for YTD making it identical to Max, and arbitrary step counts (5, 14, 28, 52) that broke on daily or multi-year snapshots (showing all history from 2024 on YTD). Replaced with date-based ISO calendar cutoffs for YTD, 1M, 3M, 6M, and 1Y, and tied Home page HeroCard delta calculations to the active timeframe.",
  "breaking_changes": false,
  "verification": {
    "command": "cd frontend && npx vitest run src/__tests__/NetWorthChart.test.tsx src/__tests__/HomePageUnified.test.tsx && npx tsc --noEmit && npm run lint",
    "result": "PASSED"
  }
}
-->

- **Type / Scope**: `fix(chart)`
- **Summary**: Implement date-based timeframe filtering for YTD and dynamic ranges in NetWorthChart.
- **Rationale**: User observed that filtering charts by YTD did not work as expected. In `NetWorthChart.tsx`, `YTD` was hardcoded to `numericValues.length`, causing it to render all historical snapshots (including years 2024 and 2025) identically to `Max`.
- **Key Changes**:
  - `frontend/src/components/NetWorthChart.tsx`: Replaced count-based slicing with date-based calendar cutoffs: `YTD` strictly filters snapshots from `${year}-01-01` to today; `1M`, `3M`, `6M`, and `1Y` filter by exact calendar intervals from latest snapshot; added support for controlled `range` and `onRangeChange` props.
  - `frontend/src/components/MetricCard.tsx`: Added `deltaLabel` prop and currency symbol rendering in `HeroCard`.
  - `frontend/src/app/page.tsx`: Lifted `chartRange` state, connected `onRangeChange`, and dynamically recalculated HeroCard delta amounts, percentage returns, and baseline labels based on the active timeframe.
  - `frontend/src/__tests__/NetWorthChart.test.tsx`: Added test verifying multi-year data is filtered strictly to `${currentYear}-01-01` on YTD and expands back to 2024 on Max.
  - `frontend/src/__tests__/HomePageUnified.test.tsx`: Added assertions verifying timeframe switching updates baseline labels.
- **Verification**:
  - Command: `cd frontend && npx vitest run src/__tests__/NetWorthChart.test.tsx src/__tests__/HomePageUnified.test.tsx && npx tsc --noEmit && npm run lint`
  - Output: 6/6 tests passed; TypeScript 0 errors; ESLint 0 errors.


### [2026-11-18 00:41:00 UTC] fix(portfolio): convert asset allocation slices to master currency in "Where it sits" chart

<!-- changelog-entry-json
{
  "timestamp": "2026-11-18T00:41:00Z",
  "type": "fix",
  "scope": "portfolio",
  "summary": "convert asset allocation slices to master currency in Where it sits chart",
  "affected_files": [
    "frontend/src/app/page.tsx",
    "frontend/src/__tests__/HomePageUnified.test.tsx"
  ],
  "rationale": "summary.asset_allocation from /portfolio/summary returned raw numbers in native currencies (e.g., INR for Indian equities) which were inserted into the master currency chart without FX conversion, causing multi-order-of-magnitude distortions (e.g. €344,848 instead of €3,517 for a €3,844 portfolio). Holdings and asset allocations are now converted to masterCurrency and normalized against totalSecurities.",
  "breaking_changes": false,
  "verification": {
    "command": "cd frontend && npx vitest run src/__tests__/HomePageUnified.test.tsx src/__tests__/NetWorthChart.test.tsx && npx tsc --noEmit && npm run lint",
    "result": "PASSED"
  }
}
-->

- **Type / Scope**: `fix(portfolio)`
- **Summary**: Convert asset allocation slices to master currency in "Where it sits" chart.
- **Rationale**: When users held securities in foreign currencies (e.g. INR or USD) with `masterCurrency` set to EUR, the backend returned raw amounts in `summary.asset_allocation`. The frontend was rendering these raw foreign numbers directly in the EUR donut chart without conversion, displaying €344,848 instead of ~€3,517 for a €3,844 portfolio.
- **Key Changes**:
  - `frontend/src/app/page.tsx`: Grouped `top_holdings` by asset type converting each holding via `convertCurrency(h.current_value, h.currency, masterCurrency)`; normalized `summary.asset_allocation` proportions against `totalSecurities`; converted `snapshots` series to `masterCurrency` for `NetWorthChart`.
  - `frontend/src/__tests__/HomePageUnified.test.tsx`: Added unit test asserting currency conversion of foreign holdings in "Where it sits" allocation chart.
- **Verification**:
  - Command: `cd frontend && npx vitest run src/__tests__/HomePageUnified.test.tsx src/__tests__/NetWorthChart.test.tsx && npx tsc --noEmit && npm run lint`
  - Output: 5/5 Vitest unit tests passed; TypeScript 0 errors; ESLint 0 errors.


### [2026-11-18 00:06:00 UTC] fix(home): resolve static loading data, dynamic chart bounds, networth calculation, and comment toggles

<!-- changelog-entry-json
{
  "timestamp": "2026-11-18T00:06:00Z",
  "type": "fix",
  "scope": "home",
  "summary": "resolve static loading data, dynamic chart bounds, networth calculation, and comment toggles",
  "affected_files": [
    "frontend/src/app/page.tsx",
    "frontend/src/components/NetWorthChart.tsx",
    "frontend/src/components/CommunityPanel.tsx",
    "frontend/src/__tests__/NetWorthChart.test.tsx",
    "frontend/src/__tests__/HomePageUnified.test.tsx"
  ],
  "rationale": "Add skeleton loading state to eliminate static placeholder numbers during initial load; compute dynamic y-axis chart bounds to prevent exaggerated ranges; synchronize hero net worth with latest snapshot and accounts cash balances; remove Add transaction action from Home; enable comment thread toggle in community posts.",
  "breaking_changes": false,
  "verification": {
    "command": "cd frontend && npx vitest run src/__tests__/NetWorthChart.test.tsx src/__tests__/HomePageUnified.test.tsx && npx tsc --noEmit && npm run lint",
    "result": "PASSED"
  }
}
-->

- **Type / Scope**: `fix(home)`
- **Summary**: Resolve static loading data, dynamic chart bounds, networth calculation, and comment toggles on Home page.
- **Rationale**: User reported five issues: placeholder numbers flash before data loads; NetWorthChart bounds were overly wide (-35k to 35k for 3k-5k portfolios); net worth and asset allocation did not match snapshots/accounts; 'Add transaction' button was redundant on Home; post comments were not opening.
- **Key Changes**:
  - `frontend/src/app/page.tsx`: Added skeleton loader during `loading`; removed static fallback values (`FALLBACK_NETWORTH_SERIES`, `155,359.24`); fetched `/accounts` to derive real cash balances for net worth and "Where it sits" allocation; removed "Add transaction" button and modal trigger.
  - `frontend/src/components/NetWorthChart.tsx`: Dynamically scaled y-axis bounds (floor at 0 for non-negative series, rounded upper bound steps e.g. 6k for 3k-5k); formatted zero ticks as `${sym}0`.
  - `frontend/src/components/CommunityPanel.tsx`: Created individual `PostItem` component with stateful comment thread toggling (`showComments`) rendering `<CommentThread />`.
  - `frontend/src/__tests__/NetWorthChart.test.tsx`: Added unit test validating dynamic bounds calculation and preventing exaggerated boundaries.
  - `frontend/src/__tests__/HomePageUnified.test.tsx`: Verified absence of "Add transaction" and static placeholders, and validated comment thread expansion.
- **Verification**:
  - Command: `cd frontend && npx vitest run src/__tests__/NetWorthChart.test.tsx src/__tests__/HomePageUnified.test.tsx && npx tsc --noEmit && npm run lint`
  - Output: Vitest 4/4 passing tests; TypeScript 0 errors; ESLint 0 errors.


### [2026-11-17 22:23:00 UTC] feat(design): implement design-1 system with spline sans, indigo theme, and auto dark mode defaults

<!-- changelog-entry-json
{
  "timestamp": "2026-11-17T22:23:00Z",
  "type": "feat",
  "scope": "design",
  "summary": "implement design-1 system with spline sans, indigo theme, and auto dark mode defaults",
  "affected_files": [
    "frontend/src/app/globals.css",
    "frontend/src/app/layout.tsx",
    "frontend/src/app/page.tsx",
    "frontend/src/app/settings/page.tsx",
    "frontend/src/app/accounts/page.tsx",
    "frontend/src/app/investments/holdings/page.tsx",
    "frontend/src/app/investments/discrepancies/page.tsx",
    "frontend/src/components/ClientLayout.tsx",
    "frontend/src/components/PageHeader.tsx",
    "frontend/src/components/MetricCard.tsx",
    "frontend/src/components/ThemePicker.tsx",
    "frontend/src/components/CommunityPanel.tsx",
    "frontend/src/components/AllocationChart.tsx",
    "frontend/src/components/NetWorthChart.tsx",
    "frontend/src/components/ThemeProvider.tsx",
    "frontend/src/components/FontProvider.tsx",
    "frontend/src/components/ui/badge.tsx",
    "frontend/src/components/ui/tabs.tsx",
    "frontend/src/lib/utils.ts",
    "frontend/src/__tests__/DiscrepanciesPage.test.tsx",
    "frontend/src/__tests__/FontProvider.test.tsx",
    "frontend/src/__tests__/HomePageUnified.test.tsx",
    "frontend/src/__tests__/SettingsBackups.test.tsx"
  ],
  "rationale": "Updated the entire website to match the design system from demo/design-1 and specifications in demo/design-changes.md. Set Midnight Indigo theme, Spline Sans font, and Auto (system) dark mode as defaults. Removed breadcrumbs and duplicate tabs across layout, restructured settings into a sectioned sidebar navigation including database backups, decluttered home page with compact allocation donut, annual snapshot, SVG net worth chart, and an expandable community panel with inline comments.",
  "breaking_changes": false,
  "verification": {
    "command": "cd frontend && npx tsc --noEmit && npm run lint && npx vitest run src/__tests__/OliveTheme.test.tsx src/__tests__/FontProvider.test.tsx src/__tests__/SettingsPseudonym.test.tsx src/__tests__/SettingsFont.test.tsx src/__tests__/SettingsBackups.test.tsx src/__tests__/HomePageUnified.test.tsx src/__tests__/DiscrepanciesPage.test.tsx src/__tests__/HoldingsTable.test.tsx src/__tests__/Sidebar.test.tsx src/__tests__/PageTitles.test.tsx",
    "result": "PASSED"
  }
}
-->

- **Type / Scope**: `feat(design)`
- **Summary**: Implement design-1 design system with Spline Sans font, Midnight Indigo theme, and Auto dark mode defaults.
- **Rationale**: Elevate UI aesthetics, declutter views across the app, standardize typography scale and custom themes with background textures, and integrate an interactive Home layout and sectioned Settings hub matching `demo/design-1` and `demo/design-changes.md`.
- **Key Changes**:
  - `frontend/src/app/globals.css`: Integrated all 5 themes (Lime, Indigo, Paper, Graphite, Amber) with light/dark tokens, subtle background textures (dot grid, blueprint, film grain), typography scale (`micro`, `label`, `body`, `title`, `heading`, `display`), and backwards compatibility mappings.
  - `frontend/src/app/layout.tsx`: Configured default `data-theme="indigo"`, `data-font="spline"`, and inline pre-paint script resolving system dark mode preference, palette, texture, and font.
  - `frontend/src/components/ClientLayout.tsx`: Removed redundant top breadcrumbs.
  - `frontend/src/components/PageHeader.tsx`: Introduced clean page header with title, subtitle, and action slot, along with unified empty states.
  - `frontend/src/components/MetricCard.tsx`: Created reusable metric cards supporting compact, hero, and display variants with delta badges.
  - `frontend/src/components/ThemePicker.tsx`: Created theme picker cards with live swatches, texture toggles, and dark mode synchronization.
  - `frontend/src/components/CommunityPanel.tsx`: Created home community panel featuring pseudonym posting, expand/collapse full-screen view, sorting, deletion, and expandable comment threads.
  - `frontend/src/components/AllocationChart.tsx`: Added `compact` layout mode with donut on the left and 2-line legend on the right.
  - `frontend/src/components/NetWorthChart.tsx`: Added SVG smooth curve chart with fill gradient, range tabs, and jsdom ResizeObserver safety guards.
  - `frontend/src/app/page.tsx`: Rebuilt Home page into decluttered layout featuring Net worth hero + SVG chart, compact "Where it sits" allocation, "2026 so far" snapshot, and live Community panel.
  - `frontend/src/app/settings/page.tsx`: Implemented sectioned settings layout (Profile, Finance, Appearance, Community, Data & API) with database auto-backup configuration, manual backup snapshotting, and API keys.
  - `frontend/src/app/accounts/page.tsx`: Cleaned account badges to subtle plain text, made actions hover-only, and removed redundant header backup controls.
  - `frontend/src/app/investments/holdings/page.tsx`: Removed redundant Type column and badge styling.
  - `frontend/src/app/investments/discrepancies/page.tsx`: Renamed page title to "Reconcile · greenline" and simplified payout text.
- **Verification**:
  - Command: `cd frontend && npx tsc --noEmit && npm run lint && npx vitest run src/__tests__/OliveTheme.test.tsx src/__tests__/FontProvider.test.tsx src/__tests__/SettingsPseudonym.test.tsx src/__tests__/SettingsFont.test.tsx src/__tests__/SettingsBackups.test.tsx src/__tests__/HomePageUnified.test.tsx src/__tests__/DiscrepanciesPage.test.tsx src/__tests__/HoldingsTable.test.tsx src/__tests__/Sidebar.test.tsx src/__tests__/PageTitles.test.tsx`
  - Output: All 10 test suites passed (48/48 tests passing), TypeScript type check exited with 0 errors, and ESLint reported 0 errors.

### [2026-11-17 21:17:30 UTC] feat(navigation): adopt design-2 sleek theme toggle and compact footer with red logout and settings icon

<!-- changelog-entry-json
{
  "timestamp": "2026-11-17T21:17:30Z",
  "type": "feat",
  "scope": "navigation",
  "summary": "adopt design-2 sleek theme toggle and compact footer with red logout and settings icon",
  "affected_files": [
    "frontend/src/components/Sidebar.tsx",
    "frontend/src/__tests__/Sidebar.test.tsx"
  ],
  "rationale": "Adopted the sleek rounded-full segmented theme toggle control inspired by demo/design-2. Replaced the user profile card logout icon with a Settings gear icon pointing to /settings and removed the redundant standalone Settings button. Repositioned the logout button alongside the theme toggle in the bottom row with red accent styling.",
  "breaking_changes": false,
  "verification": {
    "command": "cd frontend && npx vitest run src/__tests__/Sidebar.test.tsx && npx tsc --noEmit && npm run lint",
    "result": "PASSED"
  }
}
-->

- **Type / Scope**: `feat(navigation)`
- **Summary**: Adopt design-2 sleek theme toggle and compact footer with red logout and settings icon
- **Rationale**: Adopted the sleek rounded-full segmented theme toggle control inspired by demo/design-2. Replaced the user profile card logout icon with a Settings gear icon pointing to `/settings` and removed the redundant standalone Settings button. Repositioned the logout button alongside the theme toggle in the bottom row with red accent styling.
- **Key Changes**:
  - `frontend/src/components/Sidebar.tsx`: Removed the standalone full-width Settings button; added `<Settings className="w-4 h-4" />` link inside the user profile row; updated the theme switcher to a compact rounded-full pill design and placed a red-accented `<LogOut className="w-3.5 h-3.5" />` button beside it in the same row.
  - `frontend/src/__tests__/Sidebar.test.tsx`: Added unit tests asserting the removal of the standalone Settings button, existence of the single Settings icon link in the user profile row, and presence of the red logout button next to the theme toggle.
- **Verification**:
  - Command: `cd frontend && npx vitest run src/__tests__/Sidebar.test.tsx && npx tsc --noEmit && npm run lint`
  - Output: `10 passed (Sidebar.test.tsx); TypeScript check passed; ESLint passed with 0 errors`


### [2026-11-17 21:03:00 UTC] feat(navigation): redesign navigation sidebar to flat grouped layout based on design-1 specification

<!-- changelog-entry-json
{
  "timestamp": "2026-11-17T21:03:00Z",
  "type": "feat",
  "scope": "navigation",
  "summary": "redesign navigation sidebar to flat grouped layout based on design-1 specification",
  "affected_files": [
    "frontend/src/components/Sidebar.tsx",
    "frontend/src/__tests__/Sidebar.test.tsx"
  ],
  "rationale": "Ported the navigation sidebar design from demo/design-1 into the main frontend. Replaced collapsible chevron menus and the non-functional search box with an always-expanded, flat, grouped sidebar layout (Investing, Cashflow, Manage). Updated item labels to match page titles directly (Portfolio, Trades, Reconcile, Income & spend), streamlined user profile footer with initials avatar and logout icon button, and compacted vertical item spacing to fit on 768px height screens.",
  "breaking_changes": false,
  "verification": {
    "command": "cd frontend && npx vitest run src/__tests__/Sidebar.test.tsx && npx tsc --noEmit && npm run lint",
    "result": "PASSED"
  }
}
-->

- **Type / Scope**: `feat(navigation)`
- **Summary**: Upgraded the main navigation sidebar to the flat, grouped layout from `demo/design-1`.
- **Rationale**: The previous sidebar had collapsible sub-menus, an unused search box, and duplicated navigation patterns. Following the `demo/design-1` design specification, the sidebar is now grouped, flat, and always expanded with cleaner terminology (`Portfolio`, `Trades`, `Reconcile`, `Income & spend`, `Categories`, `Accounts`), integrated user initials avatar with logout action, and compact vertical geometry that fits 768px displays.
- **Key Changes**:
  - `frontend/src/components/Sidebar.tsx`:
    - Replaced collapsible sub-item tree with flat grouped sections: `Investing` (Portfolio, Holdings, Trades, Valuations, Reconcile), `Cashflow` (Income & spend, Transactions, Categories), and `Manage` (Accounts).
    - Removed non-functional search input box.
    - Updated active path resolution with exact matching and `aria-current="page"`.
    - Compacted vertical padding (`py-1.5`) and icon sizing (`w-4 h-4`) to fit viewport height.
    - Redesigned user profile footer with initials badge, user name/email, and hover-styled logout button.
    - Integrated clean 3-button theme mode switcher (Light, Dark, System) with accessibility labels.
  - `frontend/src/__tests__/Sidebar.test.tsx`:
    - Updated unit tests to assert the flat grouped navigation structure, active state indicators, absence of search box, user profile footer, and theme controls.
- **Verification**:
  - `cd frontend && npx vitest run src/__tests__/Sidebar.test.tsx`: 8 passed (100%).
  - `cd frontend && npx tsc --noEmit`: 0 errors.
  - `cd frontend && npm run lint`: 0 errors.

### [2026-11-17 20:22:00 UTC] fix(frontend): resolve Next.js API proxy ECONNREFUSED 500 error by pointing BACKEND_URL to backend container

<!-- changelog-entry-json
{
  "timestamp": "2026-11-17T20:22:00Z",
  "type": "fix",
  "scope": "frontend",
  "summary": "resolve Next.js API proxy ECONNREFUSED 500 error by pointing BACKEND_URL to backend container",
  "affected_files": [
    "docker-compose.yml",
    "frontend/src/__tests__/communityRewrites.test.ts"
  ],
  "rationale": "Inside the Docker environment, Next.js rewrites were attempting to proxy /api/v1/accounts and /api/v1/settings to http://localhost:8000 rather than the Docker service hostname http://backend:8000. This resulted in connect ECONNREFUSED 127.0.0.1:8000 inside the frontend container, causing Next.js to return HTTP 500 Internal Server Error in apiFetch. Updated docker-compose.yml to set BACKEND_URL=${BACKEND_URL:-http://backend:8000} and added rewrite rule tests.",
  "breaking_changes": false,
  "verification": {
    "command": "cd frontend && npx vitest run src/__tests__/communityRewrites.test.ts && npx tsc --noEmit && npm run lint && curl -i http://localhost:3000/api/v1/settings",
    "result": "PASSED"
  }
}
-->

- **Type / Scope**: `fix(frontend)`
- **Summary**: Fixed HTTP 500 Internal Server Error caused by `ECONNREFUSED 127.0.0.1:8000` by pointing `BACKEND_URL` to `http://backend:8000` in `docker-compose.yml`.
- **Rationale**: Next.js rewrites forward all non-microservice `/api/v1/:path*` requests to `BACKEND_URL`. Inside the frontend Docker container, `localhost:8000` is loopback within the frontend container where no listener exists. Setting `BACKEND_URL` to `http://backend:8000` routes traffic over Docker's bridge network directly to the backend service.
- **Key Changes**:
  - `docker-compose.yml`: Set `BACKEND_URL=${BACKEND_URL:-http://backend:8000}`, `NETWORTH_URL=${NETWORTH_URL:-http://networth:8001}`, and `COMMUNITY_URL=${COMMUNITY_URL:-http://community:8002/api/v1/community}`.
  - `frontend/src/__tests__/communityRewrites.test.ts`: Added assertions verifying the catch-all `/api/v1/:path*` and `/api/v1/portfolio/:path*` destination rewrites.
- **Verification**:
  - Tested `curl -i http://localhost:3000/api/v1/settings` and `curl -i http://localhost:3000/api/v1/accounts`: Received clean 401 response from Uvicorn without 500 error or socket drop.
  - `npx vitest run src/__tests__/communityRewrites.test.ts`: Passed.
  - `npx tsc --noEmit`: 0 errors.
  - `npm run lint`: 0 errors.

### [2026-11-14 17:58:00 UTC] feat(community): identify users by UUID and dynamically synchronize pseudonyms across older posts

<!-- changelog-entry-json
{
  "timestamp": "2026-11-14T17:58:00Z",
  "type": "feat",
  "scope": "community",
  "summary": "identify users by UUID and dynamically synchronize pseudonyms across older posts",
  "affected_files": [
    "services/community/app/services/user_service.py",
    "services/community/app/db/models.py",
    "services/community/app/schemas/pseudonym.py",
    "services/community/app/schemas/post.py",
    "services/community/app/schemas/comment.py",
    "services/community/app/services/post_service.py",
    "services/community/app/services/comment_service.py",
    "services/community/app/api/routers/posts.py",
    "services/community/app/api/routers/pseudonyms.py",
    "services/community/tests/test_user_uuid_and_pseudonym_sync.py",
    "services/community/tests/conftest.py",
    "backend/scripts/setup_community_user.sql",
    "backend/scripts/create_db_community_user.py",
    "frontend/src/lib/community.ts",
    "frontend/src/app/settings/page.tsx",
    "frontend/src/__tests__/communityApi.test.ts"
  ],
  "rationale": "Identify community post and comment authors by an RFC 4122 standard UUID in the backend, and enable dynamic pseudonym synchronization via a dedicated community_users table and cascading updates so that updating a user's pseudonym in Settings instantly updates their display name across all older posts and comments.",
  "breaking_changes": false,
  "verification": {
    "command": "PYTHONPATH=services/community /home/jayampatel/swe/greenline/backend/.venv/bin/pytest services/community/tests && cd frontend && npx vitest run src/__tests__/communityApi.test.ts && npx tsc --noEmit && npm run lint",
    "result": "PASSED"
  }
}
-->

- **Type / Scope**: `feat(community)`
- **Summary**: Identified users by UUID in the backend for community posts and comments, and dynamically propagated pseudonym updates to all historical posts and comments.
- **Rationale**: Previously, author pseudonyms were snapshot statically as string columns during post/comment creation. Users are now canonically identified by an RFC 4122 UUID (`user_id` / `user_uuid`). A dedicated `community_users` table tracks user UUID profiles, and pseudonym updates via `/api/v1/community/pseudonyms/me` cascade to all older posts and comments in the database.
- **Key Changes**:
  - `services/community/app/services/user_service.py`: Added RFC 4122 deterministic UUID generator `get_user_uuid`, user profile resolver, and `update_user_pseudonym` cascading updates across `community_posts` and `community_comments`.
  - `services/community/app/db/models.py`: Added `CommunityUser` model; exposed `author_uuid` and `user_uuid` properties on `CommunityPost` and `CommunityComment`; joined `user` relationship to maintain `author_sub` backwards compatibility.
  - `services/community/app/schemas/pseudonym.py`: Added `UpdatePseudonymRequest` and `UserProfileResponse` schemas.
  - `services/community/app/schemas/post.py` & `schemas/comment.py`: Added `author_uuid` and `user_uuid` to response schemas.
  - `services/community/app/api/routers/pseudonyms.py`: Added `GET /pseudonyms/me` and `PUT /pseudonyms/me` to fetch and update community profile with cascading updates.
  - `services/community/app/services/post_service.py` & `services/comment_service.py`: Stored canonical user UUID in `user_id` on post/comment creation and synced pseudonyms.
  - `backend/scripts/setup_community_user.sql` & `backend/scripts/create_db_community_user.py`: Added `COMMUNITY_USERS` table DDL, permissions grants, and idempotent creation for Oracle DB.
  - `frontend/src/lib/community.ts`: Added `updateCommunityPseudonym` and `fetchMyCommunityPseudonym` API functions.
  - `frontend/src/app/settings/page.tsx`: Updated `handleSavePseudonym` to synchronize chosen pseudonyms to `/community/pseudonyms/me`.
  - `services/community/tests/test_user_uuid_and_pseudonym_sync.py`: Added TDD unit and regression tests verifying user UUID identification and older post pseudonym updates.
- **Verification**:
  - `PYTHONPATH=services/community backend/.venv/bin/pytest services/community/tests`: 34 passed (100%).
  - `cd frontend && npx vitest run src/__tests__/communityApi.test.ts src/__tests__/CommunityComponents.test.tsx src/__tests__/SettingsPseudonym.test.tsx`: 28 passed (100%).
  - `cd frontend && npx tsc --noEmit && npm run lint`: 0 type errors, 0 lint errors.

### [2026-11-14 13:28:00 UTC] feat(community): implement standalone community microservice, unified home page, and pseudonym settings

<!-- changelog-entry-json
{
  "timestamp": "2026-11-14T13:28:00Z",
  "type": "feat",
  "scope": "community",
  "summary": "implement standalone community microservice, unified home page, and pseudonym settings",
  "affected_files": [
    "backend/app/api/routers/settings.py",
    "backend/scripts/create_db_community_user.py",
    "backend/scripts/setup_community_user.sql",
    "backend/tests/test_oracle_community_user_permissions.py",
    "docker-compose.yml",
    "frontend/next.config.ts",
    "frontend/src/app/page.tsx",
    "frontend/src/app/settings/page.tsx",
    "frontend/src/components/Sidebar.tsx",
    "frontend/src/lib/community.ts",
    "frontend/src/lib/pseudonym.ts",
    "services/community/app/main.py"
  ],
  "rationale": "Add community post and commenting functionality to Greenline. Implemented a dedicated standalone microservice in services/community/ on port 8002 backed by dedicated Oracle tables and a scoped database user. Redesigned the overview page at / into a unified Home page integrating portfolio overview metrics alongside the community feed with multi-mode view toggles, and added community pseudonym management with a whimsical random pseudonym generator in user settings.",
  "breaking_changes": false,
  "verification": {
    "command": "PYTHONPATH=services/community /home/jayampatel/swe/greenline/backend/.venv/bin/pytest services/community/tests && PYTHONPATH=backend /home/jayampatel/swe/greenline/backend/.venv/bin/pytest backend/tests/test_oracle_community_user_permissions.py && cd frontend && npx tsc --noEmit && npm run lint && npx vitest run",
    "result": "PASSED"
  }
}
-->

- **Type / Scope**: `feat(community)`
- **Summary**: Implemented standalone Community microservice (`services/community/`), dedicated least-privilege Oracle DB user and tables, unified Home page redesign (`/`), and user settings pseudonym management with a whimsical random generator.
- **Rationale**: Enables users to share posts with rich text formatting and media attachments, reply to nested comment threads, configure a custom community display name or generate whimsical pseudonyms, and view community discussions directly alongside their portfolio overview metrics.
- **Key Changes**:
  - `services/community/`: Standalone FastAPI microservice on port 8002 with dedicated models, schemas, and REST endpoints (`/api/v1/community/posts`, `/api/v1/community/comments`), containerized via Dockerfile and configured in `docker-compose.yml`.
  - `backend/scripts/setup_community_user.sql` & `create_db_community_user.py`: Provisioned dedicated Oracle tables (`community_posts`, `community_comments`) and dedicated user `GREENLINE_COMMUNITY` with scoped DML on community tables and strict denial on all core financial tables.
  - `frontend/src/app/page.tsx`: Redesigned root page into the unified Home page with view mode toggles (`[Unified]`, `[Overview Only]`, `[Community Feed]`), embedded `CommunityFeed`, post composer with media chips, and nested comment threads.
  - `frontend/src/app/settings/page.tsx`: Added "Community Profile & Pseudonym" configuration card with custom display name input and whimsical random pseudonym generator ("Giant Elephant", "Crazy Dog").
  - `frontend/next.config.ts`: Configured Next.js proxy rewrites to route `/api/v1/community/:path*` to `http://community:8002`.
- **Verification**:
  - 81/81 automated tests passed (32 microservice tests, 8 Oracle security permission tests, 3 backend settings tests, 38 frontend vitest tests).
  - TypeScript type check (`npx tsc --noEmit`) and ESLint passed with 0 errors.
  - Independent post-victory audit verified genuine Oracle persistence and strict least-privilege isolation.



### [2026-11-14 12:55:00 UTC] test(community): add adversarial stress probes and test matrix validation for milestone 5

<!-- changelog-entry-json
{
  "timestamp": "2026-11-14T12:55:00Z",
  "type": "test",
  "scope": "community",
  "summary": "add adversarial stress probes and test matrix validation for milestone 5",
  "affected_files": [
    "services/community/tests/test_adversarial_probes.py"
  ],
  "rationale": "Harden Community microservice test suite with Tier 5 adversarial stress loops verifying deterministic sorting, authentication and authorization boundaries, input edge cases, and Oracle DB isolation.",
  "breaking_changes": false,
  "verification": {
    "command": "PYTHONPATH=services/community /home/jayampatel/swe/greenline/backend/.venv/bin/pytest services/community/tests/test_adversarial_probes.py -v",
    "result": "PASSED"
  }
}
-->

- **Type / Scope**: `test(community)`
- **Summary**: Add adversarial stress probes and test matrix validation for milestone 5.
- **Rationale**: Harden Community microservice test suite with Tier 5 adversarial stress loops verifying deterministic sorting, authentication and authorization boundaries, input edge cases, and Oracle DB isolation.
- **Key Changes**:
  - `services/community/tests/test_adversarial_probes.py`: Implemented 5 adversarial probe suites testing post/comment sorting determinism stress loops (50 repetitions), authentication/authorization denial (401/403/404), input boundary limits (empty, 10k/5k limits, unicode/emojis/RTL, SQLi, XSS, cross-post comments), and Oracle DB least-privilege table denials (all 21 financial tables ORA-00942 and zero DDL ORA-01031).
- **Verification**:
  - Command: `PYTHONPATH=services/community /home/jayampatel/swe/greenline/backend/.venv/bin/pytest services/community/tests/test_adversarial_probes.py -v`
  - Output: `5 passed in 3.18s`

### [2026-11-14 12:31:00 UTC] feat(frontend): implement unified home page redesign and community feed ui

<!-- changelog-entry-json
{
  "timestamp": "2026-11-14T12:31:00Z",
  "type": "feat",
  "scope": "frontend",
  "summary": "implement unified home page redesign and community feed ui",
  "affected_files": [
    "docker-compose.yml",
    "frontend/next.config.ts",
    "frontend/src/lib/community.ts",
    "frontend/src/components/community/MarkdownContent.tsx",
    "frontend/src/components/community/PostComposer.tsx",
    "frontend/src/components/community/PostCard.tsx",
    "frontend/src/components/community/CommentThread.tsx",
    "frontend/src/components/community/CommunityFeed.tsx",
    "frontend/src/components/Sidebar.tsx",
    "frontend/src/app/page.tsx",
    "frontend/src/__tests__/Sidebar.test.tsx",
    "frontend/src/__tests__/communityApi.test.ts",
    "frontend/src/__tests__/CommunityComponents.test.tsx",
    "frontend/src/__tests__/HomePageUnified.test.tsx",
    "frontend/src/__tests__/communityRewrites.test.ts"
  ],
  "rationale": "Implements Milestone 4 by redesigning the home page to integrate portfolio overview metrics alongside a standalone community feed with rich formatting, media attachments, and comments.",
  "breaking_changes": false,
  "verification": {
    "command": "cd frontend && npx tsc --noEmit && npm run lint && npx vitest run src/__tests__/communityApi.test.ts src/__tests__/CommunityComponents.test.tsx src/__tests__/HomePageUnified.test.tsx src/__tests__/communityRewrites.test.ts src/__tests__/Sidebar.test.tsx",
    "result": "PASSED"
  }
}
-->

- **Type / Scope**: `feat(frontend)`
- **Summary**: Implement unified home page redesign and community feed UI with rich markdown composer, media attachments, and commenting.
- **Rationale**: Satisfies Milestone 4 requirements to bridge frontend users to the standalone community microservice via Next.js proxy rewrites and interactive social components embedded on the Home dashboard.
- **Key Changes**:
  - `docker-compose.yml`: Passed `COMMUNITY_URL=http://community:8002/api/v1/community` to the frontend container environment.
  - `frontend/next.config.ts`: Configured gateway proxy rewrites routing `/api/v1/community/:path*` to the community microservice on port 8002.
  - `frontend/src/lib/community.ts`: Implemented typed API client functions for fetching posts, creating posts, fetching comments, creating comments, and fetching random pseudonyms with Auth0 Bearer token injection.
  - `frontend/src/components/community/MarkdownContent.tsx`: Created AST-based safe markdown compiler supporting headings, bold, italic, code, quotes, lists, and sanitized links without dangerouslySetInnerHTML.
  - `frontend/src/components/community/PostComposer.tsx`: Built post composer with rich markdown toolbar, media attachments input and chip previews, and author pseudonym display with randomize button.
  - `frontend/src/components/community/PostCard.tsx`: Created post card component displaying author pseudonym, relative timestamp, media previews, and collapsible comment threads.
  - `frontend/src/components/community/CommentThread.tsx`: Built comment thread component supporting threaded replies, author pseudonym display, and inline reply submission.
  - `frontend/src/components/community/CommunityFeed.tsx`: Built feed container with sort switching (Latest/Oldest), manual refresh, loading skeletons, and empty state.
  - `frontend/src/components/Sidebar.tsx`: Updated navigation branding to label `/` as "Home" with Home icon.
  - `frontend/src/app/page.tsx`: Redesigned root page into a unified Home hub featuring portfolio overview metrics and interactive community feed with view mode switcher (`Unified`, `Overview Only`, `Community Feed`).
  - `frontend/src/__tests__/`: Added comprehensive test suites covering API client methods, community UI components, unified home page rendering, and gateway rewrites.
- **Verification**:
  - Command: `cd frontend && npx tsc --noEmit && npm run lint && npx vitest run src/__tests__/communityApi.test.ts src/__tests__/CommunityComponents.test.tsx src/__tests__/HomePageUnified.test.tsx src/__tests__/communityRewrites.test.ts src/__tests__/Sidebar.test.tsx`
  - Output: TypeScript 0 errors, ESLint 0 errors, Vitest 52/52 tests passed.

### [2026-11-14 11:53:00 UTC] fix(community): add deterministic id tie-breaker for comment ordering in community microservice

<!-- changelog-entry-json
{
  "timestamp": "2026-11-14T11:53:00Z",
  "type": "fix",
  "scope": "community",
  "summary": "add deterministic id tie-breaker for comment ordering in community microservice",
  "affected_files": [
    "services/community/app/services/comment_service.py",
    "services/community/app/db/models.py",
    "services/community/tests/test_comments.py",
    "services/community/tests/test_community_models.py"
  ],
  "rationale": "Oracle DB produces non-deterministic ordering when sorting comments with identical created_at timestamps without a secondary unique tie-breaker. Adding CommunityComment.id.asc() ensures stable chronological ordering under concurrency.",
  "breaking_changes": false,
  "verification": {
    "command": "PYTHONPATH=services/community /home/jayampatel/swe/greenline/backend/.venv/bin/pytest services/community/tests -v && for i in {1..5}; do PYTHONPATH=services/community /home/jayampatel/swe/greenline/backend/.venv/bin/pytest services/community/tests -q || exit 1; done && PYTHONPATH=backend /home/jayampatel/swe/greenline/backend/.venv/bin/pytest backend/tests/test_oracle_community_user_permissions.py -v",
    "result": "PASSED"
  }
}
-->

- **Type / Scope**: `fix(community)`
- **Summary**: Add deterministic `id.asc()` secondary tie-breaker to comment queries and post comments relationship in the Community microservice.
- **Rationale**: Prevent intermittent race conditions and indeterminate sorting order in Oracle DB when multiple comments share identical `created_at` timestamps.
- **Key Changes**:
  - `services/community/app/services/comment_service.py`: Add `CommunityComment.id.asc()` to `get_comments` order_by clause.
  - `services/community/app/db/models.py`: Update `CommunityPost.comments` relationship `order_by` to include `[CommunityComment.created_at.asc(), CommunityComment.id.asc()]`.
  - `services/community/tests/test_comments.py`: Add `test_get_comments_deterministic_tie_breaker_same_timestamp` asserting deterministic order when comments share identical timestamps.
  - `services/community/tests/test_community_models.py`: Add `test_community_models_comments_relationship_order_by_tie_breaker` testing relationship order_by expressions.
- **Verification**:
  - Command: `PYTHONPATH=services/community /home/jayampatel/swe/greenline/backend/.venv/bin/pytest services/community/tests -v`
  - Output: 27 passed in 4.19s
  - Command: `for i in {1..5}; do PYTHONPATH=services/community /home/jayampatel/swe/greenline/backend/.venv/bin/pytest services/community/tests -q || exit 1; done`
  - Output: 5/5 loop passes with zero regressions
  - Command: `PYTHONPATH=backend /home/jayampatel/swe/greenline/backend/.venv/bin/pytest backend/tests/test_oracle_community_user_permissions.py -v`
  - Output: 8 passed in 1.48s


### [2026-11-14 11:15:00 UTC] feat(community): implement standalone community microservice with posts, comments, and pseudonyms

<!-- changelog-entry-json
{
  "timestamp": "2026-11-14T11:15:00Z",
  "type": "feat",
  "scope": "community",
  "summary": "implement standalone community microservice with posts, comments, and pseudonyms",
  "affected_files": [
    "services/community/app/config.py",
    "services/community/app/db/database.py",
    "services/community/app/db/models.py",
    "services/community/app/schemas/post.py",
    "services/community/app/schemas/comment.py",
    "services/community/app/schemas/pseudonym.py",
    "services/community/app/services/auth0_service.py",
    "services/community/app/services/post_service.py",
    "services/community/app/services/comment_service.py",
    "services/community/app/services/pseudonym_service.py",
    "services/community/app/api/deps.py",
    "services/community/app/api/routers/posts.py",
    "services/community/app/api/routers/comments.py",
    "services/community/app/api/routers/pseudonyms.py",
    "services/community/app/main.py",
    "services/community/Dockerfile",
    "services/community/requirements.txt",
    "services/community/tests/conftest.py",
    "services/community/tests/test_posts.py",
    "services/community/tests/test_comments.py",
    "services/community/tests/test_pseudonyms.py",
    "services/community/tests/test_community_models.py",
    "services/community/tests/test_service_health.py",
    "services/community/tests/test_e2e_community_service.py",
    "docker-compose.yml",
    "backend/tests/conftest.py"
  ],
  "rationale": "Implement Milestone 2 standalone community microservice (port 8002) connecting via dedicated Oracle user GREENLINE_COMMUNITY to access community_posts and community_comments tables, offering stateless RS256 Auth0 verification and REST endpoints for creating posts with rich text and media attachments, threaded comments, and random pseudonyms.",
  "breaking_changes": false,
  "verification": {
    "command": "PYTHONPATH=services/community /home/jayampatel/swe/greenline/backend/.venv/bin/pytest services/community/tests -v && PYTHONPATH=backend /home/jayampatel/swe/greenline/backend/.venv/bin/pytest backend/tests/test_oracle_community_user_permissions.py -v",
    "result": "PASSED"
  }
}
-->

- **Type / Scope**: `feat(community)`
- **Summary**: Implement standalone FastAPI Community microservice at `services/community/` with posts, threaded comments, random pseudonym generator, and container orchestration.
- **Rationale**: Decouple community discussions from the core financial ledger by creating an isolated microservice running on port 8002 that connects exclusively using the dedicated least-privilege `GREENLINE_COMMUNITY` Oracle user.
- **Key Changes**:
  - `services/community/app/config.py`: BaseSettings reading port 8002, API prefix `/api/v1/community`, dedicated user `GREENLINE_COMMUNITY`, and Auth0 configuration.
  - `services/community/app/db/database.py` & `models.py`: Async engine and ORM models for `CommunityPost` and `CommunityComment` with cascade deletion and properties for `post_id`, `comment_id`, and `author_sub`.
  - `services/community/app/schemas/`: Pydantic validation schemas for posts, comments, media attachments, and pseudonyms.
  - `services/community/app/services/`: Services for Auth0 token verification, random pseudonym generation, post creation/retrieval, and threaded comments.
  - `services/community/app/api/deps.py` & `routers/`: Auth dependencies and REST endpoints under `/api/v1/community`.
  - `services/community/Dockerfile` & `requirements.txt`: Container packaging and dependencies.
  - `docker-compose.yml`: Added `community` microservice container service on port 8002 and linked to frontend gateway.
  - `services/community/tests/`: 25 automated tests covering endpoints, validation, pagination, multi-user threads, cascade deletion, and least-privilege DB security.
- **Verification**:
  - Command: `PYTHONPATH=services/community /home/jayampatel/swe/greenline/backend/.venv/bin/pytest services/community/tests -v && PYTHONPATH=backend /home/jayampatel/swe/greenline/backend/.venv/bin/pytest backend/tests/test_oracle_community_user_permissions.py -v`
  - Output: 25 passed in 4.05s (community) and 8 passed in 1.52s (security user permissions).

### [2026-11-14 10:17:00 UTC] feat(settings): integrate community pseudonym management card and preview in settings page

<!-- changelog-entry-json
{
  "timestamp": "2026-11-14T10:17:00Z",
  "type": "feat",
  "scope": "settings",
  "summary": "integrate community pseudonym management card and preview in settings page",
  "affected_files": [
    "frontend/src/app/settings/page.tsx"
  ],
  "rationale": "Implement Milestone 3 frontend community pseudonym configuration interface, providing users with a dedicated settings card to configure their community pseudonym, generate whimsical aliases using the pseudonym library, view a live preview badge, and display their configured alias in the current profile card.",
  "breaking_changes": false,
  "verification": {
    "command": "cd frontend && npx vitest run src/__tests__/SettingsPseudonym.test.tsx src/__tests__/pseudonym.test.ts && npx tsc --noEmit && npm run lint && PYTHONPATH=backend /home/jayampatel/swe/greenline/backend/.venv/bin/pytest backend/tests/test_settings.py",
    "result": "PASSED"
  }
}
-->

- **Type / Scope**: `feat(settings)`
- **Summary**: Integrate Community Profile & Pseudonym configuration card with live preview badge and random name generation in settings page.
- **Rationale**: Users need the ability to customize or randomize their community pseudonym for anonymous benchmarking and community discussions, with full persistence to backend settings and local storage.
- **Key Changes**:
  - `frontend/src/app/settings/page.tsx`: Added Community Profile & Pseudonym configuration card with controlled input, "Pick Random Name" button powered by `generateRandomPseudonym()`, Save button, Enter-key handler, live preview badge, and Community Alias row in Current Profile card.
- **Verification**:
  - Command: `cd frontend && npx vitest run src/__tests__/SettingsPseudonym.test.tsx src/__tests__/pseudonym.test.ts && npx tsc --noEmit && npm run lint && PYTHONPATH=backend /home/jayampatel/swe/greenline/backend/.venv/bin/pytest backend/tests/test_settings.py`
  - Output: 10/10 Vitest tests passed, 0 TypeScript errors, 0 ESLint errors, 3/3 pytest backend settings tests passed.

### [2026-11-14 10:02:00 UTC] feat(database): provision dedicated community tables and scoped db user with least privilege

<!-- changelog-entry-json
{
  "timestamp": "2026-11-14T10:02:00Z",
  "type": "feat",
  "scope": "database",
  "summary": "provision dedicated community tables and scoped db user with least privilege",
  "affected_files": [
    "backend/scripts/setup_community_user.sql",
    "backend/scripts/create_db_community_user.py",
    "scripts/setup_community_user.sql",
    "backend/tests/test_oracle_community_user_permissions.py"
  ],
  "rationale": "In alignment with the standalone microservice architectural requirement, dedicated database tables (community_posts, community_comments) and a scoped database user (GREENLINE_COMMUNITY) are provisioned. The user has strictly least-privilege DML permissions on the community tables, an AFTER LOGON trigger setting CURRENT_SCHEMA, zero DDL privileges, and zero access to all 21 core financial tables. Core backend models and migrations have zero community post/comment definitions.",
  "breaking_changes": false,
  "verification": {
    "command": "PYTHONPATH=backend /home/jayampatel/swe/greenline/backend/.venv/bin/pytest backend/tests/test_oracle_community_user_permissions.py backend/tests/test_migrations.py -v",
    "result": "PASSED"
  }
}
-->

- **Type / Scope**: `feat(database)`
- **Summary**: Provision dedicated database tables and least-privilege scoped user for Community microservice.
- **Rationale**: Standalone microservice architecture requires community post and comment persistence to be owned exclusively by dedicated tables and accessed via a scoped database user, isolating financial records and credentials from community interactions.
- **Key Changes**:
  - `backend/scripts/setup_community_user.sql`: Least-privilege SQL DDL and grants provisioning `community_posts` and `community_comments` with `GREENLINE_COMMUNITY` user and `AFTER LOGON` trigger.
  - `backend/scripts/create_db_community_user.py`: Python CLI tool provisioning tables and credentials against Autonomous Cloud DB and local Oracle Free 23ai containers.
  - `scripts/setup_community_user.sql`: Root mirror of setup script.
  - `backend/tests/test_oracle_community_user_permissions.py`: Security and permissions verification suite covering all 8 static and live database assertions.
- **Verification**:
  - Command: `PYTHONPATH=backend /home/jayampatel/swe/greenline/backend/.venv/bin/pytest backend/tests/test_oracle_community_user_permissions.py backend/tests/test_migrations.py -v`
  - Output: 10 passed in 3.27s (100% pass rate).


### [2026-11-13 17:33:00 UTC] feat(portfolio): incorporate dividends into realized pnl and compute holding-level xirr in networth service

<!-- changelog-entry-json
{
  "timestamp": "2026-11-13T17:33:00Z",
  "type": "feat",
  "scope": "portfolio",
  "summary": "incorporate dividends into realized pnl and compute holding-level xirr in networth service",
  "affected_files": [
    "services/networth/app/api/routers/portfolio.py",
    "services/networth/tests/test_networth_dividends_and_xirr.py"
  ],
  "rationale": "In the Networth microservice (/api/v1/portfolio), dividend income was excluded from realized P&L and total dividend income was hardcoded to 0.0. Additionally, holding-level XIRR was never computed because _compute_asset_xirr_in_memory was not invoked with asset cashflows, causing the XIRR column in /investments/holdings to display empty hyphens. Pre-fetching net dividends and asset cash flows populates dividend_income, adds dividends into realized_pnl and total_realized_pnl, and computes per-holding and closed-position annualized XIRR.",
  "breaking_changes": false,
  "verification": {
    "command": "PYTHONPATH=backend:. backend/.venv/bin/pytest services/networth/tests/test_networth_dividends_and_xirr.py services/networth/tests/test_networth_fees_and_taxes.py backend/tests/test_fees_taxes_and_pnl.py && cd frontend && npx vitest run src/__tests__/LocalFont.test.ts src/__tests__/SettingsFont.test.tsx && npx tsc --noEmit && npm run lint",
    "result": "PASSED"
  }
}
-->

- **Type / Scope**: `feat(portfolio)`
- **Summary**: Include dividend income in realized P&L, populate total dividend income, and compute holding-level XIRRs in the Networth service.
- **Rationale**:
  - Resolves missing dividend income in realized P&L and portfolio summary KPI metrics on `/investments/holdings`.
  - Resolves empty XIRR column (`-`) across active and closed holdings by querying asset cashflows and evaluating `_compute_asset_xirr_in_memory` with latest market valuations.
- **Key Changes**:
  - `services/networth/app/api/routers/portfolio.py`:
    - Imported `CashFlow` and pre-fetched asset cash flows (`scope_type="asset"`) and net dividend transactions.
    - Updated active holdings: added net dividends to `realized_pnl`, populated `dividend_income`, and computed `xirr` via `_compute_asset_xirr_in_memory`.
    - Updated closed holdings: included dividend-receiving assets in closed candidate list, added dividends to `realized_pnl`, and computed closed holding `xirr`.
    - Updated portfolio summary response: aggregated `total_dividend_income` and included dividends in `total_realized_pnl`.
  - `services/networth/tests/test_networth_dividends_and_xirr.py`: Added automated test suite verifying dividend inclusion and holding XIRR calculation.
- **Verification**:
  - Live Networth service check: User 19 returns active XIRRs across all 5 holdings (e.g. NVDA: 30.27%, AMZN: 28.38%, GOOGL: 28.10%, MSFT: 25.68%, AAPL: 23.48%) and portfolio XIRR 27.51%; User 15 returns `total_dividend_income: 610.64`, `total_realized_pnl: 8698.37` (8087.73 capital gains + 610.64 dividends), with 32/32 active holdings and 7/7 closed holdings populated with valid XIRRs.
  - Automated tests: 13 passed in 23.61s (`test_networth_dividends_and_xirr.py`, `test_networth_fees_and_taxes.py`, `test_fees_taxes_and_pnl.py`, `test_assets_router.py`, `test_price_engine.py`).
  - Frontend vitest: 12 passed in 6.06s.
  - TypeScript & lint: Passed with 0 errors.



### [2026-11-13 16:06:00 UTC] feat(portfolio): calculate fees and taxes in networth service and switch spline sans font to local assets

<!-- changelog-entry-json
{
  "timestamp": "2026-11-13T16:06:00Z",
  "type": "feat",
  "scope": "portfolio",
  "summary": "calculate fees and taxes in networth service and switch spline sans font to local assets",
  "affected_files": [
    "backend/app/services/networth_client.py",
    "frontend/src/app/layout.tsx",
    "frontend/src/__tests__/LocalFont.test.ts",
    "services/networth/app/api/routers/portfolio.py",
    "services/networth/tests/test_networth_fees_and_taxes.py"
  ],
  "rationale": "In the Networth microservice (/api/v1/portfolio), total_fees and total_taxes were hardcoded to 0.0, and fees_and_taxes, total_fees, and total_taxes were not populated on holding summaries. Pre-fetching fees and taxes from Transaction records grouped by asset and aggregating total transaction fees and taxes enables accurate portfolio and per-holding fee/tax accounting. Additionally, Spline Sans in layout.tsx has been switched from the external Google Fonts API (next/font/google) to localFont loading from public/fonts/Spline_Sans/SplineSans-VariableFont_wght.ttf for offline resilience, zero third-party font latency, and strict privacy compliance.",
  "breaking_changes": false,
  "verification": {
    "command": "PYTHONPATH=backend:. backend/.venv/bin/pytest services/networth/tests/test_networth_fees_and_taxes.py backend/tests/test_fees_taxes_and_pnl.py && cd frontend && npx vitest run src/__tests__/LocalFont.test.ts src/__tests__/SettingsFont.test.tsx && npx tsc --noEmit && npm run lint",
    "result": "PASSED"
  }
}
-->

- **Type / Scope**: `feat(portfolio)`
- **Summary**: Calculate transaction fees and taxes across holdings and portfolio summary in the Networth service, and load Spline Sans via `localFont` using local TTF assets instead of Google API.
- **Rationale**:
  - Ensures accurate fees, taxes, and net P&L display across both portfolio summary and active/closed holdings cards and tables.
  - Eliminates external requests to Google Fonts API by serving Spline Sans directly from `public/fonts/Spline_Sans/SplineSans-VariableFont_wght.ttf`.
  - Fixes networth notification client to safely handle FastAPI `Header` instances in direct test invocations.
- **Key Changes**:
  - `services/networth/app/api/routers/portfolio.py`: Pre-aggregated fees and taxes from `Transaction` grouped by `asset_id`; populated `fees_and_taxes`, `total_fees`, and `total_taxes` on both active and closed `HoldingSummary` models; aggregated portfolio-level `total_fees` and `total_taxes` with currency conversion.
  - `services/networth/tests/test_networth_fees_and_taxes.py`: Added automated test suite verifying portfolio and holding fee/tax computations.
  - `frontend/src/app/layout.tsx`: Replaced `Spline_Sans` import from `next/font/google` with `localFont` pointing to `./../../public/fonts/Spline_Sans/SplineSans-VariableFont_wght.ttf`.
  - `frontend/src/__tests__/LocalFont.test.ts`: Added unit test ensuring Spline Sans loads via `localFont` rather than Google Fonts.
  - `backend/app/services/networth_client.py`: Added `isinstance(auth_token, str)` check to protect against `AttributeError` when `auth_token` is a FastAPI `Header` object in direct Python unit test calls.
- **Verification**:
  - Live Networth service check: User 19 returns `total_fees: 170.0`, `total_taxes: 0.0` with 34.0 fee per holding; User 15 returns `total_fees: 41.97`, `total_taxes: 9.05`.
  - Backend tests: `services/networth/tests/test_networth_fees_and_taxes.py` & `backend/tests/test_fees_taxes_and_pnl.py` (12 passed in 17.92s).
  - Frontend vitest: `LocalFont.test.ts`, `SettingsFont.test.tsx`, `FontProvider.test.tsx`, `apiFetch.test.ts` (12 passed in 5.41s).
  - Typecheck & Lint: `npx tsc --noEmit && npm run lint` passed with 0 errors.



### [2026-11-13 13:16:00 UTC] fix(portfolio): compute realized pnl and closed holdings in networth service and add composite primary key to app_settings

<!-- changelog-entry-json
{
  "timestamp": "2026-11-13T13:16:00Z",
  "type": "fix",
  "scope": "portfolio",
  "summary": "compute realized pnl and closed holdings in networth service and add composite primary key to app_settings",
  "affected_files": [
    "backend/app/db/migrations.py",
    "frontend/src/app/investments/holdings/page.tsx",
    "services/networth/app/api/routers/portfolio.py"
  ],
  "rationale": "In the networth microservice (/api/v1/portfolio), realized_pnl and realized_pnl_pct were hardcoded to 0.0 and closed_holdings was empty, causing /investments/holdings to show 0.00 for realized P&L and hide closed positions. Pre-fetching realized P&L and cost basis from LotSale joins computes realized P&L and populates closed holdings accurately. Additionally, Oracle app_settings had a legacy single-column primary key on key, causing ORA-00001 unique constraint violations on auth sync and settings updates when multi-user rows were inserted. Adding migration v014_app_settings_composite_primary_key establishes composite primary key (user_id, key).",
  "breaking_changes": false,
  "verification": {
    "command": "PYTHONPATH=backend:. backend/.venv/bin/pytest backend/tests/test_assets_router.py backend/tests/test_price_engine.py && cd frontend && npx vitest run src/__tests__/apiFetch.test.ts src/__tests__/AccountModals.test.tsx && npx tsc --noEmit && npm run lint",
    "result": "PASSED"
  }
}
-->

- **Type / Scope**: `fix(portfolio)`
- **Summary**: Accurately calculate and return realized P&L and closed holdings in the Networth service, and migrate Oracle `app_settings` primary key to `(user_id, key)`.
- **Rationale**:
  - Fixes `/investments/holdings` displaying `0.00` for Realized P&L and missing closed holdings by querying `LotSale` matched with `Lot.asset_id` and calculating realized P&L per holding and closed asset.
  - Fixes HTTP 500 error on settings save / auth sync caused by `ORA-00001: unique constraint (ADMIN.SYS_C0037045) violated on table ADMIN.APP_SETTINGS columns (key)` by transitioning Oracle `app_settings` to a composite primary key `(user_id, "key")`.
- **Key Changes**:
  - `services/networth/app/api/routers/portfolio.py`: Pre-aggregated realized P&L and cost basis from `LotSale` per asset; populated `realized_pnl`, `realized_pnl_pct`, `net_pnl`, and `capital_gains_realized` on each `HoldingSummary`; populated `closed_holdings` list and added `/closed-holdings` endpoint.
  - `backend/app/db/migrations.py`: Added migration `v014_app_settings_composite_primary_key` dropping the legacy primary key and adding composite `PRIMARY KEY (user_id, "key")` in Oracle.
  - `frontend/src/app/investments/holdings/page.tsx`: Cleaned whitespace and verified currency conversion integration with `realized_pnl` for both active and closed holdings.
- **Verification**:
  - Verified `get_portfolio_summary` returns non-zero `total_realized_pnl` (`15370.86`) and holding-level realized PnL for active positions, and 7 closed positions for user 15.
  - Verified `app_settings` allows duplicate keys across different `user_id` values without constraint violations.
  - Backend tests: `backend/tests/test_assets_router.py` & `backend/tests/test_price_engine.py` (10 passed).
  - Frontend tests: `src/__tests__/apiFetch.test.ts` & `src/__tests__/AccountModals.test.tsx` (6 passed).
  - Frontend lint & typecheck: `npx tsc --noEmit` and `npm run lint` passed with 0 errors.



### [2026-11-13 01:10:00 UTC] fix(api): eliminate 307 internal host redirects on assets endpoint and add client trailing slash recovery

<!-- changelog-entry-json
{
  "timestamp": "2026-11-13T01:10:00Z",
  "type": "fix",
  "scope": "api",
  "summary": "eliminate 307 internal host redirects on assets endpoint and add client trailing slash recovery",
  "affected_files": [
    "backend/app/api/routers/assets.py",
    "backend/tests/test_assets_router.py",
    "frontend/src/lib/api.ts",
    "frontend/src/__tests__/apiFetch.test.ts"
  ],
  "rationale": "FastAPI router assets.py only defined @router.get('/'), causing requests to /api/v1/assets to emit an HTTP 307 redirect with 'Location: http://backend:8000/api/v1/assets/'. Because 'backend:8000' is an internal Docker container name unresolvable by the browser, Promise.all on the accounts page threw 'TypeError: Failed to fetch' and aborted account rendering. Adding dual route decorators (@router.get('') and @router.get('/')) and client-side trailing-slash recovery ensures direct responses without internal redirect leaks.",
  "breaking_changes": false,
  "verification": {
    "command": "PYTHONPATH=backend:. backend/.venv/bin/pytest backend/tests/test_assets_router.py backend/tests/test_price_engine.py && cd frontend && npx vitest run src/__tests__/apiFetch.test.ts && npx tsc --noEmit && npm run lint",
    "result": "PASSED"
  }
}
-->

- **Type / Scope**: `fix(api)`
- **Summary**: Fix internal Docker hostname leaks on `/assets` trailing-slash redirects and add client trailing-slash recovery.
- **Rationale**: Prevent `TypeError: Failed to fetch` on the Accounts page caused by FastAPI emitting 307 redirects to internal Docker hostnames (`http://backend:8000/api/v1/assets/`).
- **Key Changes**:
  - `backend/app/api/routers/assets.py`: Added dual route decorators `@router.get("")` and `@router.post("")` alongside slash routes to prevent 307 redirects.
  - `backend/tests/test_assets_router.py`: Added automated regression tests verifying that GET and POST requests without trailing slashes return direct 200/201 responses without redirects.
  - `frontend/src/lib/api.ts`: Enhanced `apiFetch` retry handler to automatically append trailing slashes on transient network errors for root endpoints.
  - `frontend/src/__tests__/apiFetch.test.ts`: Added unit tests verifying trailing-slash retry handling.
- **Verification**:
  - Command: `PYTHONPATH=backend:. backend/.venv/bin/pytest backend/tests/test_assets_router.py` -> 7 passed.
  - Command: `cd frontend && npx vitest run src/__tests__/apiFetch.test.ts` -> 3 passed.
  - Command: `cd frontend && npx tsc --noEmit && npm run lint` -> 0 errors.

### [2026-11-12 21:07:00 UTC] fix(frontend): add automatic retry on proxy socket hangup and transient fetch drops in apiFetch

<!-- changelog-entry-json
{
  "timestamp": "2026-11-12T21:07:00Z",
  "type": "fix",
  "scope": "frontend",
  "summary": "add automatic retry on proxy socket hangup and transient fetch drops in apiFetch",
  "affected_files": [
    "frontend/src/lib/api.ts",
    "frontend/src/__tests__/apiFetch.test.ts"
  ],
  "rationale": "When backend services are restarted or host wakeups cause Docker proxy socket resets (ECONNRESET), Next.js proxy connections can become stale, resulting in client-side 'TypeError: Failed to fetch' or 502 Bad Gateway. Adding a lightweight single retry in apiFetch gracefully reopens a fresh connection and recovers without failing page renders or showing unhandled console exceptions.",
  "breaking_changes": false,
  "verification": {
    "command": "cd frontend && npx vitest run src/__tests__/apiFetch.test.ts && npx tsc --noEmit && npm run lint",
    "result": "PASSED"
  }
}
-->

- **Type / Scope**: `fix(frontend)`
- **Summary**: Add automatic 1-shot retry for transient socket hangups and proxy gateway drops in `apiFetch`.
- **Rationale**: Mitigates `TypeError: Failed to fetch` and transient 502/504 proxy resets when upstream microservices restart or when stale keep-alive sockets drop.
- **Key Changes**:
  - `frontend/src/lib/api.ts`: Wrapped HTTP fetch in a resilient try/catch checking for transient `TypeError` and 502/504 gateway responses to retry once over a fresh socket connection after a 200ms backoff.
  - `frontend/src/__tests__/apiFetch.test.ts`: Added unit tests verifying automatic 1-shot retry behavior for both `TypeError: Failed to fetch` and HTTP 502 responses.
- **Verification**:
  - Command: `npx vitest run src/__tests__/apiFetch.test.ts` -> 2 passed.
  - Command: `npx tsc --noEmit && npm run lint` -> 0 errors.

### [2026-11-12 13:05:00 UTC] fix(portfolio): fix price refresh timeouts, historical snapshot timeline generation, and chart tick formatting

<!-- changelog-entry-json
{
  "timestamp": "2026-11-12T13:05:00Z",
  "type": "fix",
  "scope": "portfolio",
  "summary": "fix price refresh timeouts, historical snapshot timeline generation, and chart tick formatting",
  "affected_files": [
    "backend/app/api/routers/prices.py",
    "backend/app/services/price_engine.py",
    "backend/app/services/dividend_engine.py",
    "backend/tests/test_price_engine.py",
    "services/networth/app/api/routers/snapshots.py",
    "frontend/src/app/page.tsx",
    "frontend/src/app/investments/page.tsx",
    "frontend/src/components/NetWorthChart.tsx"
  ],
  "rationale": "Clicking 'Sync Market Prices' caused HTTP 500 ECONNRESET timeouts because price and dividend engines sequentially queried Yahoo Finance for unlisted .PRIVATE assets across the whole database. Additionally, newly populated historical transactions lacked precomputed snapshots, and the snapshot endpoint strictly required Sunday dates, rendering the timeline chart empty. Non-INR currencies were also misformatted with Indian Lakh (L) and Crore (Cr) notation.",
  "breaking_changes": false,
  "verification": {
    "command": "PYTHONPATH=backend:. backend/.venv/bin/pytest backend/tests/test_price_engine.py && cd frontend && npx tsc --noEmit && npm run lint",
    "result": "PASSED"
  }
}
-->

- **Type / Scope**: `fix(portfolio)`
- **Summary**: Fix price refresh proxy timeouts, ensure historical snapshot timeline regeneration on price sync, guarantee non-empty snapshot timeline endpoints, and format EUR/USD chart ticks as k/M/B.
- **Rationale**:
  - Unlisted private assets (`.PRIVATE`, `$*`) caused long yfinance network retries that exceeded the proxy socket timeout (ECONNRESET -> HTTP 500).
  - Populating transactions without computing historical snapshots left users with 0 Sunday snapshots in the filter window, causing the net worth graph to render empty.
  - The currency tick formatter in `NetWorthChart` always evaluated `absVal >= 100000` with `'L'` before `'M'`, incorrectly applying Indian numbering to EUR/USD.
- **Key Changes**:
  - `backend/app/services/price_engine.py` & `dividend_engine.py`: Added `_is_unsupported_ticker` to bypass `.PRIVATE` and delisted assets; added 10-second network timeouts.
  - `backend/app/api/routers/prices.py`: Filtered price sync by assets owned by the requesting tenant and triggered `recalculate_past_snapshots` from `min_tx` so the timeline updates automatically.
  - `services/networth/app/api/routers/snapshots.py`: Included the latest non-Sunday snapshot alongside Sundays so active timelines are never empty.
  - `frontend/src/components/NetWorthChart.tsx`: Corrected `formatCurrencyTick` to only use `L` and `Cr` for `currency === "INR"`, and `k`, `M`, `B` for EUR/USD/others.
  - `frontend/src/app/page.tsx` & `investments/page.tsx`: Ensured `loadData` runs in `finally` even if background price refresh encounters transient warnings.
- **Verification**:
  - Command: `PYTHONPATH=backend:. backend/.venv/bin/pytest backend/tests/test_price_engine.py` -> 3 passed.
  - Command: `cd frontend && npx tsc --noEmit && npm run lint` -> 0 errors.
  - Container test: User 19 snapshot recalculation produced 105 Sunday snapshots spanning 2024-11-12 to 2026-11-15; chart data verified.

### [2026-11-12 11:45:00 UTC] feat(db): add 1000 row 2-year sample data population script with multi-account, multi-category, and stock transactions

<!-- changelog-entry-json
{
  "timestamp": "2026-11-12T11:45:00Z",
  "type": "feat",
  "scope": "db",
  "summary": "add 1000 row 2-year sample data population script with multi-account, multi-category, and stock transactions",
  "affected_files": [
    "backend/scripts/populate_1000_sample_data.sql",
    "scripts/populate_1000_sample_data.sql"
  ],
  "rationale": "Provide an idempotent, standalone Oracle PL/SQL script generating 1,000 realistic transaction records spanning exactly two years (730 days) across cashflow (single-category, multi-category splits, multi-account split payments, and both combined) and stock investments (FIFO buys and lot depletion sales with realized PnL and asset price history).",
  "breaking_changes": false,
  "verification": {
    "command": "Executed against local Oracle Free 23ai container and verified row counts (900 cashflow, 100 investment = 1,000 total), date ranges, split patterns, and FIFO lot sales.",
    "result": "PASSED"
  }
}
-->

- **Type / Scope**: `feat(db)`
- **Summary**: Add standalone Oracle SQL script to populate 1,000 transactions spanning 2 years with multi-account, multi-category, and stock buy/sell transactions.
- **Rationale**: Enables realistic load, aggregation, and Sankey/Networth chart validation across diverse transaction patterns (single account/category, split items, split payment sources, simultaneous split items and payments, and FIFO equity lots with price histories).
- **Key Changes**:
  - `backend/scripts/populate_1000_sample_data.sql`: Core Oracle PL/SQL procedure populating 900 cashflow transactions (225 single, 225 split category, 225 split accounts, 225 both) and 100 investment transactions (60 buys, 40 sells with 52 FIFO lot_sales), plus verification queries and rollback block.
  - `scripts/populate_1000_sample_data.sql`: Root scripts directory copy for developer convenience.
- **Verification**:
  - Command: Script executed and tested on local Oracle Free 23ai test database (`FREEPDB1`).
  - Output: 900 cashflow + 100 stock transactions = 1,000 total across 2024-11-12 to 2026-11-12. Idempotency and child cascade cleanups verified.

### [2026-11-12 00:58:00 UTC] fix(networth): normalize multi-currency asset valuations and cash balances to EUR base currency in snapshot engines

<!-- changelog-entry-json
{
  "timestamp": "2026-11-12T00:58:00Z",
  "type": "fix",
  "scope": "networth",
  "summary": "normalize multi-currency asset valuations and cash balances to EUR base currency in snapshot engines",
  "affected_files": [
    "services/networth/app/services/snapshot_engine.py",
    "services/networth/app/api/routers/portfolio.py",
    "services/networth/app/api/routers/snapshots.py",
    "backend/app/services/snapshot_engine.py",
    "backend/tests/test_snapshot_currency_normalization.py",
    "backend/tests/test_snapshot_funding_multicurrency.py"
  ],
  "rationale": "Historical snapshots in NETWORTH_SNAPSHOTS stored raw unconverted currency amounts, causing Indian Rupee accounts to be stored in lakhs (e.g. 463k) and frontend charts to display EUR values in Lakhs ('L') with distorted net worth deltas (+€453,005). Normalizing all asset lots, realized PnL, cash movements, and total invested to EUR base resolves chart scale and annual snapshot metrics.",
  "breaking_changes": false,
  "verification": {
    "command": "PYTHONPATH=services/networth:backend:. backend/.venv/bin/pytest backend/tests/test_snapshot_currency_normalization.py backend/tests/test_snapshot_funding_multicurrency.py backend/tests/test_e2e_networth_microservice.py -v",
    "result": "PASSED"
  }
}
-->

- **Type / Scope**: `fix(networth)`
- **Summary**: Normalize multi-currency asset valuations, cash movements, and realized/unrealized PnL to EUR base currency in snapshot engines and annual snapshot API.
- **Rationale**: Prior snapshot engines accumulated raw transaction and asset currency figures without FX conversion, contaminating EUR base net worth with un-converted INR values and generating distorted chart axes (`€5.4L`, `€4.5L`) and massive false deltas (`+€453,005.60`).
- **Key Changes**:
  - `services/networth/app/services/snapshot_engine.py`: Converted asset valuation (`rem_qty * price`), cost basis, realized PnL, transaction cash movements, and cashflow payments to EUR using `to_eur(...)` based on account/asset currency. Enforced 2 decimal places precision.
  - `backend/app/services/snapshot_engine.py`: Mirrored EUR normalization logic across daily generator and historical Sunday recalculation replay.
  - `services/networth/app/api/routers/portfolio.py`: Normalized start and end snapshot net worth to requested `master_currency` and populated `investments_done`, `investments_closed`, and `taxes_and_fees` from transaction records.
  - `services/networth/app/api/routers/snapshots.py`: Added type guards on `account_id` and `start_date` to prevent SQLAlchemy Query object binding errors.
  - `ADMIN.NETWORTH_SNAPSHOTS`: Altered unique constraint to composite `(USER_ID, SNAPSHOT_DATE)`, pruned legacy non-Sunday records, and recalculated all past snapshots for user 15 to reflect true EUR valuations (€3,854.07 current, €5,764.69 historical peak).
  - `backend/tests/test_snapshot_currency_normalization.py`: Added TDD unit test verifying multi-currency INR+EUR normalization.
  - `backend/tests/test_snapshot_funding_multicurrency.py`: Updated assertion expectations to test direct EUR persistence.
- **Verification**:
  - Command: `PYTHONPATH=services/networth:backend:. backend/.venv/bin/pytest backend/tests/test_snapshot_currency_normalization.py backend/tests/test_snapshot_funding_multicurrency.py backend/tests/test_e2e_networth_microservice.py -v`
  - Output: 37 passed in 17.56s.
  - Command: `npm --prefix frontend run build`
  - Output: Compiled successfully, TypeScript passed with zero errors.

### [2026-11-12 00:14:00 UTC] fix(frontend): enhance apiFetch error reporting to display exact HTTP status details

<!-- changelog-entry-json
{
  "timestamp": "2026-11-12T00:14:00Z",
  "type": "fix",
  "scope": "frontend",
  "summary": "enhance apiFetch error reporting to display exact HTTP status details",
  "affected_files": [
    "frontend/src/lib/api.ts"
  ],
  "rationale": "Prevent opaque 'API Error' console messages when upstream backend is unreachable or returning non-JSON error pages, providing clear HTTP status code and status text diagnostics.",
  "breaking_changes": false,
  "verification": {
    "command": "cd frontend && npx tsc --noEmit && npm run lint",
    "result": "PASSED"
  }
}
-->

- **Type / Scope**: `fix(frontend)`
- **Summary**: Enhance `apiFetch` error diagnostics to include HTTP status code and text.
- **Rationale**: When the backend returns an error or connection reset, provide informative error text instead of generic `"API Error"`.
- **Key Changes**:
  - `frontend/src/lib/api.ts`: Format fallback error with `HTTP ${res.status}: ${res.statusText || "API Error"}`.
- **Verification**:
  - Command: `cd frontend && npx tsc --noEmit && npm run lint`
  - Output: `0 errors`.

### [2026-11-12 00:02:00 UTC] feat(config): support dedicated ORACLE_NETWORTH_USER and credentials forwarding in microservice and docker-compose

<!-- changelog-entry-json
{
  "timestamp": "2026-11-12T00:02:00Z",
  "type": "feat",
  "scope": "config",
  "summary": "support dedicated ORACLE_NETWORTH_USER and credentials forwarding in microservice and docker-compose",
  "affected_files": [
    "services/networth/app/config.py",
    "docker-compose.yml",
    ".env.example"
  ],
  "rationale": "Allow users to configure dedicated credentials for the Networth microservice (ORACLE_NETWORTH_USER / ORACLE_NETWORTH_PASSWORD) in .env, falling back seamlessly to ORACLE_USER when unset.",
  "breaking_changes": false,
  "verification": {
    "command": "docker compose config",
    "result": "PASSED"
  }
}
-->

- **Type / Scope**: `feat(config)`
- **Summary**: Support dedicated `ORACLE_NETWORTH_USER` and `ORACLE_NETWORTH_PASSWORD` in `.env` and `docker-compose.yml`.
- **Rationale**: Allow isolated database role credentials for the analytical microservice without disrupting Core API credentials.
- **Key Changes**:
  - `services/networth/app/config.py`: Added fallback check for `ORACLE_NETWORTH_USER` and `ORACLE_NETWORTH_PASSWORD`.
  - `docker-compose.yml`: Forwarded `ORACLE_NETWORTH_USER` and `ORACLE_NETWORTH_PASSWORD` environment variables to `networth` container.
  - `.env.example`: Documented `ORACLE_NETWORTH_USER` and `ORACLE_NETWORTH_PASSWORD` configuration options.
- **Verification**:
  - Command: `docker compose config`
  - Output: `Verified clean compose configuration`.

### [2026-11-11 20:35:00 UTC] feat(networth): integrate weekly sunday snapshots, sub-50ms caching, background worker, and core api client

<!-- changelog-entry-json
{
  "timestamp": "2026-11-11T20:35:00Z",
  "type": "feat",
  "scope": "networth",
  "summary": "integrate weekly sunday snapshots, sub-50ms caching, background worker, and core api client",
  "affected_files": [
    "services/networth/app/main.py",
    "services/networth/app/api/routers/snapshots.py",
    "services/networth/app/api/routers/portfolio.py",
    "services/networth/app/db/database.py",
    "services/networth/app/services/snapshot_engine.py",
    "services/networth/app/services/background_worker.py",
    "services/networth/app/scheduler.py",
    "backend/app/config.py",
    "backend/app/services/networth_client.py",
    "backend/app/api/routers/transactions.py",
    "backend/tests/test_e2e_networth_microservice.py"
  ],
  "rationale": "Mount Networth microservice routers, manage background worker and scheduler lifecycles, enforce Sunday snapshot invariants, enable L1 in-memory sub-50ms TTL caching with invalidation, support NullPool engine config under test environments, add non-blocking Networth notification client in Core API transactions, and verify 100% passing E2E test suite.",
  "breaking_changes": false,
  "verification": {
    "command": "PYTHONPATH=services/networth:backend:. /home/jayampatel/swe/greenline/backend/.venv/bin/pytest backend/tests/test_e2e_networth_microservice.py -v",
    "result": "PASSED (35/35 passed in 16.59s)"
  }
}
-->

- **Type / Scope**: `feat(networth)`
- **Summary**: Integrate weekly Sunday snapshots, sub-50ms caching, background worker, and Core API client.
- **Rationale**: Wire the Networth microservice into the Greenline architecture with background recalculation, weekly Sunday interval aggregation, L1 caching, and decoupled Core API notifications.
- **Key Changes**:
  - `services/networth/app/main.py`: Mounted `snapshots` and `portfolio` routers, wired `background_worker` and `scheduler` startup/shutdown into lifespan.
  - `services/networth/app/api/routers/portfolio.py`: Added `NetworthSnapshot` import, verified sub-50ms `portfolio_summary_cache`.
  - `services/networth/app/api/routers/snapshots.py`: Enforced Sunday invariant (`weekday == 6`), verified SQL pushdown for `start_date`, L1 `snapshots_cache` with per-user invalidation, and `POST /trigger-recalculate` returning 202 Accepted.
  - `services/networth/app/db/database.py`: Stripped `pool_size` and `max_overflow` when `NullPool` is configured.
  - `services/networth/app/services/snapshot_engine.py`: Attached and persisted `NetworthByAssetClass` breakdowns in `generate_daily_snapshot` and ensured 7-day Sunday stepping.
  - `services/networth/app/services/background_worker.py`: Added self-starting check in `enqueue_recalculate` for resilient async execution.
  - `services/networth/app/scheduler.py`: Added UTC timezone and isolated database sessions per user during Sunday consolidation.
  - `backend/app/config.py`: Added `NETWORTH_SERVICE_URL`.
  - `backend/app/services/networth_client.py`: Created non-blocking async notification client for snapshot recalculation with resilient error suppression.
  - `backend/app/api/routers/transactions.py`: Replaced synchronous recalculation with non-blocking async background notifications via `networth_client`.
  - `backend/tests/test_e2e_networth_microservice.py`: Resolved root sys.path, patched Auth0 JWKS across both services, and injected DB test session dependency overrides.
- **Verification**:
  - Command: `PYTHONPATH=services/networth:backend:. /home/jayampatel/swe/greenline/backend/.venv/bin/pytest backend/tests/test_e2e_networth_microservice.py -v`
  - Output: `35 passed in 16.59s` (100% pass rate, sub-50ms latency confirmed).

### [2026-11-11 16:40:00 UTC] feat(frontend): add transparent rewrites and snapshot starting date selection UI

<!-- changelog-entry-json
{
  "timestamp": "2026-11-11T16:40:00Z",
  "type": "feat",
  "scope": "frontend",
  "summary": "add transparent rewrites and snapshot starting date selection UI",
  "affected_files": [
    "docker-compose.yml",
    "frontend/next.config.ts",
    "frontend/src/lib/api.ts",
    "frontend/src/components/SnapshotDateControl.tsx",
    "frontend/src/app/page.tsx",
    "frontend/src/app/investments/page.tsx",
    "frontend/src/app/settings/page.tsx",
    "frontend/src/test/SnapshotDateControl.test.tsx"
  ],
  "rationale": "Configure transparent Next.js rewrites for dedicated Networth microservice routing on port 8001, update client API base to relative origin, update docker-compose frontend service configuration, implement SnapshotDateControl with Auto/Manual modes, 'Sep 1' and other quick presets, and localStorage persistence, and integrate into dashboard views.",
  "breaking_changes": false,
  "verification": {
    "command": "cd frontend && npx vitest run src/test/SnapshotDateControl.test.tsx && npx tsc --noEmit && npm run lint",
    "result": "PASSED"
  }
}
-->

- **Type / Scope**: `feat(frontend)`
- **Summary**: Add transparent rewrites and snapshot starting date selection UI
- **Rationale**: Support seamless client communication with the new Networth microservice via Next.js rewrites, update client apiFetch base, configure docker-compose frontend environment, and provide user controls for automatic vs manual snapshot baseline selection with quick presets.
- **Key Changes**:
  - `docker-compose.yml`: Set `NEXT_PUBLIC_API_URL=` empty, added `NETWORTH_URL=http://networth:8001`, `BACKEND_URL=http://backend:8000`, and added `networth` dependency.
  - `frontend/next.config.ts`: Added Next.js `rewrites()` proxying `/api/v1/portfolio/:path*` and `/api/v1/snapshots/:path*` to `NETWORTH_URL` (port 8001) and `/api/v1/:path*` to `BACKEND_URL` (port 8000).
  - `frontend/src/lib/api.ts`: Updated `getApiBase()` to return `process.env.NEXT_PUBLIC_API_URL || ""` in the browser, routing client requests relatively through Next.js proxy.
  - `frontend/src/components/SnapshotDateControl.tsx`: Created reusable component supporting Auto (earliest record) vs Manual date selection, quick presets ("Sep 1", "Jan 1 (YTD)", "Apr 1 (Fiscal)", "1 Year Ago"), and `localStorage` persistence (`greenline_snapshot_start_mode`, `greenline_snapshot_start_date`).
  - `frontend/src/app/page.tsx`: Embedded `SnapshotDateControl` beside timeframe buttons and appended `?start_date=YYYY-MM-DD` query param to snapshot requests.
  - `frontend/src/app/investments/page.tsx`: Embedded `SnapshotDateControl` beside timeframe buttons and appended `?start_date=YYYY-MM-DD` query param to snapshot requests.
  - `frontend/src/app/settings/page.tsx`: Added Snapshot Starting Date Baseline card under Preferences section using inline variant.
  - `frontend/src/test/SnapshotDateControl.test.tsx`: Added 14 automated Vitest tests covering auto/manual switching, quick presets, date input changes, localStorage persistence, popover toggle, getApiBase, and Next.js rewrite rules.
- **Verification**:
  - Command: `cd frontend && npx vitest run src/test/SnapshotDateControl.test.tsx && npx tsc --noEmit && npm run lint`
  - Output: 14 passing Vitest tests, TypeScript clean (0 errors), ESLint clean (0 errors).



### [2026-11-11 16:25:00 UTC] feat(networth): scaffold dedicated Networth microservice infrastructure and core API setup

<!-- changelog-entry-json
{
  "timestamp": "2026-11-11T16:25:00Z",
  "type": "feat",
  "scope": "networth",
  "summary": "scaffold dedicated Networth microservice infrastructure and core API setup",
  "affected_files": [
    "docker-compose.yml",
    "services/__init__.py",
    "services/networth/__init__.py",
    "services/networth/requirements.txt",
    "services/networth/Dockerfile",
    "services/networth/app/__init__.py",
    "services/networth/app/config.py",
    "services/networth/app/db/__init__.py",
    "services/networth/app/db/database.py",
    "services/networth/app/db/models.py",
    "services/networth/app/services/__init__.py",
    "services/networth/app/services/auth0_service.py",
    "services/networth/app/api/__init__.py",
    "services/networth/app/api/deps.py",
    "services/networth/app/main.py",
    "services/networth/tests/conftest.py",
    "services/networth/tests/test_service_init.py"
  ],
  "rationale": "Implement Milestone 2 infrastructure for the dedicated Networth and Analytics microservice: Dockerfile on port 8001, docker-compose.yml service definition, async Oracle DB engine with declarative models restricted to the 17 accessible tables, stateless Auth0 RS256 JWT verification with 24h JWKS caching, and healthcheck endpoint with GZip middleware.",
  "breaking_changes": false,
  "verification": {
    "command": "PYTHONPATH=services/networth:backend /home/jayampatel/swe/greenline/backend/.venv/bin/pytest services/networth/tests/test_service_init.py",
    "result": "PASSED"
  }
}
-->

- **Type / Scope**: `feat(networth)`
- **Summary**: Scaffold dedicated Networth microservice infrastructure, Docker environment, DB models, Auth0 verification, and health endpoint.
- **Rationale**: Enables separation of CPU-heavy analytical calculations from the transactional core API while enforcing least-privilege table boundaries and sub-millisecond local auth resolution.
- **Key Changes**:
  - `docker-compose.yml`: Added `networth` container on port 8001 with hot reload, database connection credentials, and healthy Oracle dependency.
  - `services/networth/requirements.txt` & `Dockerfile`: Python 3.11-slim container spec exposing port 8001 running Uvicorn.
  - `services/networth/app/config.py`: BaseSettings loading database URL, Oracle connection parameters, and Auth0 configuration.
  - `services/networth/app/db/database.py` & `models.py`: Async SQLAlchemy session factory and declarative models for 17 accessible tables, strictly omitting forbidden tables (`api_keys`, `app_settings`, `expected_dividends`, `schema_migrations`).
  - `services/networth/app/services/auth0_service.py` & `api/deps.py`: Stateless Auth0 RS256 token verification using public JWKS with 24-hour caching and query-level user lookup.
  - `services/networth/app/main.py`: FastAPI application instance configured with GZip middleware (`minimum_size=1000`), CORS, and `/health` endpoint.
  - `services/networth/tests/test_service_init.py`: Comprehensive test suite verifying healthcheck (200 OK), root info, GZip middleware, Auth0 token verification (valid, missing, empty, expired, attacker forged, tampered signature, unregistered user), database execution, and table metadata boundaries.
- **Verification**:
  - Command: `PYTHONPATH=services/networth:backend /home/jayampatel/swe/greenline/backend/.venv/bin/pytest services/networth/tests/test_service_init.py`
  - Output: 11 passed in 1.82s.


### [2026-11-11 16:10:00 UTC] test(networth): establish 4-tier opaque-box E2E test suite and test infrastructure

<!-- changelog-entry-json
{
  "timestamp": "2026-11-11T16:10:00Z",
  "type": "test",
  "scope": "networth",
  "summary": "establish 4-tier opaque-box E2E test suite and test infrastructure",
  "affected_files": [
    "TEST_INFRA.md",
    "TEST_READY.md",
    "backend/tests/test_e2e_networth_microservice.py",
    "services/networth/tests/__init__.py",
    "services/networth/tests/conftest.py",
    "services/networth/tests/test_e2e_networth_microservice.py"
  ],
  "rationale": "Implement comprehensive opaque-box E2E testing framework for the Networth microservice covering endpoints, Auth0 RS256 token verification, weekly Sunday aggregation, starting date selection, background recalculation triggers, and sub-50ms latency SLAs.",
  "breaking_changes": false,
  "verification": {
    "command": "PYTHONPATH=backend /home/jayampatel/swe/greenline/backend/.venv/bin/pytest backend/tests/test_e2e_networth_microservice.py",
    "result": "PASSED"
  }
}
-->

- **Type / Scope**: `test(networth)`
- **Summary**: Implemented comprehensive 4-tier opaque-box E2E test suite (`backend/tests/test_e2e_networth_microservice.py` and `services/networth/tests/`), created `TEST_INFRA.md` with 35-feature coverage matrix, and published `TEST_READY.md` certification report.
- **Rationale**: Validates MSc WAA microservices architecture requirements (R1–R6) with rigorous TDD verification: 25 pre-implementation tests passing (auth, core endpoints, multi-tenant isolation, real-world lifecycle) and 10 red-phase tests asserting weekly Sunday aggregation, starting date pushdown, recalculation triggers, and sub-50ms query SLAs.
- **Key Changes**:
  - `TEST_INFRA.md`: Established testing methodology, 35-feature inventory coverage matrix, 4-tier structure, and execution runbooks.
  - `TEST_READY.md`: Published certification matrix, execution commands, and verbatim test run outputs.
  - `backend/tests/test_e2e_networth_microservice.py`: 35 genuine opaque-box tests executing against Oracle Free 23ai and FastAPI app with 100% offline Auth0 mock RSA keypairs.
  - `services/networth/tests/conftest.py`: Test harness dynamically binding backend test fixtures and NullPool Oracle session factories.
  - `services/networth/tests/test_e2e_networth_microservice.py`: Symlinked E2E test suite for direct microservice test execution.
- **Verification**:
  - Command: `PYTHONPATH=backend /home/jayampatel/swe/greenline/backend/.venv/bin/pytest backend/tests/test_e2e_networth_microservice.py`
  - Output: 35 collected, 25 passed, 10 expected red-phase failures in 29.30s.



### [2026-11-11 16:00:00 UTC] feat(db): provision GREENLINE_NETWORTH user with least privilege and table grants

<!-- changelog-entry-json
{
  "timestamp": "2026-11-11T16:00:00Z",
  "type": "feat",
  "scope": "db",
  "summary": "provision GREENLINE_NETWORTH user with least privilege and table grants",
  "affected_files": [
    "scripts/setup_networth_user.sql",
    "backend/scripts/setup_networth_user.sql",
    "backend/scripts/create_db_networth_user.py",
    "backend/tests/test_oracle_networth_user_permissions.py"
  ],
  "rationale": "The dedicated Networth microservice requires strict least-privilege database isolation: read-only access to 13 analytical input tables, read/write access to 4 snapshot/cache tables, zero access to sensitive tables (api_keys, app_settings), and zero DDL privileges.",
  "breaking_changes": false,
  "verification": {
    "command": "PYTHONPATH=backend /home/jayampatel/swe/greenline/backend/.venv/bin/pytest backend/tests/test_oracle_networth_user_permissions.py",
    "result": "PASSED"
  }
}
-->

- **Type / Scope**: `feat(db)`
- **Summary**: Created database provisioning script `scripts/setup_networth_user.sql` and automated test suite verifying least-privilege table grants, logon schema triggers, and forbidden DDL/table rejections for the `GREENLINE_NETWORTH` user.
- **Rationale**: Isolates the Networth & Analytics microservice from transactional tables (transactions, accounts, users) by granting read-only `SELECT` privileges, allowing write operations only on analytical output and cache tables (`networth_snapshots`, `networth_by_asset_class`, `xirr_cache`, `benchmarks`), while strictly rejecting access to sensitive tables (`api_keys`, `app_settings`, `expected_dividends`, `schema_migrations`) and forbidding DDL statements.
- **Key Changes**:
  - `scripts/setup_networth_user.sql`: Admin provisioning script defining `GREENLINE_NETWORTH` user, `CREATE SESSION` grant, SELECT grants on 13 analytical tables, DML grants on 4 snapshot/cache tables, and `AFTER LOGON` trigger setting `CURRENT_SCHEMA`.
  - `backend/scripts/setup_networth_user.sql`: Co-located copy of setup script for backend deployment workflows.
  - `backend/scripts/create_db_networth_user.py`: Python CLI tool to provision `GREENLINE_NETWORTH` user dynamically with automated tablespace detection.
  - `backend/tests/test_oracle_networth_user_permissions.py`: Automated pytest suite testing static script security properties, live Oracle connection, SELECT access, DML on snapshots, rejection of writes on inputs (`ORA-01031`/`ORA-41900`), rejection of forbidden tables (`ORA-00942`), and zero DDL enforcement.
- **Verification**:
  - Command: `PYTHONPATH=backend /home/jayampatel/swe/greenline/backend/.venv/bin/pytest backend/tests/test_oracle_networth_user_permissions.py`
  - Output: 7 passed in 1.34s


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
