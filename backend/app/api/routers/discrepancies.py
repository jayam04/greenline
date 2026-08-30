import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, func
from sqlalchemy.orm import aliased
from app.db.database import get_db
from app.db.models import Transaction, Account, Asset, CashflowTransaction, CashflowPayment, User
from app.schemas.schemas import (
    DiscrepancySummaryResponse,
    DiscrepancyItemResponse,
    DiscrepancyResolveRequest,
    CandidateMatchItem,
)
from app.api.deps import get_current_user
from app.services.fifo_engine import recalculate_all_lots
from app.services.dividend_engine import sync_all_dividends

router = APIRouter(prefix="/discrepancies", tags=["discrepancies"])

SuggestedFundingAccount = aliased(Account)

@router.get("", response_model=DiscrepancySummaryResponse)
@router.get("/", response_model=DiscrepancySummaryResponse)
async def list_discrepancies(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Returns all unresolved discrepancies (unlinked dividend payouts where funding_account_id is NULL).
    Attaches suggested default bank account if configured on the Demat account.
    """
    stmt = (
        select(
            Transaction,
            Account.account_name,
            Account.currency,
            Account.default_dividend_account_id,
            Asset.symbol,
            Asset.name.label("asset_name"),
            SuggestedFundingAccount.account_name.label("suggested_bank_name")
        )
        .join(Account, Transaction.account_id == Account.account_id)
        .outerjoin(SuggestedFundingAccount, Account.default_dividend_account_id == SuggestedFundingAccount.account_id)
        .join(Asset, Transaction.asset_id == Asset.asset_id)
        .where(
            Transaction.transaction_type == "dividend",
            Transaction.funding_account_id.is_(None)
        )
        .order_by(desc(Transaction.transaction_date), desc(Transaction.transaction_id))
    )

    res = await db.execute(stmt)
    rows = res.all()

    # Pre-fetch all bank accounts
    bank_stmt = select(Account.account_id, Account.account_name).where(Account.account_type == "bank")
    bank_res = await db.execute(bank_stmt)
    bank_map = {row[0]: row[1] for row in bank_res.all()}
    bank_ids = set(bank_map.keys())

    unlinked_items: List[DiscrepancyItemResponse] = []
    total_unlinked_amount = 0.0
    auto_linkable_count = 0

    for tx, acc_name, acc_curr, def_acc_id, symbol, asset_name, def_bank_name in rows:
        gross_amt = float(tx.total_amount or 0.0)
        tax_amt = float(tx.taxes or 0.0)
        net_amt = round(gross_amt - tax_amt, 2)
        total_unlinked_amount += net_amt

        if def_acc_id is not None:
            auto_linkable_count += 1

        # Search for candidate bank matches within [tx.transaction_date, tx.transaction_date + 90 days]
        candidate_matches: List[CandidateMatchItem] = []
        if bank_ids and tx.transaction_date:
            start_d = tx.transaction_date
            end_d = tx.transaction_date + datetime.timedelta(days=90)

            # 1. Check Cashflow income payments
            cf_stmt = (
                select(
                    CashflowTransaction.cashflow_id,
                    CashflowTransaction.transaction_date,
                    CashflowTransaction.title,
                    CashflowPayment.account_id,
                    CashflowPayment.amount
                )
                .join(CashflowPayment, CashflowTransaction.cashflow_id == CashflowPayment.cashflow_id)
                .where(
                    CashflowPayment.account_id.in_(bank_ids),
                    CashflowPayment.amount > 0,
                    CashflowTransaction.transaction_date >= start_d,
                    CashflowTransaction.transaction_date <= end_d,
                    func.abs(CashflowPayment.amount - net_amt) < 0.01
                )
                .order_by(CashflowTransaction.transaction_date)
            )
            cf_res = await db.execute(cf_stmt)
            for cf_id, cf_date, cf_title, b_id, b_amt in cf_res.all():
                candidate_matches.append(CandidateMatchItem(
                    match_id=cf_id,
                    match_type="cashflow",
                    account_id=b_id,
                    account_name=bank_map.get(b_id, "Bank Account"),
                    date=cf_date,
                    amount=float(b_amt),
                    title=cf_title or "Cashflow Income"
                ))

            # 2. Check direct bank transactions
            btx_stmt = (
                select(
                    Transaction.transaction_id,
                    Transaction.transaction_date,
                    Transaction.notes,
                    Transaction.account_id,
                    Transaction.total_amount
                )
                .where(
                    Transaction.account_id.in_(bank_ids),
                    Transaction.transaction_id != tx.transaction_id,
                    Transaction.transaction_date >= start_d,
                    Transaction.transaction_date <= end_d,
                    func.abs(Transaction.total_amount - net_amt) < 0.01
                )
                .order_by(Transaction.transaction_date)
            )
            btx_res = await db.execute(btx_stmt)
            for btx_id, btx_date, btx_notes, b_id, b_amt in btx_res.all():
                candidate_matches.append(CandidateMatchItem(
                    match_id=btx_id,
                    match_type="transaction",
                    account_id=b_id,
                    account_name=bank_map.get(b_id, "Bank Account"),
                    date=btx_date,
                    amount=float(b_amt),
                    title=btx_notes or "Bank Transaction"
                ))

        unlinked_items.append(DiscrepancyItemResponse(
            transaction_id=tx.transaction_id,
            account_id=tx.account_id,
            account_name=acc_name or "",
            asset_id=tx.asset_id,
            asset_symbol=symbol or "",
            asset_name=asset_name,
            currency=acc_curr or "USD",
            transaction_date=tx.transaction_date,
            quantity=float(tx.quantity or 0.0),
            price_per_unit=float(tx.price_per_unit or 0.0),
            total_amount=gross_amt,
            taxes=tax_amt,
            net_amount=net_amt,
            source=getattr(tx, "source", "manual") or "manual",
            suggested_funding_account_id=def_acc_id,
            suggested_funding_account_name=def_bank_name,
            candidate_matches=candidate_matches,
            notes=tx.notes
        ))

    return DiscrepancySummaryResponse(
        total_count=len(unlinked_items),
        total_unlinked_amount=round(total_unlinked_amount, 2),
        auto_linkable_count=auto_linkable_count,
        unlinked_items=unlinked_items
    )

@router.post("/resolve", status_code=status.HTTP_200_OK)
async def resolve_discrepancies(
    payload: DiscrepancyResolveRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Applies bank account assignments, custom credit dates, and optional tax/notes adjustments to unlinked dividends.
    Optionally sets the default dividend deposit account for a Demat account.
    """
    if payload.set_default_for_demat:
        demat_id = payload.set_default_for_demat.get("demat_account_id")
        def_bank_id = payload.set_default_for_demat.get("default_dividend_account_id")
        if demat_id:
            acc_res = await db.execute(select(Account).where(Account.account_id == demat_id))
            acc = acc_res.scalar_one_or_none()
            if acc:
                acc.default_dividend_account_id = def_bank_id

    tx_ids = [r.transaction_id for r in payload.resolutions]
    if tx_ids:
        tx_stmt = select(Transaction).where(Transaction.transaction_id.in_(tx_ids))
        tx_res = await db.execute(tx_stmt)
        tx_map = {t.transaction_id: t for t in tx_res.scalars().all()}

        for item in payload.resolutions:
            target_tx = tx_map.get(item.transaction_id)
            if target_tx:
                target_tx.funding_account_id = item.funding_account_id
                if item.transaction_date is not None:
                    target_tx.transaction_date = item.transaction_date
                if item.taxes is not None:
                    target_tx.taxes = float(item.taxes)
                if item.notes is not None:
                    target_tx.notes = item.notes

        await db.commit()
        await recalculate_all_lots(db)

    return {"status": "success", "resolved_count": len(payload.resolutions)}

@router.post("/sync-dividends", status_code=status.HTTP_200_OK)
async def trigger_dividend_sync(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Triggers Yahoo Finance dividend harvest for all stock/etf assets."""
    changes = await sync_all_dividends(db)
    return {"status": "success", "changes": changes}
