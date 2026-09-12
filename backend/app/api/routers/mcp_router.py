import datetime
import calendar
from typing import List, Optional, Any, Union
from fastapi import APIRouter, Depends, HTTPException, status, Query, Body, Request
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from sqlalchemy.orm import selectinload, aliased

from app.db.database import get_db
from app.db.models import CashflowTransaction, CashflowPayment, CashflowItem, Account, Category, User, Transaction, Asset
from app.schemas.mcp_schemas import (
    MCPCashflowOperation, MCPCashflowMutateRequest, MCPCashflowMutateResponse,
    MCPCashflowReadResponse, MCPCashflowStatement, MCPCashflowPaymentResponse,
    MCPCashflowItemResponse, MCPCategoriesResponse, MCPCategoryItem, MCPAvailableAccount
)
from app.schemas.mcp_stock_schemas import (
    MCPStockMutateRequest, MCPStockMutateResponse, MCPStockReadResponse,
    MCPStockTransactionResponse, MCPStockAssetItem, MCPStockOperation
)
from app.services.cashflow_engine import build_category_lineage_map
from app.services.fifo_engine import recalculate_all_lots
from app.services.snapshot_engine import recalculate_past_snapshots
from app.services.dividend_engine import sync_dividends_for_asset
from app.api.routers.transactions import _ensure_price_history_for_tx, cleanup_orphan_transaction_prices
from app.api.deps import get_current_user

router = APIRouter(prefix="/mcp", tags=["mcp"])

GENERIC_MERCHANT_NAMES = {
    "expense", "expenses", "income", "incomes", "transaction",
    "transactions", "payment", "payments", "title", "misc", "unknown", "item", "items"
}

def _build_statement(tx: CashflowTransaction, lineage_map: dict) -> MCPCashflowStatement:
    is_expense = (tx.transaction_kind or "").upper() == "EXPENSE"
    # Signed total: negative for expense, positive for income
    signed_total = -abs(tx.total_amount) if is_expense else abs(tx.total_amount)

    pmts = []
    for p in tx.payments:
        pmts.append(MCPCashflowPaymentResponse(
            payment_id=p.payment_id,
            account_id=p.account_id,
            account_name=p.account.account_name if p.account else f"Account #{p.account_id}",
            amount=p.amount,
            currency=p.account.currency if p.account and p.account.currency else "EUR"
        ))

    items = []
    for i in tx.items:
        signed_item_amount = -abs(i.amount) if is_expense else abs(i.amount)
        items.append(MCPCashflowItemResponse(
            item_id=i.item_id,
            category_id=i.category_id,
            category_name=i.category.name if i.category else f"Category #{i.category_id}",
            amount=signed_item_amount,
            description=i.description,
            label=i.label
        ))

    return MCPCashflowStatement(
        cashflow_id=tx.cashflow_id,
        date=tx.transaction_date,
        merchant=tx.title,
        total_amount=signed_total,
        currency=tx.currency or "EUR",
        transaction_kind=tx.transaction_kind or "EXPENSE",
        notes=tx.notes,
        payments=pmts,
        items=items
    )

