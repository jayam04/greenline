# greenline: TODO

## Draft

### Stack 3

#### Layer 1A: Basic UI
- User should be able to reposition accounts in Networth (/) page.
- In Cashflow (/cashflow) show all transactions instead of only day-to-day transactions.
- Move /holdings to /investments/holdings and /transactions to /investments/transactions
- Clicking on "Investments" or "Cashflows" should open dropdown if user is on (/investments or /investments/* or /cashflow or /cashflow/*)
- "Allocation" chart in Investments (/investments) page should not show assets below doughnut, instead it should show same security, % allocation etc, when hovered over securities area in doughnut chart.
- Cashflow Transactions table in /cashflow/transactions should remove selection between day-to-day, investments, and both and show all. 

#### Layer 1B: Basic UI
- All pages
    - Currently, breadcrumb is part of navbar, update it so it's looks like it's part of the page. So same background as of actual body.
    - Page title shown in browser should be <PAGE TITLE> (centered dot) greenline
- In networth page (/)
    - Order of Accounts should be same for graph selection and accounts page (http://localhost:3000/accounts).
    - Allow hiding accounts with extact 0 balance.
    - Remove Manage button from main page.
- In "http://localhost:3000/cashflow/transactions", show change in holdings instead of just holdings.
    - Holdings not shown in case of sell transaction
- Update breadcrumb
    - Show full path in breadcrumb
    - Allow navigating to parent pages using breadcrumb.
    - Add sub-pages to right side in the same row as breadcrumb.
- In "http://localhost:3000/investments",
    - Remove Day selection in Holdings table.
    - Allow user to optionally see 1d change in Holdings page.
- in "http://localhost:3000/investments/holdings",
    - Allow users to see 1day change.

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

### Stack 3 / Layer 1A: Basic UI
- [x] **Task 1: Account Repositioning & Visibility Modal on Networth (`/`) Page**
  - [x] Add "Edit" button to Accounts & Balances header in `src/app/page.tsx`
  - [x] Create `AccountCustomizationModal.tsx` for reordering (move up/down) and visibility toggling (hide/show)
  - [x] Persist customized ordering and hidden account IDs to `localStorage`
  - [x] Filter and sort accounts table on `/` according to saved configuration
- [x] **Task 2: Show All Transactions in Cashflow (`/cashflow`)**
  - [x] Fetch both `/cashflow` and `/transactions` in `src/app/cashflow/page.tsx`
  - [x] Unify day-to-day and investment trades into a single chronological ledger
- [x] **Task 3: Relocate Routes to `/investments/holdings` and `/investments/transactions`**
  - [x] Move `src/app/holdings/page.tsx` to `src/app/investments/holdings/page.tsx`
  - [x] Move `src/app/transactions/page.tsx` to `src/app/investments/transactions/page.tsx`
  - [x] Configure backward-compatible redirects in `next.config.ts`
  - [x] Update internal navigation links across Navbar, Dashboard, and breadcrumbs
- [x] **Task 4: Navbar Smart Dropdown Toggle for Active Sections**
  - [x] Toggle Investments dropdown when clicking "Investments" tab from `/investments/*`
  - [x] Toggle Cashflow dropdown when clicking "Cashflow" tab from `/cashflow/*`
- [x] **Task 5: Interactive Donut Allocation Hover in `/investments`**
  - [x] Remove bottom asset legend list from `AllocationChart.tsx`
  - [x] Implement dynamic center hover state displaying hovered security, valuation, and % allocation
- [x] **Task 6: Unified All-Inclusive Ledger in `/cashflow/transactions`**
  - [x] Remove 3-way mode switch buttons (`DAY_TO_DAY`, `INVESTMENTS`, `BOTH`)
  - [x] Always render all transactions in the ledger
  - [x] Update `TransactionsLedger.test.tsx` and Playwright E2E tests
