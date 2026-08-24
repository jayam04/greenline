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
    generate_sankey_data, get_cashflow_summary, build_category_lineage_map, convert_currency_to_eur
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

        is_trans = any(p.amount < 0 for p in tx.payments) or any(i.category and i.category.category_type == "TRANSFER" for i in tx.items)
        is_inc = not is_trans and any(i.category and i.category.category_type == "INCOME" for i in tx.items)
        tx_kind = "TRANSFER" if is_trans else "INCOME" if is_inc else "EXPENSE"

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

    is_trans = any(p.amount < 0 for p in tx.payments) or any(i.category and i.category.category_type == "TRANSFER" for i in tx.items)
    is_inc = not is_trans and any(i.category and i.category.category_type == "INCOME" for i in tx.items)
    tx_kind = "TRANSFER" if is_trans else "INCOME" if is_inc else "EXPENSE"

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

    # Fetch accounts to verify currencies
    acc_ids = [p.account_id for p in tx_in.payments]
    acc_stmt = select(Account).where(Account.account_id.in_(acc_ids))
    acc_res = await db.execute(acc_stmt)
    accounts = {a.account_id: a for a in acc_res.scalars().all()}

    currencies = set(accounts[p.account_id].currency or "EUR" for p in tx_in.payments if p.account_id in accounts)

    total_payments = sum(p.amount for p in tx_in.payments)
    total_items = sum(i.amount for i in tx_in.items)

    is_transfer = tx_in.transaction_kind == "TRANSFER"

    # Determine primary currency and total amount
    if is_transfer:
        # For transfers, primary currency is the destination (or source) currency
        primary_currency = list(currencies)[0] if currencies else "EUR"
        # Find positive payment (destination) or max absolute payment
        dest_pmt = next((p for p in tx_in.payments if p.amount > 0), None)
        final_total = dest_pmt.amount if dest_pmt else max(abs(p.amount) for p in tx_in.payments)
        if dest_pmt and dest_pmt.account_id in accounts:
            primary_currency = accounts[dest_pmt.account_id].currency or primary_currency
        final_currency = tx_in.currency or primary_currency
    elif len(currencies) == 1:
        primary_currency = list(currencies)[0]
        final_total = tx_in.total_amount if tx_in.total_amount and tx_in.total_amount > 0 else total_payments
        final_currency = tx_in.currency or primary_currency
    else:
        primary_currency = "EUR"
        final_total = sum(
            convert_currency_to_eur(p.amount, accounts[p.account_id].currency if p.account_id in accounts else "EUR")
            for p in tx_in.payments
        )
        final_currency = primary_currency

    # Validate balance if single currency non-transfer
    if not is_transfer and len(currencies) <= 1:
        if abs(total_payments - final_total) > 0.01:
            raise HTTPException(
                status_code=400,
                detail=f"Sum of payment methods ({total_payments:.2f}) does not match total ({final_total:.2f})"
            )
        if abs(total_items - final_total) > 0.01:
            raise HTTPException(
                status_code=400,
                detail=f"Sum of category line items ({total_items:.2f}) does not match total ({final_total:.2f})"
            )

    # Create parent transaction
    tx = CashflowTransaction(
        transaction_date=tx_in.transaction_date,
        title=tx_in.title,
        total_amount=round(final_total, 2),
        currency=final_currency,
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
    if "notes" in update_data:
        tx.notes = update_data["notes"]
    if "total_amount" in update_data and update_data["total_amount"] is not None:
        tx.total_amount = update_data["total_amount"]

    # If payments provided, replace all
    if tx_in.payments is not None:
        acc_ids = [p.account_id for p in tx_in.payments]
        acc_stmt = select(Account).where(Account.account_id.in_(acc_ids))
        acc_res = await db.execute(acc_stmt)
        accounts = {a.account_id: a for a in acc_res.scalars().all()}
        currencies = set(accounts[p.account_id].currency or "EUR" for p in tx_in.payments if p.account_id in accounts)

        is_transfer = (tx_in.transaction_kind == "TRANSFER") or any(p.amount < 0 for p in tx_in.payments)
        if is_transfer:
            dest_pmt = next((p for p in tx_in.payments if p.amount > 0), None)
            final_total = dest_pmt.amount if dest_pmt else max(abs(p.amount) for p in tx_in.payments)
            primary_currency = accounts[dest_pmt.account_id].currency if dest_pmt and dest_pmt.account_id in accounts else "EUR"
            final_currency = tx_in.currency or primary_currency
        elif len(currencies) == 1:
            primary_currency = list(currencies)[0]
            final_total = tx_in.total_amount if tx_in.total_amount and tx_in.total_amount > 0 else sum(p.amount for p in tx_in.payments)
            final_currency = tx_in.currency or primary_currency
        else:
            primary_currency = "EUR"
            final_total = sum(
                convert_currency_to_eur(p.amount, accounts[p.account_id].currency if p.account_id in accounts else "EUR")
                for p in tx_in.payments
            )
            final_currency = primary_currency

        tx.total_amount = round(final_total, 2)
        tx.currency = final_currency

        # Delete old payments
        del_p_stmt = select(CashflowPayment).where(CashflowPayment.cashflow_id == cashflow_id)
        p_res = await db.execute(del_p_stmt)
        for old_p in p_res.scalars().all():
            await db.delete(old_p)
        # Insert new payments
        for p in tx_in.payments:
            db.add(CashflowPayment(cashflow_id=tx.cashflow_id, account_id=p.account_id, amount=p.amount))

    # If items provided, replace all
    if tx_in.items is not None:
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
