# 🌿 Greenline: Project Roadmap

## Stack 3: UI Modernization & Portfolio Refinements

### ✅ Layer 1: Basic UI Enhancements (Completed in `s3l1-ui-fixes`)
- [x] Reposition & customize accounts layout and visibility on Net Worth (`/`) and Accounts (`/accounts`) pages with modal and local storage persistence.
- [x] Unified all-inclusive transaction ledger in Cashflow (`/cashflow` and `/cashflow/transactions`) with holding delta indicators (`+X shares` / `-X shares`) and blue dot styling.
- [x] Relocate routes from `/holdings` to `/investments/holdings` and `/transactions` to `/investments/transactions` with permanent redirects in `next.config.ts`.
- [x] Breadcrumb redesign: full hierarchical path navigation with clickable ancestors and sub-page sibling tabs.
- [x] Dynamic browser page titles (`<PAGE TITLE> · greenline`).
- [x] Interactive Donut Allocation chart with dynamic center hover state (security name, value, allocation percentage) without redundant legend.
- [x] 1-Day daily price change tracking: SQL window function optimization in backend portfolio router, 1D metrics toggle in Holdings tables.
- [x] Holdings page XIRR capping (`>= 1000%` -> `999%+`, `<= -1000%` -> `-999%+`).
- [x] 30-day recent window filtering on `/cashflow` overview ledger with single-letter category classification badges (`E`, `D`, `I`, `L`).

### 📋 Layer 2: Dividends
- [ ] Automatic dividend ingestion from Yahoo Finance.
- [ ] Realized P&L integration for dividends in portfolio valuation and return metrics.

---

## Stack 4: Advanced Extensibility & AI Integration

### 📋 Layer 1: Granular Import & Export
- [ ] Granular import/export models for specific accounts, transactions, and securities.
- [ ] Selective JSON/CSV schema validation and restore engine.

### 📋 Layer 2: MCP Server (Model Context Protocol)
- [ ] Dedicated Greenline MCP Server utilizing granular import/export layer.
- [ ] AI assistant integrations for automated trade logging, financial inquiries, and portfolio advisory.
