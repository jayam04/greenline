import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from sqlalchemy.orm import selectinload

from app.db.database import get_db
from app.db.models import CashflowTransaction, CashflowPayment, CashflowItem, Account, Category, User
from app.schemas.schemas import (
    CashflowTransactionCreate, CashflowTransactionUpdate, CashflowTransactionResponse,
    CashflowPaymentResponse, CashflowItemResponse, CashflowSummaryResponse, SankeyDataResponse
)
from app.services.cashflow_engine import (
    generate_sankey_data, get_cashflow_summary, build_category_lineage_map, convert_currency_to_eur,
    convert_currency, resolve_transaction_kind
)
from app.api.deps import get_current_user

router = APIRouter(prefix="/cashflow", tags=["cashflow"])

@router.get("", response_model=List[CashflowTransactionResponse])
@router.get("/", response_model=List[CashflowTransactionResponse])
async def list_cashflow_transactions(
    start_date: Optional[datetime.date] = Query(None),
    end_date: Optional[datetime.date] = Query(None),
    account_id: Optional[int] = Query(None),
    category_id: Optional[int] = Query(None),
    label: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    stmt = (
        select(CashflowTransaction)
        .options(
            selectinload(CashflowTransaction.payments).selectinload(CashflowPayment.account),
            selectinload(CashflowTransaction.items).selectinload(CashflowItem.category)
        )
        .order_by(desc(CashflowTransaction.transaction_date), desc(CashflowTransaction.cashflow_id))
    )

    if start_date:
        stmt = stmt.where(CashflowTransaction.transaction_date >= start_date)
    if end_date:
        stmt = stmt.where(CashflowTransaction.transaction_date <= end_date)

    res = await db.execute(stmt)
    transactions = res.scalars().all()

    lineage_map = await build_category_lineage_map(db)
    results = []

    for tx in transactions:
        # Filter by account_id if specified
        if account_id and not any(p.account_id == account_id for p in tx.payments):
            continue

        # Filter by category_id if specified
        if category_id and not any(i.category_id == category_id for i in tx.items):
            continue

        payments_out = [
            CashflowPaymentResponse(
                payment_id=p.payment_id,
                cashflow_id=p.cashflow_id,
                account_id=p.account_id,
                account_name=p.account.account_name if p.account else f"Account #{p.account_id}",
                account_currency=p.account.currency if p.account and p.account.currency else "EUR",
                amount=p.amount
            )
            for p in tx.payments
        ]

        items_out = []
        for i in tx.items:
            cat_meta = lineage_map.get(i.category_id)
            eff_label = i.label or (cat_meta["effective_label"] if cat_meta else None)
            
            # Filter by label if specified
            if label and eff_label != label.upper():
                continue

            items_out.append(CashflowItemResponse(
                item_id=i.item_id,
                cashflow_id=i.cashflow_id,
                category_id=i.category_id,
                category_name=i.category.name if i.category else f"Category #{i.category_id}",
                category_type=i.category.category_type if i.category else "EXPENSE",
                amount=i.amount,
                label=i.label,
                effective_label=eff_label,
                description=i.description
            ))

        if label and not items_out:
            continue

        tx_kind = resolve_transaction_kind(tx)

        results.append(CashflowTransactionResponse(
            cashflow_id=tx.cashflow_id,
            transaction_date=tx.transaction_date,
            title=tx.title,
            total_amount=tx.total_amount,
            currency=tx.currency or "EUR",
            master_amount_eur=convert_currency_to_eur(tx.total_amount, tx.currency or "EUR"),
            transaction_kind=tx_kind,
            notes=tx.notes,
            created_at=tx.created_at,
            payments=payments_out,
            items=items_out
        ))

    return results

@router.get("/summary", response_model=CashflowSummaryResponse)
async def get_summary(
    start_date: Optional[datetime.date] = Query(None),
    end_date: Optional[datetime.date] = Query(None),
    include_investments: bool = Query(True),
    master_currency: Optional[str] = Query("EUR"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return await get_cashflow_summary(
        db,
        start_date=start_date,
        end_date=end_date,
        include_investments=include_investments,
        master_currency=master_currency or "EUR"
    )

@router.get("/sankey", response_model=SankeyDataResponse)
async def get_sankey(
    depth: int = Query(2, ge=1, le=5),
    include_investments: bool = Query(True),
    master_currency: Optional[str] = Query("EUR"),
    start_date: Optional[datetime.date] = Query(None),
    end_date: Optional[datetime.date] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return await generate_sankey_data(
        db=db,
        start_date=start_date,
        end_date=end_date,
        depth=depth,
        include_investments=include_investments,
        master_currency=master_currency or "EUR"
    )

@router.get("/{cashflow_id}", response_model=CashflowTransactionResponse)
async def get_cashflow_transaction(
    cashflow_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    stmt = (
        select(CashflowTransaction)
        .options(
            selectinload(CashflowTransaction.payments).selectinload(CashflowPayment.account),
            selectinload(CashflowTransaction.items).selectinload(CashflowItem.category)
        )
        .execution_options(populate_existing=True)
        .where(CashflowTransaction.cashflow_id == cashflow_id)
    )
    res = await db.execute(stmt)
    tx = res.scalar_one_or_none()
    if not tx:
        raise HTTPException(status_code=404, detail="Transaction not found")

    lineage_map = await build_category_lineage_map(db)

    payments_out = [
        CashflowPaymentResponse(
            payment_id=p.payment_id,
            cashflow_id=p.cashflow_id,
            account_id=p.account_id,
            account_name=p.account.account_name if p.account else f"Account #{p.account_id}",
            account_currency=p.account.currency if p.account and p.account.currency else "EUR",
            amount=p.amount
        )
        for p in tx.payments
    ]

    items_out = [
        CashflowItemResponse(
            item_id=i.item_id,
            cashflow_id=i.cashflow_id,
            category_id=i.category_id,
            category_name=i.category.name if i.category else f"Category #{i.category_id}",
            category_type=i.category.category_type if i.category else "EXPENSE",
            amount=i.amount,
            label=i.label,
            effective_label=i.label or (lineage_map[i.category_id]["effective_label"] if i.category_id in lineage_map else None),
            description=i.description
        )
        for i in tx.items
    ]

    tx_kind = resolve_transaction_kind(tx)

    return CashflowTransactionResponse(
        cashflow_id=tx.cashflow_id,
        transaction_date=tx.transaction_date,
        title=tx.title,
        total_amount=tx.total_amount,
        currency=tx.currency or "EUR",
        master_amount_eur=convert_currency_to_eur(tx.total_amount, tx.currency or "EUR"),
        transaction_kind=tx_kind,
        notes=tx.notes,
        created_at=tx.created_at,
        payments=payments_out,
        items=items_out
    )

@router.post("", response_model=CashflowTransactionResponse, status_code=status.HTTP_201_CREATED)
@router.post("/", response_model=CashflowTransactionResponse, status_code=status.HTTP_201_CREATED)
async def create_cashflow_transaction(
    tx_in: CashflowTransactionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if not tx_in.payments:
        raise HTTPException(status_code=400, detail="At least one funding payment method is required")
    if not tx_in.items:
        raise HTTPException(status_code=400, detail="At least one category line item is required")

    # 1. Fetch accounts to verify currencies
    acc_ids = [p.account_id for p in tx_in.payments]
    acc_stmt = select(Account).where(Account.account_id.in_(acc_ids))
    acc_res = await db.execute(acc_stmt)
    accounts = {a.account_id: a for a in acc_res.scalars().all()}

    # 2. Fetch categories to verify categorical intent
    cat_ids = [i.category_id for i in tx_in.items]
    cat_stmt = select(Category).where(Category.category_id.in_(cat_ids))
    cat_res = await db.execute(cat_stmt)
    categories_map = {c.category_id: c for c in cat_res.scalars().all()}

    # 3. Determine primary currency
    currencies = set(accounts[p.account_id].currency or "EUR" for p in tx_in.payments if p.account_id in accounts)
    if len(currencies) > 1:
        primary_currency = "EUR"
    elif tx_in.currency:
        primary_currency = tx_in.currency
    elif currencies:
        primary_currency = list(currencies)[0]
    else:
        primary_currency = "EUR"

    has_transfer_cat = any(categories_map.get(i.category_id) and categories_map[i.category_id].category_type == "TRANSFER" for i in tx_in.items)
    has_income_cat = any(categories_map.get(i.category_id) and categories_map[i.category_id].category_type == "INCOME" for i in tx_in.items)
    has_expense_cat = any(categories_map.get(i.category_id) and categories_map[i.category_id].category_type in ["EXPENSE", "SPEND"] for i in tx_in.items)

    has_outflow = any(p.amount < 0 for p in tx_in.payments)
    has_inflow = any(p.amount > 0 for p in tx_in.payments)
    is_multi_payment = len(tx_in.payments) > 1

    net_payments_tx_curr = sum(
        convert_currency(p.amount, accounts[p.account_id].currency if p.account_id in accounts else primary_currency, primary_currency)
        for p in tx_in.payments
    )
    total_items_tx_curr = sum(
        i.amount for i in tx_in.items
    )

    is_transfer = (
        tx_in.transaction_kind == "TRANSFER" or
        has_transfer_cat or
        (tx_in.transaction_kind is None and not has_expense_cat and not has_income_cat and is_multi_payment and has_outflow and has_inflow and abs(net_payments_tx_curr) < 0.05)
    )

    # 4. Multi-Currency Server-Side Balancing Validation
    if is_transfer:
        outflow_eur = sum(
            convert_currency_to_eur(abs(p.amount), accounts[p.account_id].currency if p.account_id in accounts else "EUR")
            for p in tx_in.payments if p.amount < 0
        )
        inflow_eur = sum(
            convert_currency_to_eur(abs(p.amount), accounts[p.account_id].currency if p.account_id in accounts else "EUR")
            for p in tx_in.payments if p.amount > 0
        )
        if outflow_eur > 0 and inflow_eur > 0:
            diff_pct = abs(outflow_eur - inflow_eur) / max(outflow_eur, inflow_eur)
            if diff_pct > 0.05:
                raise HTTPException(
                    status_code=400,
                    detail=f"Transfer outflow ({outflow_eur:.2f} EUR) and inflow ({inflow_eur:.2f} EUR) differ by more than 5% FX tolerance."
                )
        dest_pmt = next((p for p in tx_in.payments if p.amount > 0), None)
        final_total = dest_pmt.amount if dest_pmt else max(abs(p.amount) for p in tx_in.payments)
        resolved_kind = "TRANSFER"
    else:
        diff = abs(abs(net_payments_tx_curr) - total_items_tx_curr)
        if diff > 0.05:
            raise HTTPException(
                status_code=400,
                detail=f"Net account payments ({abs(net_payments_tx_curr):.2f} {primary_currency}) do not match category allocations ({total_items_tx_curr:.2f} {primary_currency})."
            )

        final_total = max(abs(net_payments_tx_curr), total_items_tx_curr)
        if tx_in.transaction_kind == "INCOME" or has_income_cat:
            resolved_kind = "INCOME"
        elif tx_in.transaction_kind == "EXPENSE" or has_expense_cat:
            resolved_kind = "EXPENSE"
        elif net_payments_tx_curr > 0.001:
            resolved_kind = "INCOME"
        else:
            resolved_kind = "EXPENSE"

    # Create parent transaction
    tx = CashflowTransaction(
        transaction_date=tx_in.transaction_date,
        title=tx_in.title,
        total_amount=round(abs(final_total), 2),
        currency=primary_currency,
        transaction_kind=resolved_kind,
        notes=tx_in.notes
    )
    db.add(tx)
    await db.flush()
    await db.refresh(tx)

    # Create payments
    for p in tx_in.payments:
        pmt = CashflowPayment(
            cashflow_id=tx.cashflow_id,
            account_id=p.account_id,
            amount=p.amount
        )
        db.add(pmt)

    # Create items
    for i in tx_in.items:
        itm = CashflowItem(
            cashflow_id=tx.cashflow_id,
            category_id=i.category_id,
            amount=i.amount,
            label=i.label.upper() if i.label else None,
            description=i.description
        )
        db.add(itm)

    await db.commit()
    return await get_cashflow_transaction(tx.cashflow_id, db=db, current_user=current_user)

@router.put("/{cashflow_id}", response_model=CashflowTransactionResponse)
async def update_cashflow_transaction(
    cashflow_id: int,
    tx_in: CashflowTransactionUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    stmt = select(CashflowTransaction).where(CashflowTransaction.cashflow_id == cashflow_id)
    res = await db.execute(stmt)
    tx = res.scalar_one_or_none()
    if not tx:
        raise HTTPException(status_code=404, detail="Transaction not found")

    update_data = tx_in.model_dump(exclude_unset=True)

    if "transaction_date" in update_data and update_data["transaction_date"]:
        tx.transaction_date = update_data["transaction_date"]
    if "title" in update_data and update_data["title"]:
        tx.title = update_data["title"]
    if "currency" in update_data and update_data["currency"]:
        tx.currency = update_data["currency"]
    if "transaction_kind" in update_data and update_data["transaction_kind"]:
        tx.transaction_kind = update_data["transaction_kind"]
    if "notes" in update_data:
        tx.notes = update_data["notes"]
    if "total_amount" in update_data and update_data["total_amount"] is not None:
        tx.total_amount = update_data["total_amount"]

    # If payments or items provided, replace and validate
    if tx_in.payments is not None and tx_in.items is not None:
        acc_ids = [p.account_id for p in tx_in.payments]
        acc_stmt = select(Account).where(Account.account_id.in_(acc_ids))
        acc_res = await db.execute(acc_stmt)
        accounts = {a.account_id: a for a in acc_res.scalars().all()}

        cat_ids = [i.category_id for i in tx_in.items]
        cat_stmt = select(Category).where(Category.category_id.in_(cat_ids))
        cat_res = await db.execute(cat_stmt)
        categories_map = {c.category_id: c for c in cat_res.scalars().all()}

        currencies = set(accounts[p.account_id].currency or "EUR" for p in tx_in.payments if p.account_id in accounts)
        if len(currencies) > 1:
            primary_currency = "EUR"
        elif tx_in.currency:
            primary_currency = tx_in.currency
        elif currencies:
            primary_currency = list(currencies)[0]
        else:
            primary_currency = tx.currency or "EUR"
        has_transfer_cat = any(categories_map.get(i.category_id) and categories_map[i.category_id].category_type == "TRANSFER" for i in tx_in.items)
        has_income_cat = any(categories_map.get(i.category_id) and categories_map[i.category_id].category_type == "INCOME" for i in tx_in.items)
        has_expense_cat = any(categories_map.get(i.category_id) and categories_map[i.category_id].category_type in ["EXPENSE", "SPEND"] for i in tx_in.items)

        has_outflow = any(p.amount < 0 for p in tx_in.payments)
        has_inflow = any(p.amount > 0 for p in tx_in.payments)
        is_multi_payment = len(tx_in.payments) > 1

        net_payments_tx_curr = sum(
            convert_currency(p.amount, accounts[p.account_id].currency if p.account_id in accounts else primary_currency, primary_currency)
            for p in tx_in.payments
        )
        total_items_tx_curr = sum(
            i.amount for i in tx_in.items
        )

        is_transfer = (
            tx_in.transaction_kind == "TRANSFER" or
            has_transfer_cat or
            (tx_in.transaction_kind is None and not has_expense_cat and not has_income_cat and is_multi_payment and has_outflow and has_inflow and abs(net_payments_tx_curr) < 0.05)
        )

        if is_transfer:
            outflow_eur = sum(
                convert_currency_to_eur(abs(p.amount), accounts[p.account_id].currency if p.account_id in accounts else "EUR")
                for p in tx_in.payments if p.amount < 0
            )
            inflow_eur = sum(
                convert_currency_to_eur(abs(p.amount), accounts[p.account_id].currency if p.account_id in accounts else "EUR")
                for p in tx_in.payments if p.amount > 0
            )
            if outflow_eur > 0 and inflow_eur > 0:
                diff_pct = abs(outflow_eur - inflow_eur) / max(outflow_eur, inflow_eur)
                if diff_pct > 0.05:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Transfer outflow ({outflow_eur:.2f} EUR) and inflow ({inflow_eur:.2f} EUR) differ by more than 5% FX tolerance."
                    )
            dest_pmt = next((p for p in tx_in.payments if p.amount > 0), None)
            final_total = dest_pmt.amount if dest_pmt else max(abs(p.amount) for p in tx_in.payments)
            resolved_kind = "TRANSFER"
        else:
            diff = abs(abs(net_payments_tx_curr) - total_items_tx_curr)
            if diff > 0.05:
                raise HTTPException(
                    status_code=400,
                    detail=f"Net account payments ({abs(net_payments_tx_curr):.2f} {primary_currency}) do not match category allocations ({total_items_tx_curr:.2f} {primary_currency})."
                )

            final_total = max(abs(net_payments_tx_curr), total_items_tx_curr)
            if tx_in.transaction_kind == "INCOME" or has_income_cat:
                resolved_kind = "INCOME"
            elif tx_in.transaction_kind == "EXPENSE" or has_expense_cat:
                resolved_kind = "EXPENSE"
            elif net_payments_tx_curr > 0.001:
                resolved_kind = "INCOME"
            else:
                resolved_kind = "EXPENSE"

        tx.total_amount = round(final_total, 2)
        tx.currency = primary_currency
        tx.transaction_kind = resolved_kind

        # Delete old payments
        del_p_stmt = select(CashflowPayment).where(CashflowPayment.cashflow_id == cashflow_id)
        p_res = await db.execute(del_p_stmt)
        for old_p in p_res.scalars().all():
            await db.delete(old_p)
        # Insert new payments
        for p in tx_in.payments:
            db.add(CashflowPayment(cashflow_id=tx.cashflow_id, account_id=p.account_id, amount=p.amount))

        # Delete old items
        del_i_stmt = select(CashflowItem).where(CashflowItem.cashflow_id == cashflow_id)
        i_res = await db.execute(del_i_stmt)
        for old_i in i_res.scalars().all():
            await db.delete(old_i)
        # Insert new items
        for i in tx_in.items:
            db.add(CashflowItem(
                cashflow_id=tx.cashflow_id,
                category_id=i.category_id,
                amount=i.amount,
                label=i.label.upper() if i.label else None,
                description=i.description
            ))

    await db.commit()
    return await get_cashflow_transaction(tx.cashflow_id, db=db, current_user=current_user)

@router.delete("/{cashflow_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_cashflow_transaction(
    cashflow_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    stmt = select(CashflowTransaction).where(CashflowTransaction.cashflow_id == cashflow_id)
    res = await db.execute(stmt)
    tx = res.scalar_one_or_none()
    if not tx:
        raise HTTPException(status_code=404, detail="Transaction not found")

    await db.delete(tx)
    await db.commit()
