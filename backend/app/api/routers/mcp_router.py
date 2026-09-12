import datetime
import calendar
from typing import List, Optional, Any, Union
from fastapi import APIRouter, Depends, HTTPException, status, Query, Body
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from sqlalchemy.orm import selectinload

from app.db.database import get_db
from app.db.models import CashflowTransaction, CashflowPayment, CashflowItem, Account, Category, User
from app.schemas.mcp_schemas import (
    MCPCashflowOperation, MCPCashflowMutateRequest, MCPCashflowMutateResponse,
    MCPCashflowReadResponse, MCPCashflowStatement, MCPCashflowPaymentResponse,
    MCPCashflowItemResponse, MCPCategoriesResponse, MCPCategoryItem, MCPAvailableAccount
)
from app.services.cashflow_engine import build_category_lineage_map
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
