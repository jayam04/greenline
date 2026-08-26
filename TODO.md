# greenline: TODO

## Draft

### Stack 3

#### Layer 1: Basic UI
- User should be able to reposition accounts in Networth (/) page.
- In Cashflow (/cashflow) show all transactions instead of only day-to-day transactions.
- Move /holdings to /investments/holdings and /transactions to /investments/transactions
- Clicking on "Investments" or "Cashflows" should open dropdown if user is on (/investments or /investments/* or /cashflow or /cashflow/*)
- "Allocation" chart in Investments (/investments) page should not show assets below doughnut, instead it should show same security, % allocation etc, when hovered over securities area in doughnut chart.
- Cashflow Transactions table in /cashflow/transactions should remove selection between day-to-day, investments, and both and show all. 

#### Layer 2: Dividends
- Dividends are not added automatically from Yahoo finance
- Dividends are not added in Realized P&L.

### Stack 4

#### Layer 1: Advanced Import/Export
- Allow user to import/export specific accoutns, transactions, securities, etc. This should be supported by import/export models.

#### Layer 2: MCP Server
- Create a MCP server which uses new import export from previous layer and allow AI support.

### Next Steps

- Fix issues with Stack 2 and merge Stack 2.

## Actual Plan

### Stack 3 / Layer 1: Basic UI
- [ ] **Task 1: Account Repositioning & Visibility Modal on Networth (`/`) Page**
  - [ ] Add "Edit" button to Accounts & Balances header in `src/app/page.tsx`
  - [ ] Create `AccountCustomizationModal.tsx` for reordering (move up/down) and visibility toggling (hide/show)
  - [ ] Persist customized ordering and hidden account IDs to `localStorage`
  - [ ] Filter and sort accounts table on `/` according to saved configuration
- [ ] **Task 2: Show All Transactions in Cashflow (`/cashflow`)**
  - [ ] Fetch both `/cashflow` and `/transactions` in `src/app/cashflow/page.tsx`
  - [ ] Unify day-to-day and investment trades into a single chronological ledger
- [ ] **Task 3: Relocate Routes to `/investments/holdings` and `/investments/transactions`**
  - [ ] Move `src/app/holdings/page.tsx` to `src/app/investments/holdings/page.tsx`
  - [ ] Move `src/app/transactions/page.tsx` to `src/app/investments/transactions/page.tsx`
  - [ ] Configure backward-compatible redirects in `next.config.ts`
  - [ ] Update internal navigation links across Navbar, Dashboard, and breadcrumbs
- [ ] **Task 4: Navbar Smart Dropdown Toggle for Active Sections**
  - [ ] Toggle Investments dropdown when clicking "Investments" tab from `/investments/*`
  - [ ] Toggle Cashflow dropdown when clicking "Cashflow" tab from `/cashflow/*`
- [ ] **Task 5: Interactive Donut Allocation Hover in `/investments`**
  - [ ] Remove bottom asset legend list from `AllocationChart.tsx`
  - [ ] Implement dynamic center hover state displaying hovered security, valuation, and % allocation
- [ ] **Task 6: Unified All-Inclusive Ledger in `/cashflow/transactions`**
  - [ ] Remove 3-way mode switch buttons (`DAY_TO_DAY`, `INVESTMENTS`, `BOTH`)
  - [ ] Always render all transactions in the ledger
  - [ ] Update `TransactionsLedger.test.tsx` and Playwright E2E tests
