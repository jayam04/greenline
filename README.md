<div align="center">

# 🌿 Greenline

**Self-Hosted, Privacy-First Investment & Multi-Account Portfolio Tracker**

An elegant, real-time personal finance and investment analytics platform designed to aggregate multi-currency portfolios across brokerages, demat accounts, crypto wallets, and bank accounts. Features strict **FIFO cost lot accounting**, annualized **XIRR / TWR return tracking**, dynamic **Cashflow Sankey modeling**, **hierarchical spend taxonomy**, live **market price synchronization**, and **market benchmark overlays**.

[![Next.js](https://img.shields.io/badge/Next.js-16.3-black?style=flat&logo=next.js)](https://nextjs.org/)
[![React](https://img.shields.io/badge/React-19.2-61DAFB?style=flat&logo=react)](https://react.dev/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?style=flat&logo=fastapi)](https://fastapi.tiangolo.com/)
[![Python](https://img.shields.io/badge/Python-3.11-3776AB?style=flat&logo=python)](https://python.org/)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?style=flat&logo=docker)](https://www.docker.com/)
[![Showcase Website](https://img.shields.io/badge/Showcase-Interactive%20Tour-10B981?style=flat&logo=safari)](https://jayam04.github.io/greenline/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

</div>

> 🌐 **Live Interactive Showcase**: Explore the live, interactive showcase website featuring screenshot galleries, deep-dive architectural comparisons, and quickstart instructions at [**jayam04.github.io/greenline**](https://jayam04.github.io/greenline/) (or open `docs/index.html` locally).

---

## 📸 Interface Showcase

### 1. Unified Net Worth & Multi-Account Dashboard
Track marked-to-market valuations across individual accounts or aggregated across your entire net worth in a unified master currency (EUR). Switch seamlessly between **Value** and **Performance (P&L %)** modes, view interactive entity allocation donuts, and track calendar-year cashflow snapshots alongside live liquid cash vs securities breakdown.

![Net Worth Dashboard](.github/data/networth-dashboard.png)

---

### 2. Investment Portfolio Analytics & Asset Allocation
Dedicated portfolio dashboard offering deep capital breakdowns (Invested Capital, Price Gain, Realized Gain, Total Return, XIRR, and TWR). Visualize portfolio diversification with 3-way toggle allocation rings across **Individual Positions**, **Economic Sectors**, and **Asset Classes** (Equities, ETFs, Crypto, Cash).

![Investments Portfolio Dashboard](.github/data/investments-portfolio.png)

---

### 3. Positions & Tax-Lot FIFO Holdings Ledger
Deep-dive into active positions with 2-line Unrealized and Realized P&L breakdowns, annualized XIRR metrics, sorting across every column, and expand open FIFO cost lots with full buy-date granularity and unit cost basis (incorporating acquisition fees and taxes). Fully liquidated securities automatically move to a dedicated **Closed Positions** ledger.

![Positions & Holdings](.github/data/holdings.png)

---

### 4. Interactive Cashflow & Sankey Flow Engine
Visualize how money moves from all income sources through classification tiers (**Essential**, **Discretionary**, **Luxury**, **Investment**) down to specific subcategories. Features multi-account split payment methods, multi-category line-item itemization, negative value adjustments (reimbursements/splits), and flexible timeframe filters (This Month, Last Month, YTD, All Time).

![Cashflow Sankey Flow](.github/data/cashflow-sankey.png)

---

### 5. 5-Level Category Taxonomy & Multi-Period Comparative Spends
Organize your financial life into a flexible category hierarchy spanning **Income**, **Spends**, **Investments & Savings**, and **Account Transfers**. Compare expenses across dynamic timeframes (This Month vs. Last Month vs. Custom Periods) with automated parent-category aggregations.

![Category Hierarchy](.github/data/categories-hierarchy.png)

---

### 6. Unified Trade & Transaction Ledger
Manage buy, sell, dividend, split, deposit, and withdrawal records. Features live typeahead security search with automatic Yahoo Finance metadata registration (ISIN, Industry, Sector, Asset Type), funding account routing, and automated FIFO tax-lot calculation.

![Transactions Ledger](.github/data/transactions-ledger.png)

---

### 7. One-Click Privacy & Streaming Mode
Instantly mask all net worth figures, position amounts, cash balances, and trade values when presenting in public, recording videos, or streaming screen captures.

![Privacy Mode](.github/data/privacy-mode.png)

---

## ✨ Core Features & Financial Engineering

- **💼 Comprehensive Demat & Cash Accounting**: Demat and trading accounts accurately reflect total valuation (`cash_balance + securities_value`), preventing double-counting or disconnected liquid balances.
- **🏦 Funding Account Routing**: Seamlessly fund trades and investments from external bank accounts while keeping asset holdings registered inside the target brokerage.
- **📐 Strict First-In, First-Out (FIFO) Cost-Basis Engine**: Chronologically depletes purchase lots to compute realized capital gains and remaining cost lots, fully compliant with international tax accounting standards.
- **💵 Precision Fees & Taxes Capitalization**: Purchase brokerage fees and taxes are capitalized into open lot cost basis, while sale charges are correctly factored into net realized P&L without double-deducting funded bank balances.
- **📈 Advanced Performance Metrics**:
  - **XIRR**: Annualized Internal Rate of Return calculated over real cash-flow schedules using Newton-Raphson optimization.
  - **TWR**: True Time-Weighted Return eliminating distortion from external deposits and withdrawals.
  - **P&L % Performance Mode**: Track actual profit & loss percentage curves over custom timeframes (1D, 1W, 1M, YTD, 1Y, Max).
- **⚖️ Market Benchmark Overlays**: Overlay normalized percentage returns of the **S&P 500 (`^GSPC`)**, **Bitcoin (`BTC-USD`)**, and **Nifty 50 (`^NSEI`)** directly on your portfolio chart.
- **🍩 Interactive Visualizations**: Recharts-powered asset allocation donuts, Net Worth timeline area charts, and responsive multi-depth Sankey diagrams.
- **🔒 Complete Data Sovereignty**: One-click full portfolio JSON export and restore capabilities. Your financial data stays entirely on your private hardware.

---

## 🛠️ Architecture & Tech Stack

```mermaid
graph TD
    subgraph Frontend["Frontend (Next.js 16 + React 19)"]
        UI["Tailwind CSS + Lucide + Recharts"]
        ClientAPI["Typed Fetch API Client"]
    end

    subgraph Backend["Backend (FastAPI + Python 3.11)"]
        Router["REST Routers (Auth, Accounts, Portfolio, Cashflow, Categories)"]
        FIFO["FIFO Engine & XIRR Calculator"]
        SnapshotEngine["Daily & Annual Snapshot Engine"]
        Scheduler["APScheduler (Nightly Sync & Snapshots)"]
    end

    subgraph Database["Storage Layer"]
        Oracle[("Oracle Autonomous Database & Oracle 23ai Free (python-oracledb)")]
    end

    subgraph External["External Services"]
        Yahoo["Yahoo Finance API (yfinance)"]
    end

    UI --> ClientAPI
    ClientAPI -->|JWT + REST API| Router
    Router --> FIFO
    Router --> SnapshotEngine
    FIFO --> Oracle
    SnapshotEngine --> Oracle
    Scheduler --> SnapshotEngine
    Scheduler --> Yahoo
```

| Layer | Technologies |
| :--- | :--- |
| **Frontend** | [Next.js 16](https://nextjs.org/) (App Router, Turbopack), [React 19](https://react.dev/), [Tailwind CSS v4](https://tailwindcss.com/), [Lucide Icons](https://lucide.dev/), [Recharts](https://recharts.org/) |
| **Backend** | [FastAPI](https://fastapi.tiangolo.com/), [SQLAlchemy 2.0](https://www.sqlalchemy.org/) (Async), [Pydantic v2](https://docs.pydantic.dev/), [APScheduler](https://apscheduler.readthedocs.io/) |
| **Database** | Oracle Autonomous Database & Oracle 23ai Free ([python-oracledb](https://python-oracledb.readthedocs.io/)) |
| **Market Data** | Yahoo Finance ([yfinance](https://github.com/ranaroussi/yfinance)) |
| **Testing** | [Pytest](https://docs.pytest.org/), [Vitest](https://vitest.dev/), [Playwright](https://playwright.dev/) |
| **Containers** | Docker & Docker Compose (Multi-stage development & production builds) |

---

## 🚀 Quick Start with Docker

### Prerequisites
- [Docker](https://docs.docker.com/get-docker/) (v24+)
- [Docker Compose](https://docs.docker.com/compose/) (v2+)

### 1. Clone the Repository
```bash
git clone https://github.com/jayam04/greenline.git
cd greenline
```

### 2. Start in Development Mode (Live Hot-Reloading)
Spins up the Next.js Turbopack dev server and FastAPI with automatic file-watch reloads:
```bash
docker compose up -d
```

Open [http://localhost:3000](http://localhost:3000) in your browser.

- **Default Admin User**: `admin`
- **Default Password**: `admin123`
- **Backend API Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)

---

### 3. Build & Start in Production Mode (Optimized Standalone)
Compiles an optimized standalone production bundle with production multi-worker services:
```bash
# Production with Local Database container:
ENV=prod FRONTEND_TARGET=runner docker compose up --build -d

# Production with Oracle Cloud Database:
ENV=prod FRONTEND_TARGET=runner DB_TARGET=cloud docker compose up --build -d
```

### 4. Stopping Containers
```bash
docker compose down
```

---

## 💻 Local Development Setup (Without Docker)

### Networth Service Setup
```bash
cd services/networth
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Run database migrations and start FastAPI server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend Setup
```bash
cd frontend
npm ci

# Start Next.js development server
npm run dev
```

### Oracle Autonomous Database

Greenline operates exclusively on **Oracle Database**. In cloud production, it connects to Oracle Autonomous Database (ATP) using walletless one-way TLS authentication. In local testing and development, it uses an Oracle Free 23ai container (`gvenzl/oracle-free:slim-faststart`).

```bash
export DATABASE_URL='oracle+oracledb://@'
export ORACLE_USER='greenline_app'
export ORACLE_PASSWORD='...'
export ORACLE_DSN='(description=(address=(protocol=tcps)(host=...)(port=1521))(connect_data=(service_name=...))(security=(ssl_server_dn_match=yes)))'
```

`ORACLE_DSN` should be the TLS connect descriptor supplied by OCI. Keep credentials in a secret manager or environment, and URL encode special characters if credentials are embedded directly in `DATABASE_URL`. The driver uses Thin mode and does not require Oracle Client libraries.

The existing Networth service manages its financial schema through startup migrations. The separate history schema is provisioned with the SQL script below.

### Networth History Service

The `networth-history` service owns daily snapshot calculation and history in the separate Oracle schema `GREENLINE_NW_HISTORY`. It reads financial source tables from `ADMIN` and writes only its own snapshot tables.

1. Run `services/networth_history/scripts/setup_schema.sql` as the Oracle schema owner. Set a private schema password and configure `ORACLE_NETWORTH_HISTORY_PASSWORD` to match.
2. Set `ORACLE_NETWORTH_HISTORY_PASSWORD` to the same password and set `NETWORTH_HISTORY_SERVICE_TOKEN` to a long random secret.
3. Start the stack with `docker compose up --build`. The history service performs a per-user daily backfill and logs parity comparisons with existing weekly snapshots before its health check passes.

If Oracle reports `ORA-01017` and `GREENLINE_NW_HISTORY` already exists (for example, from an earlier run or a persisted database volume), reset its password as the Oracle schema owner and use that exact value in `.env`:

```sql
ALTER USER GREENLINE_NW_HISTORY IDENTIFIED BY "your-private-password";
```

Then recreate the history container with `docker compose up -d --force-recreate networth-history`.

The current API authenticates snapshot requests and proxies them to the private history service. Cashflow, trade, account, asset, and price mutations enqueue recalculations after commit; the history service also rebuilds every user's daily history nightly.

---

## 🧪 Running Automated Tests

Greenline adheres to a strict Test-Driven Development (TDD) protocol across all layers:

### Backend Tests (Pytest with Local Oracle Free Container)
Backend automated tests run against a local Oracle Free (`FREEPDB1`) container:
```bash
# Start local Oracle Free test container
docker compose --profile localdockerdb up oracle -d

# Execute backend test suite
cd services/networth
pytest tests
```

### Frontend Unit & Component Tests (Vitest)
Executes component tests for formatters, holdings tables, transactions ledgers, and modals:
```bash
cd frontend
npm test
```

### End-to-End Browser Tests (Playwright)
Executes full user journeys (Dashboard, Holdings FIFO expansion, Cashflow, Privacy mode):
```bash
cd frontend
npx playwright test
```

### Linting & Type Checking
```bash
# Backend linting with Ruff
ruff check services/networth/app services/networth/tests

# Frontend TypeScript check and ESLint
cd frontend
npx tsc --noEmit
npm run lint
```

---

## 📂 Project Structure

```text
greenline/
├── .github/
│   ├── data/                 # Visual showcase screenshots & assets
│   └── workflows/            # GitHub Actions CI/CD workflows
├── services/
│   ├── networth/             # Networth FastAPI service, database migrations, and pytest suite
│   ├── networth_history/      # Daily net-worth history API, worker, schema setup, and tests
│   └── community/            # Community FastAPI service
├── docs/                     # Static showcase website & documentation (GitHub Pages)
│   ├── assets/screenshots/   # High-resolution retina screenshots
│   ├── index.html            # Showcase landing page
│   ├── styles.css            # Modern Emerald & Slate styling
│   └── script.js             # Theme toggle & interactive lightbox
├── frontend/
│   ├── e2e/                  # Playwright End-to-End test suites
│   ├── src/
│   │   ├── app/              # Next.js App Router pages (Dashboard, Holdings, Cashflow, etc.)
│   │   ├── components/       # Reusable UI components (Sankey, Charts, Modals, Navbar)
│   │   └── lib/              # API clients & currency formatters
│   ├── Dockerfile
│   ├── package.json
│   ├── playwright.config.ts
│   └── vitest.config.mts
├── scripts/                  # Automated maintenance & screenshot capture utilities
├── data/                     # Persistent file storage and JSON backups
├── docker-compose.yml        # Unified Docker Compose (dev/prod, localdockerdb/cloud)
├── pyproject.toml            # Python tool configurations (Ruff, Pytest)
├── .gitignore
└── README.md
```

---

## 📄 License

Distributed under the [MIT License](LICENSE).