@router.get("/categories", response_model=MCPCategoriesResponse)
async def get_mcp_categories(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Reference endpoint for categories and accounts.
    AI agents MUST query this endpoint first and choose strictly from the returned category IDs
    and account names. Do not invent new categories.
    """
    # 1. Categories
    cat_stmt = select(Category).order_by(Category.category_type, Category.name)
    cat_res = await db.execute(cat_stmt)
    cats = cat_res.scalars().all()
    lineage_map = await build_category_lineage_map(db)

    cat_items = []
    for c in cats:
        meta = lineage_map.get(c.category_id, {})
        cat_items.append(MCPCategoryItem(
            category_id=c.category_id,
            name=c.name,
            full_path=meta.get("full_path") or c.name,
            category_type=c.category_type,
            default_label=c.default_label
        ))

    # 2. Available accounts
    acc_stmt = select(Account).order_by(Account.account_name)
    acc_res = await db.execute(acc_stmt)
    accs = acc_res.scalars().all()

    acc_items = [
        MCPAvailableAccount(
            account_id=a.account_id,
            account_name=a.account_name,
            currency=a.currency or "EUR",
            account_type=a.account_type
        )
        for a in accs
    ]

    return MCPCategoriesResponse(categories=cat_items, available_accounts=acc_items)

@router.get("/cashflow", response_model=MCPCashflowReadResponse)
async def read_mcp_cashflow(
    month: Optional[str] = Query(None, description="Month in YYYY-MM format, e.g. 2026-09"),
    bank_account: Optional[str] = Query(None, description="Account name or ID to filter by"),
    category_id: Optional[int] = Query(None, description="Exact category ID to filter by"),
    merchant: Optional[str] = Query(None, description="Search term for merchant name"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Read cashflow statements with signed amounts and filtering.
    - Signed convention: Incomes are positive (+), expenses are negative (-).
    - Filters: month (YYYY-MM), bank_account, category_id, merchant search.
    """
    stmt = (
        select(CashflowTransaction)
        .options(
            selectinload(CashflowTransaction.payments).selectinload(CashflowPayment.account),
            selectinload(CashflowTransaction.items).selectinload(CashflowItem.category)
        )
        .order_by(desc(CashflowTransaction.transaction_date), desc(CashflowTransaction.cashflow_id))
    )

    if month:
        try:
            parts = month.strip().split("-")
            year, m_num = int(parts[0]), int(parts[1])
            start_d = datetime.date(year, m_num, 1)
            _, last_day = calendar.monthrange(year, m_num)
            end_d = datetime.date(year, m_num, last_day)
            stmt = stmt.where(CashflowTransaction.transaction_date >= start_d, CashflowTransaction.transaction_date <= end_d)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid month format. Expected YYYY-MM, e.g. 2026-09")

    if merchant:
        stmt = stmt.where(CashflowTransaction.title.ilike(f"%{merchant.strip()}%"))

    res = await db.execute(stmt)
    all_txs = res.scalars().all()

    # Filter in-memory for relationship-level filters (bank_account and category_id)
    filtered = []
    for tx in all_txs:
        if bank_account:
            ba = bank_account.strip().lower()
            acc_match = any(
                str(p.account_id) == ba or (p.account and p.account.account_name.lower() == ba)
                for p in tx.payments
            )
            if not acc_match:
                continue

        if category_id is not None:
            cat_match = any(i.category_id == category_id for i in tx.items)
            if not cat_match:
                continue

        filtered.append(tx)

    total_count = len(filtered)
    paged_txs = filtered[offset : offset + limit]
    lineage_map = await build_category_lineage_map(db)

    statements = [_build_statement(tx, lineage_map) for tx in paged_txs]
    return MCPCashflowReadResponse(statements=statements, total_count=total_count)

@router.post("/cashflow", response_model=MCPCashflowMutateResponse)
async def mutate_mcp_cashflow(
    payload: MCPCashflowMutateRequest = Body(
        ...,
        description="Batch or single cashflow mutate request containing operations to create, update, or delete."
    ),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Bulk or single mutate endpoint for cashflows (create, update, delete).
    Rules:
    - Merchant: Counterparty name only (e.g. 'Tesco', 'Employer'). Generic titles are rejected.
    - Category ID: Must be an exact, valid category_id from GET /api/v1/mcp/categories.
    - Payment Account: account_name is strictly matched against existing accounts.
    - Signed amounts: Incomes are positive (+), expenses are negative (-).
    - Double-entry balance: sum(payments.amount) MUST equal sum(items.amount).
    """
    operations = payload.operations
    if not operations:
        raise HTTPException(status_code=400, detail="No operations provided.")

    # Cache accounts and categories for strict matching
    acc_res = await db.execute(select(Account))
    all_accounts = acc_res.scalars().all()
    acc_by_id = {a.account_id: a for a in all_accounts}
    acc_by_name = {a.account_name.strip().lower(): a for a in all_accounts}
    valid_acc_names = [a.account_name for a in all_accounts]

    cat_res = await db.execute(select(Category))
    all_categories = cat_res.scalars().all()
    cat_by_id = {c.category_id: c for c in all_categories}

    results: List[MCPCashflowStatement] = []

    for op in operations:
        action = (op.action or "create").strip().lower()

        if action == "delete":
            if not op.cashflow_id:
                raise HTTPException(status_code=400, detail="cashflow_id is required for delete operation.")
            del_stmt = select(CashflowTransaction).where(CashflowTransaction.cashflow_id == op.cashflow_id)
            del_res = await db.execute(del_stmt)
            tx_to_del = del_res.scalar_one_or_none()
            if tx_to_del:
                await db.delete(tx_to_del)
            continue

        # For create and update, validate inputs
        if action == "create":
            if not op.merchant or not op.merchant.strip():
                raise HTTPException(status_code=400, detail="Specific merchant name is required for create operation.")
            m_clean = op.merchant.strip().lower()
            if m_clean in GENERIC_MERCHANT_NAMES or len(m_clean) < 2:
                raise HTTPException(
                    status_code=400,
                    detail=f"Generic merchant title '{op.merchant}' is not allowed. Please provide the exact counterparty or merchant name."
                )

            if not op.payments or not op.items:
                raise HTTPException(status_code=400, detail="Both payments and items are required for creating a cashflow.")

            tx_date = op.date or datetime.date.today()

        elif action == "update":
            if not op.cashflow_id:
                raise HTTPException(status_code=400, detail="cashflow_id is required for update operation.")
            fetch_stmt = (
                select(CashflowTransaction)
                .options(selectinload(CashflowTransaction.payments), selectinload(CashflowTransaction.items))
                .where(CashflowTransaction.cashflow_id == op.cashflow_id)
            )
            fetch_res = await db.execute(fetch_stmt)
            existing_tx = fetch_res.scalar_one_or_none()
            if not existing_tx:
                continue

            if op.merchant:
                m_clean = op.merchant.strip().lower()
                if m_clean in GENERIC_MERCHANT_NAMES:
                    raise HTTPException(status_code=400, detail="Generic merchant title is not allowed.")
                existing_tx.title = op.merchant.strip()

            if op.date:
                existing_tx.transaction_date = op.date
            if op.notes is not None:
                existing_tx.notes = op.notes

            # If payments and items are updated:
            if op.payments is not None and op.items is not None:
                pass # Will validate below
            else:
                await db.commit()
                await db.refresh(existing_tx)
                lineage_map = await build_category_lineage_map(db)
                results.append(_build_statement(existing_tx, lineage_map))
                continue

        # Common validation for payments and items (create or full update)
        # 1. Resolve and validate payments
        resolved_payments = []
        for p in (op.payments or []):
            acc_obj = None
            if p.account_id:
                acc_obj = acc_by_id.get(p.account_id)
                if not acc_obj:
                    raise HTTPException(status_code=400, detail=f"Account ID {p.account_id} not found. Valid accounts: {valid_acc_names}")
            elif p.account_name:
                acc_clean = p.account_name.strip().lower()
                acc_obj = acc_by_name.get(acc_clean)
                if not acc_obj:
                    raise HTTPException(status_code=400, detail=f"Account '{p.account_name}' not found. Valid accounts: {valid_acc_names}")
            else:
                raise HTTPException(status_code=400, detail="Each payment must provide account_id or account_name.")
            
            resolved_payments.append((acc_obj.account_id, p.amount))

        # 2. Resolve and validate categories
        resolved_items = []
        for itm in (op.items or []):
            if itm.category_id not in cat_by_id:
                raise HTTPException(
                    status_code=400,
                    detail=f"Category ID {itm.category_id} not found. Please choose a valid category_id from GET /api/v1/mcp/categories."
                )
            resolved_items.append((itm.category_id, itm.amount, itm.description, itm.label))

        # 3. Double-entry balance check
        sum_pmt = round(sum(amt for _, amt in resolved_payments), 2)
        sum_itm = round(sum(amt for _, amt, _, _ in resolved_items), 2)
        if sum_pmt != sum_itm:
            diff = round(sum_pmt - sum_itm, 2)
            raise HTTPException(
                status_code=400,
                detail=f"Double-entry balance check failed: Total payments ({sum_pmt:.2f}) does not equal total category items ({sum_itm:.2f}). Difference: {diff:.2f}"
            )

        # 4. Resolve transaction kind
        if sum_itm < 0:
            kind = "EXPENSE"
        elif sum_itm > 0:
            kind = "INCOME"
        else:
            kind = "TRANSFER"

        abs_total = round(abs(sum_itm), 2)

        if action == "create":
            tx = CashflowTransaction(
                transaction_date=tx_date,
                title=op.merchant.strip(),
                total_amount=abs_total,
                currency=op.currency or "EUR",
                transaction_kind=kind,
                notes=op.notes
            )
            db.add(tx)
            await db.flush()

            for acc_id, amt in resolved_payments:
                db.add(CashflowPayment(
                    cashflow_id=tx.cashflow_id,
                    account_id=acc_id,
                    amount=amt
                ))

            for c_id, amt, desc_txt, lbl in resolved_items:
                db.add(CashflowItem(
                    cashflow_id=tx.cashflow_id,
                    category_id=c_id,
                    amount=round(abs(amt), 2),
                    label=lbl,
                    description=desc_txt
                ))

            await db.commit()

            # Reload with relations
            stmt_reload = (
                select(CashflowTransaction)
                .options(
                    selectinload(CashflowTransaction.payments).selectinload(CashflowPayment.account),
                    selectinload(CashflowTransaction.items).selectinload(CashflowItem.category)
                )
                .where(CashflowTransaction.cashflow_id == tx.cashflow_id)
            )
            res_reload = await db.execute(stmt_reload)
            reloaded = res_reload.scalar_one()
            lineage_map = await build_category_lineage_map(db)
            results.append(_build_statement(reloaded, lineage_map))

        elif action == "update":
            existing_tx.total_amount = abs_total
            existing_tx.transaction_kind = kind
            existing_tx.payments.clear()
            existing_tx.items.clear()
            await db.flush()

            for acc_id, amt in resolved_payments:
                db.add(CashflowPayment(
                    cashflow_id=existing_tx.cashflow_id,
                    account_id=acc_id,
                    amount=amt
                ))

            for c_id, amt, desc_txt, lbl in resolved_items:
                db.add(CashflowItem(
                    cashflow_id=existing_tx.cashflow_id,
                    category_id=c_id,
                    amount=round(abs(amt), 2),
                    label=lbl,
                    description=desc_txt
                ))

            await db.commit()
            stmt_reload = (
                select(CashflowTransaction)
                .options(
                    selectinload(CashflowTransaction.payments).selectinload(CashflowPayment.account),
                    selectinload(CashflowTransaction.items).selectinload(CashflowItem.category)
                )
                .where(CashflowTransaction.cashflow_id == existing_tx.cashflow_id)
            )
            res_reload = await db.execute(stmt_reload)
            reloaded = res_reload.scalar_one()
            lineage_map = await build_category_lineage_map(db)
            results.append(_build_statement(reloaded, lineage_map))

    await db.commit()
    return MCPCashflowMutateResponse(
        results=results,
        message=f"Successfully processed {len(operations)} operation(s)."
    )

# -----------------------------------------------------------------------------
# Public MCP OpenAPI Endpoint
# -----------------------------------------------------------------------------
@router.get("/openapi.json", include_in_schema=False)
async def get_mcp_openapi_json(request: Request):
    """
    Public unauthenticated endpoint returning the curated OpenAPI 3.1.0 spec for MCP and AI agents.
    Allows one-click 'Import from URL' in ChatGPT Custom GPT Actions.
    """
    from app.services.mcp_openapi_service import build_mcp_openapi_spec
    forwarded_proto = request.headers.get("x-forwarded-proto", "https")
    forwarded_host = request.headers.get("x-forwarded-host") or request.headers.get("host")
    if forwarded_host and "ngrok" in forwarded_host:
        server_url = f"{forwarded_proto}://{forwarded_host}"
    else:
        server_url = "https://lark-unvented-festivity.ngrok-free.dev"
    return JSONResponse(content=build_mcp_openapi_spec(server_url))

# -----------------------------------------------------------------------------
# Stock / Investment Endpoints
# -----------------------------------------------------------------------------
def _build_stock_response(
    tx: Transaction,
    acc_name: str,
    acc_curr: str,
    symbol: Optional[str],
    asset_name: Optional[str],
    funding_acc_name: Optional[str] = None
) -> MCPStockTransactionResponse:
    return MCPStockTransactionResponse(
        transaction_id=tx.transaction_id,
        account_id=tx.account_id,
        account_name=acc_name,
        account_currency=acc_curr,
        funding_account_id=tx.funding_account_id,
        funding_account_name=funding_acc_name,
        asset_id=tx.asset_id,
        asset_symbol=symbol,
        asset_name=asset_name,
        transaction_type=tx.transaction_type,
        date=tx.transaction_date,
        quantity=tx.quantity,
        price_per_unit=tx.price_per_unit,
        fees=float(tx.fees or 0.0),
        taxes=float(tx.taxes or 0.0),
        total_amount=float(tx.total_amount),
        notes=tx.notes
    )

@router.get("/stocks", response_model=MCPStockReadResponse)
async def read_mcp_stocks(
    account: Optional[str] = Query(None, description="Account name or ID to filter by"),
    asset: Optional[str] = Query(None, description="Stock symbol (e.g. AAPL) or asset ID to filter by"),
    transaction_type: Optional[str] = Query(None, description="Filter by transaction type: buy, sell, dividend, bonus, split, deposit, withdrawal"),
    month: Optional[str] = Query(None, description="Month in YYYY-MM format, e.g. 2026-09"),
    limit: int = Query(50, ge=1, le=200, description="Max number of statements to return (default 50)"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Fetch existing stocks, valid investment accounts, and recent transactions.
    AI MUST call this endpoint first before executing any buy/sell/dividend trade to look up
    valid account names, check if the asset already exists, and obtain asset_id or symbol.
    """
    # 1. Fetch available accounts
    acc_stmt = select(Account).order_by(Account.account_name)
    all_accounts = (await db.execute(acc_stmt)).scalars().all()
    avail_accounts = [
        MCPAvailableAccount(
            account_id=a.account_id,
            account_name=a.account_name,
            currency=a.currency or "USD",
            account_type=a.account_type
        )
        for a in all_accounts
    ]

    # 2. Fetch available assets
    asset_stmt = select(Asset).order_by(Asset.symbol)
    all_assets = (await db.execute(asset_stmt)).scalars().all()
    avail_assets = [
        MCPStockAssetItem(
            asset_id=ast.asset_id,
            symbol=ast.symbol,
            name=ast.name,
            asset_type=ast.asset_type,
            currency=ast.currency or "USD",
            exchange=ast.exchange
        )
        for ast in all_assets
    ]

    # 3. Query transactions
    FundingAccount = aliased(Account)
    stmt = (
        select(
            Transaction,
            Account.account_name,
            Account.currency,
            Asset.symbol,
            Asset.name,
            FundingAccount.account_name
        )
        .outerjoin(Account, Transaction.account_id == Account.account_id)
        .outerjoin(FundingAccount, Transaction.funding_account_id == FundingAccount.account_id)
        .outerjoin(Asset, Transaction.asset_id == Asset.asset_id)
        .order_by(desc(Transaction.transaction_date), desc(Transaction.transaction_id))
    )

    if month:
        try:
            parts = month.strip().split("-")
            year, m_num = int(parts[0]), int(parts[1])
            start_d = datetime.date(year, m_num, 1)
            _, last_day = calendar.monthrange(year, m_num)
            end_d = datetime.date(year, m_num, last_day)
            stmt = stmt.where(Transaction.transaction_date >= start_d, Transaction.transaction_date <= end_d)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid month format. Expected YYYY-MM, e.g. 2026-09")

    if transaction_type:
        stmt = stmt.where(Transaction.transaction_type == transaction_type.strip().lower())

    res = await db.execute(stmt)
    rows = res.all()

    # Filter by account and asset
    filtered = []
    for tx, acc_name, acc_curr, symbol, asset_name, f_acc_name in rows:
        if account:
            ac_str = account.strip().lower()
            if str(tx.account_id) != ac_str and (acc_name or "").lower() != ac_str:
                continue
        if asset:
            as_str = asset.strip().lower()
            if str(tx.asset_id) != as_str and (symbol or "").lower() != as_str:
                continue
        filtered.append((tx, acc_name, acc_curr, symbol, asset_name, f_acc_name))

    total_count = len(filtered)
    paged = filtered[:limit]
    tx_responses = [
        _build_stock_response(tx, acc_name or f"Account #{tx.account_id}", acc_curr or "USD", symbol, asset_name, f_acc_name)
        for tx, acc_name, acc_curr, symbol, asset_name, f_acc_name in paged
    ]

    return MCPStockReadResponse(
        available_assets=avail_assets,
        available_accounts=avail_accounts,
        transactions=tx_responses,
        total_count=total_count
    )

@router.post("/stocks", response_model=MCPStockMutateResponse)
async def mutate_mcp_stocks(
    payload: MCPStockMutateRequest = Body(
        ...,
        description="Batch or single stock mutate request containing operations to create, update, or delete stock transactions."
    ),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Mutate stock transactions (create, update, delete).
    AI MUST call GET /api/v1/mcp/stocks first for valid accounts and assets.
    If an asset is missing, set force_create_asset=true. Creating accounts is strictly forbidden.
    """
    operations = payload.operations
    if not operations:
        raise HTTPException(status_code=400, detail="No operations provided.")

    # Cache accounts
    acc_res = await db.execute(select(Account))
    all_accounts = acc_res.scalars().all()
    acc_by_id = {a.account_id: a for a in all_accounts}
    acc_by_name = {a.account_name.strip().lower(): a for a in all_accounts}
    acc_summary = [
        {"account_id": a.account_id, "account_name": a.account_name, "account_type": a.account_type, "currency": a.currency}
        for a in all_accounts
    ]

    # Cache assets
    asset_res = await db.execute(select(Asset))
    all_assets = list(asset_res.scalars().all())
    asset_by_id = {a.asset_id: a for a in all_assets}
    asset_by_symbol = {a.symbol.strip().upper(): a for a in all_assets if a.symbol}
    asset_by_isin = {a.isin.strip().upper(): a for a in all_assets if a.isin}
    asset_by_name = {a.name.strip().lower(): a for a in all_assets if a.name}

    results: List[MCPStockTransactionResponse] = []
    earliest_date = datetime.date.today()

    for op in operations:
        action = (op.action or "create").strip().lower()

        if action == "delete":
            if not op.transaction_id:
                raise HTTPException(status_code=400, detail="transaction_id is required for delete action.")
            del_stmt = select(Transaction).where(Transaction.transaction_id == op.transaction_id)
            del_res = await db.execute(del_stmt)
            tx_to_del = del_res.scalar_one_or_none()
            if not tx_to_del:
                raise HTTPException(status_code=404, detail=f"Transaction with ID {op.transaction_id} not found.")
            target_asset_id = tx_to_del.asset_id
            t_date = tx_to_del.transaction_date
            if t_date < earliest_date:
                earliest_date = t_date
            await db.delete(tx_to_del)
            await db.commit()
            if target_asset_id:
                await cleanup_orphan_transaction_prices(db, target_asset_id)
                await db.commit()
            continue

        tx_to_up = None
        if action == "update":
            if not op.transaction_id:
                raise HTTPException(status_code=400, detail="transaction_id is required for update action.")
            up_stmt = select(Transaction).where(Transaction.transaction_id == op.transaction_id)
            up_res = await db.execute(up_stmt)
            tx_to_up = up_res.scalar_one_or_none()
            if not tx_to_up:
                raise HTTPException(status_code=404, detail=f"Transaction with ID {op.transaction_id} not found.")

        # 1. Resolve Account (Strict matching, NO force creation)
        acc = None
        if op.account_id:
            acc = acc_by_id.get(op.account_id)
        elif op.account_name:
            acc = acc_by_name.get(op.account_name.strip().lower())
        elif action == "update" and tx_to_up:
            acc = acc_by_id.get(tx_to_up.account_id)

        if not acc:
            acc_ident = op.account_name or op.account_id or "unspecified"
            raise HTTPException(
                status_code=400,
                detail=f"Account '{acc_ident}' not found. Available accounts: {acc_summary}. Creating new accounts via AI is not permitted."
            )

        # 2. Resolve Funding Account if provided
        f_acc = None
        if op.funding_account_id:
            f_acc = acc_by_id.get(op.funding_account_id)
            if not f_acc:
                raise HTTPException(
                    status_code=400,
                    detail=f"Funding account ID '{op.funding_account_id}' not found. Available accounts: {acc_summary}."
                )
        elif op.funding_account_name:
            f_acc = acc_by_name.get(op.funding_account_name.strip().lower())
            if not f_acc:
                raise HTTPException(
                    status_code=400,
                    detail=f"Funding account name '{op.funding_account_name}' not found. Available accounts: {acc_summary}."
                )

        # 3. Resolve Asset
        target_asset = None
        if op.asset_id:
            target_asset = asset_by_id.get(op.asset_id)
        elif op.symbol:
            target_asset = asset_by_symbol.get(op.symbol.strip().upper())
        elif op.isin:
            target_asset = asset_by_isin.get(op.isin.strip().upper())
        elif op.asset_name:
            target_asset = asset_by_name.get(op.asset_name.strip().lower())
        elif action == "update" and tx_to_up:
            target_asset = asset_by_id.get(tx_to_up.asset_id)

        t_type = (op.transaction_type or (tx_to_up.transaction_type if tx_to_up else "buy")).strip().lower()
        requires_asset = t_type in ["buy", "sell", "dividend", "bonus", "split"]

        if requires_asset and not target_asset:
            if op.force_create_asset:
                new_symbol = (op.symbol or op.asset_name or "UNKNOWN").strip().upper()
                new_name = op.asset_name or op.symbol or new_symbol
                new_type = (op.asset_type or "stock").strip().lower()
                new_curr = op.asset_currency or acc.currency or "USD"
                new_exch = op.exchange
                target_asset = Asset(
                    symbol=new_symbol,
                    name=new_name,
                    asset_type=new_type,
                    currency=new_curr,
                    exchange=new_exch,
                    isin=op.isin
                )
                db.add(target_asset)
                await db.flush()
                # Update caches
                all_assets.append(target_asset)
                asset_by_id[target_asset.asset_id] = target_asset
                asset_by_symbol[new_symbol] = target_asset
                if target_asset.name:
                    asset_by_name[target_asset.name.strip().lower()] = target_asset
            else:
                asset_summary = [
                    {"asset_id": a.asset_id, "symbol": a.symbol, "name": a.name, "currency": a.currency, "exchange": a.exchange}
                    for a in all_assets
                ]
                asset_ident = op.symbol or op.asset_name or op.asset_id or "unspecified"
                raise HTTPException(
                    status_code=400,
                    detail=f"Asset '{asset_ident}' not found. Available assets: {asset_summary}. To force-create this asset, set force_create_asset=true (and optionally provide symbol, asset_name, asset_type, currency, exchange)."
                )

        # 4. Resolve dates, fees, taxes, and total_amount
        tx_date = op.date or (tx_to_up.transaction_date if tx_to_up else datetime.date.today())
        if tx_date < earliest_date:
            earliest_date = tx_date

        qty = op.quantity if op.quantity is not None else (tx_to_up.quantity if tx_to_up else None)
        price = op.price_per_unit if op.price_per_unit is not None else (tx_to_up.price_per_unit if tx_to_up else None)
        fees = op.fees if op.fees is not None else (tx_to_up.fees if tx_to_up else 0.0)
        taxes = op.taxes if op.taxes is not None else (tx_to_up.taxes if tx_to_up else 0.0)

        # Calculate or use total_amount
        if op.total_amount is not None:
            tot_amt = round(float(op.total_amount), 2)
        elif qty is not None and price is not None:
            base_val = qty * price
            if t_type == "buy":
                tot_amt = round(base_val + fees + taxes, 2)
            elif t_type == "sell":
                tot_amt = round(base_val - fees - taxes, 2)
            else:
                tot_amt = round(base_val, 2)
        elif tx_to_up:
            tot_amt = tx_to_up.total_amount
        else:
            tot_amt = round(fees + taxes, 2)

        notes_val = op.notes if op.notes is not None else (tx_to_up.notes if tx_to_up else None)

        if action == "create":
            new_tx = Transaction(
                account_id=acc.account_id,
                funding_account_id=f_acc.account_id if f_acc else None,
                asset_id=target_asset.asset_id if target_asset else None,
                transaction_type=t_type,
                transaction_date=tx_date,
                quantity=qty,
                price_per_unit=price,
                fees=fees,
                taxes=taxes,
                total_amount=tot_amt,
                notes=notes_val,
                source="mcp_ai"
            )
            db.add(new_tx)
            await db.flush()
            await _ensure_price_history_for_tx(db, new_tx)
            results.append(_build_stock_response(
                new_tx,
                acc.account_name,
                acc.currency or "USD",
                target_asset.symbol if target_asset else None,
                target_asset.name if target_asset else None,
                f_acc.account_name if f_acc else None
            ))
        elif action == "update" and tx_to_up:
            tx_to_up.account_id = acc.account_id
            tx_to_up.funding_account_id = f_acc.account_id if f_acc else None
            tx_to_up.asset_id = target_asset.asset_id if target_asset else None
            tx_to_up.transaction_type = t_type
            tx_to_up.transaction_date = tx_date
            tx_to_up.quantity = qty
            tx_to_up.price_per_unit = price
            tx_to_up.fees = fees
            tx_to_up.taxes = taxes
            tx_to_up.total_amount = tot_amt
            tx_to_up.notes = notes_val
            await db.flush()
            await _ensure_price_history_for_tx(db, tx_to_up)
            results.append(_build_stock_response(
                tx_to_up,
                acc.account_name,
                acc.currency or "USD",
                target_asset.symbol if target_asset else None,
                target_asset.name if target_asset else None,
                f_acc.account_name if f_acc else None
            ))

    await db.commit()

    # Recalculate derived state
    await recalculate_all_lots(db)
    await recalculate_past_snapshots(db, start_date=earliest_date)

    return MCPStockMutateResponse(
        results=results,
        message=f"Successfully processed {len(operations)} stock operation(s)."
    )

