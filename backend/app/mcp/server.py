import asyncio
from typing import List, Dict, Any, Optional
try:
    from mcp.server.mcpserver import MCPServer
except ImportError:
    from mcp.server.fastmcp import FastMCP as MCPServer
from sqlalchemy import select

from app.db.database import AsyncSessionLocal
from app.db.models import Account, Category, Asset, Transaction, ImportBatch, StagedRecord
from app.services.ai.staging_service import create_import_batch, stage_parsed_records, commit_import_batch

mcp = MCPServer("Greenline Finance MCP")

@mcp.tool()
async def get_ledger_context() -> Dict[str, Any]:
    """Returns list of active accounts, categories, and known assets for context mapping."""
    async with AsyncSessionLocal() as session:
        accs = (await session.execute(select(Account))).scalars().all()
        cats = (await session.execute(select(Category))).scalars().all()
        asts = (await session.execute(select(Asset))).scalars().all()
        return {
            "accounts": [{"account_id": a.account_id, "name": a.account_name, "currency": a.currency} for a in accs],
            "categories": [{"category_id": c.category_id, "name": c.name, "type": c.category_type} for c in cats],
            "assets": [{"asset_id": ast.asset_id, "symbol": ast.symbol, "name": ast.name} for ast in asts]
        }

@mcp.tool()
async def search_existing_transactions(
    account_id: Optional[int] = None,
    query: Optional[str] = None,
    limit: int = 20
) -> List[Dict[str, Any]]:
    """Searches existing investment transactions to check for duplicates."""
    async with AsyncSessionLocal() as session:
        stmt = select(Transaction).order_by(Transaction.transaction_date.desc()).limit(limit)
        if account_id:
            stmt = stmt.where(Transaction.account_id == account_id)
        res = await session.execute(stmt)
        txs = res.scalars().all()
        return [
            {
                "transaction_id": t.transaction_id,
                "date": str(t.transaction_date),
                "account_id": t.account_id,
                "asset_id": t.asset_id,
                "type": t.transaction_type,
                "amount": t.total_amount,
                "notes": t.notes
            }
            for t in txs
        ]

@mcp.tool()
async def create_staging_batch(
    filename: str,
    file_type: str = "pdf",
    target_account_id: Optional[int] = None,
    default_currency: str = "USD",
    custom_instructions: Optional[str] = None
) -> Dict[str, Any]:
    """Initializes an input staging batch session for AI document parsing."""
    async with AsyncSessionLocal() as session:
        batch = await create_import_batch(
            db=session,
            filename=filename,
            file_type=file_type,
            target_account_id=target_account_id,
            default_currency=default_currency,
            custom_instructions=custom_instructions
        )
        return {
            "batch_id": batch.batch_id,
            "filename": batch.filename,
            "status": batch.status
        }

