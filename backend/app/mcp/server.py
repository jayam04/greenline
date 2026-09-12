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

if __name__ == "__main__":
    mcp.run()