@mcp.tool()
async def stage_transactions(
    batch_id: int,
    records: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """Populates staged records in an import batch and calculates duplicate matches."""
    async with AsyncSessionLocal() as session:
        staged = await stage_parsed_records(db=session, batch_id=batch_id, raw_records=records)
        return {
            "batch_id": batch_id,
            "staged_count": len(staged),
            "records": [
                {
                    "staged_id": s.staged_id,
                    "date": str(s.transaction_date),
                    "symbol": s.asset_symbol_raw,
                    "amount": s.total_amount,
                    "match_status": s.match_status,
                    "review_status": s.review_status
                }
                for s in staged
            ]
        }

@mcp.tool()
async def commit_batch(
    batch_id: int,
    record_ids: Optional[List[int]] = None
) -> Dict[str, Any]:
    """Executes the Final Green Flag: merges approved staged records into the live ledger."""
    async with AsyncSessionLocal() as session:
        return await commit_import_batch(db=session, batch_id=batch_id, record_ids=record_ids)

@mcp.tool()
async def read_categories() -> Dict[str, Any]:
    """
    Reference tool for categories and accounts.
    AI agents MUST query this tool first and choose strictly from the returned category IDs
    and account names.
    """
    from app.services.cashflow_engine import build_category_lineage_map
    async with AsyncSessionLocal() as session:
        cats = (await session.execute(select(Category))).scalars().all()
        accs = (await session.execute(select(Account))).scalars().all()
        lineage = await build_category_lineage_map(session)
        return {
            "categories": [
                {
                    "category_id": c.category_id,
                    "name": c.name,
                    "full_path": lineage.get(c.category_id, {}).get("full_path") or c.name,
                    "type": c.category_type,
                    "default_label": c.default_label
                }
                for c in cats
            ],
            "available_accounts": [
                {
                    "account_id": a.account_id,
                    "account_name": a.account_name,
                    "currency": a.currency or "EUR",
                    "account_type": a.account_type
                }
                for a in accs
            ]
        }

@mcp.tool()
async def read_cashflows(
    month: Optional[str] = None,
    bank_account: Optional[str] = None,
    category_id: Optional[int] = None,
    merchant: Optional[str] = None,
    limit: int = 50
) -> Dict[str, Any]:
    """
    Reads cashflow statements with signed amounts (+ve income, -ve expense) and filters.
    """
    import calendar
    import datetime
    from sqlalchemy import desc
    from sqlalchemy.orm import selectinload
    from app.db.models import CashflowTransaction, CashflowPayment, CashflowItem

    async with AsyncSessionLocal() as session:
        stmt = (
            select(CashflowTransaction)
            .options(
                selectinload(CashflowTransaction.payments).selectinload(CashflowPayment.account),
                selectinload(CashflowTransaction.items).selectinload(CashflowItem.category)
            )
            .order_by(desc(CashflowTransaction.transaction_date))
        )

        if month:
            parts = month.strip().split("-")
            year, m_num = int(parts[0]), int(parts[1])
            start_d = datetime.date(year, m_num, 1)
            _, last_day = calendar.monthrange(year, m_num)
            end_d = datetime.date(year, m_num, last_day)
            stmt = stmt.where(CashflowTransaction.transaction_date >= start_d, CashflowTransaction.transaction_date <= end_d)

        if merchant:
            stmt = stmt.where(CashflowTransaction.title.ilike(f"%{merchant.strip()}%"))

        res = await session.execute(stmt)
        txs = res.scalars().all()

        filtered = []
        for tx in txs:
            if bank_account:
                ba = bank_account.strip().lower()
                if not any(str(p.account_id) == ba or (p.account and p.account.account_name.lower() == ba) for p in tx.payments):
                    continue
            if category_id is not None:
                if not any(i.category_id == category_id for i in tx.items):
                    continue
            filtered.append(tx)

        paged = filtered[:limit]
        statements = []
        for tx in paged:
            is_expense = (tx.transaction_kind or "").upper() == "EXPENSE"
            statements.append({
                "cashflow_id": tx.cashflow_id,
                "date": str(tx.transaction_date),
                "merchant": tx.title,
                "total_amount": -abs(tx.total_amount) if is_expense else abs(tx.total_amount),
                "currency": tx.currency or "EUR",
                "transaction_kind": tx.transaction_kind or "EXPENSE",
                "notes": tx.notes,
                "payments": [
                    {
                        "account_id": p.account_id,
                        "account_name": p.account.account_name if p.account else f"Account #{p.account_id}",
                        "amount": p.amount
                    }
                    for p in tx.payments
                ],
                "items": [
                    {
                        "category_id": i.category_id,
                        "category_name": i.category.name if i.category else f"Category #{i.category_id}",
                        "amount": -abs(i.amount) if is_expense else abs(i.amount),
                        "description": i.description,
                        "label": i.label
                    }
                    for i in tx.items
                ]
            })

        return {"statements": statements, "count": len(statements)}

@mcp.tool()
async def mutate_cashflow(
    operations: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Bulk or single mutate cashflow transactions.
    Rules:
    - merchant: specific counterparty only
    - category_id: strict ID from read_categories
    - account_name: strict match
    - signed amounts: negative for expense, positive for income
    - double-entry balance check: sum(payments) == sum(items)
    """
    import datetime
    from app.db.models import CashflowTransaction, CashflowPayment, CashflowItem

    async with AsyncSessionLocal() as session:
        acc_res = await session.execute(select(Account))
        all_accounts = acc_res.scalars().all()
        acc_by_name = {a.account_name.strip().lower(): a for a in all_accounts}
        acc_by_id = {a.account_id: a for a in all_accounts}

        cat_res = await session.execute(select(Category))
        all_categories = cat_res.scalars().all()
        cat_by_id = {c.category_id: c for c in all_categories}

        results = []
        for op in operations:
            action = (op.get("action") or "create").strip().lower()
            if action == "delete":
                cid = op.get("cashflow_id")
                if cid:
                    dtx = (await session.execute(select(CashflowTransaction).where(CashflowTransaction.cashflow_id == cid))).scalar_one_or_none()
                    if dtx:
                        await session.delete(dtx)
                continue

            merchant = (op.get("merchant") or "").strip()
            if not merchant or merchant.lower() in {"expense", "transaction", "payment", "misc", "unknown"}:
                raise ValueError(f"Invalid merchant: '{merchant}'. Specific merchant name required.")

            payments = op.get("payments") or []
            items = op.get("items") or []
            if not payments or not items:
                raise ValueError("Both payments and items are required.")

            resolved_pmts = []
            for p in payments:
                if p.get("account_id") and p["account_id"] in acc_by_id:
                    resolved_pmts.append((p["account_id"], float(p["amount"])))
                elif p.get("account_name"):
                    aname = p["account_name"].strip().lower()
                    if aname in acc_by_name:
                        resolved_pmts.append((acc_by_name[aname].account_id, float(p["amount"])))
                    else:
                        raise ValueError(f"Account '{p['account_name']}' not found.")
                else:
                    raise ValueError("account_id or account_name required in payments.")

            resolved_itms = []
            for itm in items:
                cid = itm.get("category_id")
                if cid not in cat_by_id:
                    raise ValueError(f"Category ID {cid} not found.")
                resolved_itms.append((cid, float(itm["amount"]), itm.get("description"), itm.get("label")))

            sum_p = round(sum(amt for _, amt in resolved_pmts), 2)
            sum_i = round(sum(amt for _, amt, _, _ in resolved_itms), 2)
            if sum_p != sum_i:
                raise ValueError(f"Balance check failed: Payments ({sum_p}) != Items ({sum_i})")

            kind = "EXPENSE" if sum_i < 0 else ("INCOME" if sum_i > 0 else "TRANSFER")
            tx_date_str = op.get("date")
            tx_date = datetime.date.fromisoformat(tx_date_str) if tx_date_str else datetime.date.today()

            tx = CashflowTransaction(
                transaction_date=tx_date,
                title=merchant,
                total_amount=round(abs(sum_i), 2),
                currency=op.get("currency") or "EUR",
                transaction_kind=kind,
                notes=op.get("notes")
            )
            session.add(tx)
            await session.flush()

            for aid, amt in resolved_pmts:
                session.add(CashflowPayment(cashflow_id=tx.cashflow_id, account_id=aid, amount=amt))
            for cid, amt, desc, lbl in resolved_itms:
                session.add(CashflowItem(cashflow_id=tx.cashflow_id, category_id=cid, amount=round(abs(amt), 2), description=desc, label=lbl))

            results.append({"cashflow_id": tx.cashflow_id, "merchant": merchant, "amount": sum_i, "kind": kind})

        await session.commit()
        return {"results": results, "status": "success"}

@mcp.tool()
async def read_stock_transactions(
    account: Optional[str] = None,
    asset: Optional[str] = None,
    transaction_type: Optional[str] = None,
    month: Optional[str] = None,
    limit: int = 50
) -> Dict[str, Any]:
    """
    Fetch existing stocks, valid investment accounts, and recent transactions.
    AI MUST call this tool first before executing any buy/sell/dividend trade to look up
    valid account names, check if the asset already exists, and obtain asset_id or symbol.
    """
    import calendar
    from app.db.models import Transaction, Asset
    from sqlalchemy.orm import aliased

    async with AsyncSessionLocal() as session:
        # Accounts
        acc_res = await session.execute(select(Account).order_by(Account.account_name))
        all_accounts = [
            {"account_id": a.account_id, "account_name": a.account_name, "currency": a.currency, "type": a.account_type}
            for a in acc_res.scalars().all()
        ]

        # Assets
        asset_res = await session.execute(select(Asset).order_by(Asset.symbol))
        all_assets = [
            {"asset_id": a.asset_id, "symbol": a.symbol, "name": a.name, "type": a.asset_type, "currency": a.currency, "exchange": a.exchange}
            for a in asset_res.scalars().all()
        ]

        # Transactions
        FundingAccount = aliased(Account)
        stmt = (
            select(Transaction, Account.account_name, Asset.symbol, Asset.name, FundingAccount.account_name)
            .outerjoin(Account, Transaction.account_id == Account.account_id)
            .outerjoin(FundingAccount, Transaction.funding_account_id == FundingAccount.account_id)
            .outerjoin(Asset, Transaction.asset_id == Asset.asset_id)
            .order_by(desc(Transaction.transaction_date), desc(Transaction.transaction_id))
        )

        if month:
            parts = month.strip().split("-")
            year, m_num = int(parts[0]), int(parts[1])
            start_d = datetime.date(year, m_num, 1)
            _, last_day = calendar.monthrange(year, m_num)
            end_d = datetime.date(year, m_num, last_day)
            stmt = stmt.where(Transaction.transaction_date >= start_d, Transaction.transaction_date <= end_d)

        if transaction_type:
            stmt = stmt.where(Transaction.transaction_type == transaction_type.strip().lower())

        res = await session.execute(stmt)
        rows = res.all()

        filtered = []
        for tx, acc_name, symbol, asset_name, f_acc in rows:
            if account:
                ac_str = account.strip().lower()
                if str(tx.account_id) != ac_str and (acc_name or "").lower() != ac_str:
                    continue
            if asset:
                as_str = asset.strip().lower()
                if str(tx.asset_id) != as_str and (symbol or "").lower() != as_str:
                    continue
            filtered.append({
                "transaction_id": tx.transaction_id,
                "account_id": tx.account_id,
                "account_name": acc_name,
                "asset_id": tx.asset_id,
                "asset_symbol": symbol,
                "asset_name": asset_name,
                "transaction_type": tx.transaction_type,
                "date": str(tx.transaction_date),
                "quantity": tx.quantity,
                "price_per_unit": tx.price_per_unit,
                "fees": tx.fees or 0.0,
                "taxes": tx.taxes or 0.0,
                "total_amount": tx.total_amount,
                "notes": tx.notes
            })

        return {
            "available_assets": all_assets,
            "available_accounts": all_accounts,
            "transactions": filtered[:limit],
            "total_count": len(filtered)
        }

@mcp.tool()
async def mutate_stock_transactions(
    operations: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Mutate stock transactions (buy, sell, dividend, bonus, split, deposit, withdrawal).
    AI MUST call read_stock_transactions first to obtain exact account_name and check available_assets.
    If the asset does not exist in available_assets, set force_create_asset=true to create it automatically.
    Creating accounts is strictly forbidden.
    """
    from app.db.models import Transaction, Asset
    from app.services.fifo_engine import recalculate_all_lots
    from app.services.snapshot_engine import recalculate_past_snapshots
    from app.api.routers.transactions import _ensure_price_history_for_tx, cleanup_orphan_transaction_prices

    async with AsyncSessionLocal() as session:
        acc_res = await session.execute(select(Account))
        all_accounts = acc_res.scalars().all()
        acc_by_id = {a.account_id: a for a in all_accounts}
        acc_by_name = {a.account_name.strip().lower(): a for a in all_accounts}
        acc_summary = [{"id": a.account_id, "name": a.account_name} for a in all_accounts]

        asset_res = await session.execute(select(Asset))
        all_assets = list(asset_res.scalars().all())
        asset_by_id = {a.asset_id: a for a in all_assets}
        asset_by_symbol = {a.symbol.strip().upper(): a for a in all_assets if a.symbol}

        results = []
        earliest_date = datetime.date.today()

        for op in operations:
            action = (op.get("action") or "create").strip().lower()
            if action == "delete":
                tid = op.get("transaction_id")
                if tid:
                    dtx = (await session.execute(select(Transaction).where(Transaction.transaction_id == tid))).scalar_one_or_none()
                    if dtx:
                        if dtx.transaction_date < earliest_date:
                            earliest_date = dtx.transaction_date
                        t_asset = dtx.asset_id
                        await session.delete(dtx)
                        await session.commit()
                        if t_asset:
                            await cleanup_orphan_transaction_prices(session, t_asset)
                            await session.commit()
                continue

            # Resolve Account
            acc = None
            if op.get("account_id"):
                acc = acc_by_id.get(op["account_id"])
            elif op.get("account_name"):
                acc = acc_by_name.get(op["account_name"].strip().lower())
            if not acc:
                raise ValueError(f"Account '{op.get('account_name') or op.get('account_id')}' not found. Valid accounts: {acc_summary}. Creating accounts is forbidden.")

            # Resolve Asset
            target_asset = None
            if op.get("asset_id"):
                target_asset = asset_by_id.get(op["asset_id"])
            elif op.get("symbol"):
                target_asset = asset_by_symbol.get(op["symbol"].strip().upper())

            t_type = (op.get("transaction_type") or "buy").strip().lower()
            if t_type in ["buy", "sell", "dividend", "bonus", "split"] and not target_asset:
                if op.get("force_create_asset"):
                    sym = (op.get("symbol") or "UNKNOWN").strip().upper()
                    target_asset = Asset(
                        symbol=sym,
                        name=op.get("asset_name") or sym,
                        asset_type=op.get("asset_type") or "stock",
                        currency=op.get("asset_currency") or acc.currency or "USD",
                        exchange=op.get("exchange")
                    )
                    session.add(target_asset)
                    await session.flush()
                    asset_by_id[target_asset.asset_id] = target_asset
                    asset_by_symbol[sym] = target_asset
                else:
                    known = [{"id": a.asset_id, "symbol": a.symbol} for a in all_assets]
                    raise ValueError(f"Asset '{op.get('symbol')}' not found. Available assets: {known}. Set force_create_asset=true to create it automatically.")

            # Date & amounts
            tx_d_str = op.get("date")
            tx_date = datetime.date.fromisoformat(tx_d_str) if tx_d_str else datetime.date.today()
            if tx_date < earliest_date:
                earliest_date = tx_date

            qty = float(op["quantity"]) if op.get("quantity") is not None else None
            price = float(op["price_per_unit"]) if op.get("price_per_unit") is not None else None
            fees = float(op.get("fees") or 0.0)
            taxes = float(op.get("taxes") or 0.0)

            if op.get("total_amount") is not None:
                tot_amt = round(float(op["total_amount"]), 2)
            elif qty is not None and price is not None:
                base = qty * price
                tot_amt = round(base + fees + taxes if t_type == "buy" else (base - fees - taxes if t_type == "sell" else base), 2)
            else:
                tot_amt = round(fees + taxes, 2)

            new_tx = Transaction(
                account_id=acc.account_id,
                asset_id=target_asset.asset_id if target_asset else None,
                transaction_type=t_type,
                transaction_date=tx_date,
                quantity=qty,
                price_per_unit=price,
                fees=fees,
                taxes=taxes,
                total_amount=tot_amt,
                notes=op.get("notes"),
                source="mcp_ai"
            )
            session.add(new_tx)
            await session.flush()
            await _ensure_price_history_for_tx(session, new_tx)
            results.append({
                "transaction_id": new_tx.transaction_id,
                "account": acc.account_name,
                "asset": target_asset.symbol if target_asset else None,
                "type": t_type,
                "amount": tot_amt
            })

        await session.commit()
        await recalculate_all_lots(session)
        await recalculate_past_snapshots(session, start_date=earliest_date)
        return {"results": results, "status": "success"}

if __name__ == "__main__":
    mcp.run()


