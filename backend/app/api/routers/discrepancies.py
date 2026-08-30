import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, func, or_
from sqlalchemy.orm import aliased
from app.db.database import get_db
from app.db.models import Transaction, Account, Asset, ExpectedDividend, CashflowTransaction, CashflowPayment, User
from app.schemas.schemas import (
    DiscrepancySummaryResponse,
    DiscrepancyItemResponse,
    DiscrepancyResolveRequest,
    DiscrepancyActionRequest,
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
    Returns all unresolved discrepancies from Table B (ExpectedDividend) and any unlinked dividend transactions.
    """
    # 1. Query Expected Dividends from Table B with status UNMATCHED, AMOUNT_MISMATCH, ORPHAN
    stmt = (
        select(
            ExpectedDividend,
            Account.account_name,
            Account.currency,
            Account.default_dividend_account_id,
            Asset.symbol,
            Asset.name.label("asset_name"),
            SuggestedFundingAccount.account_name.label("suggested_bank_name"),
            Transaction.transaction_id.label("linked_tx_id"),
            Transaction.total_amount.label("linked_tx_amount"),
            Transaction.taxes.label("linked_tx_taxes"),
            Transaction.funding_account_id.label("linked_funding_account_id")
        )
        .join(Account, ExpectedDividend.account_id == Account.account_id)
        .outerjoin(SuggestedFundingAccount, Account.default_dividend_account_id == SuggestedFundingAccount.account_id)
        .join(Asset, ExpectedDividend.asset_id == Asset.asset_id)
        .outerjoin(Transaction, ExpectedDividend.matched_transaction_id == Transaction.transaction_id)
        .where(
            ExpectedDividend.status.in_(["UNMATCHED", "AMOUNT_MISMATCH", "ORPHAN"])
        )
        .order_by(desc(ExpectedDividend.ex_date), desc(ExpectedDividend.expected_dividend_id))
    )

    res = await db.execute(stmt)
    rows = res.all()

    # Pre-fetch all bank accounts for candidate matching
    bank_stmt = select(Account.account_id, Account.account_name).where(Account.account_type == "bank")
    bank_res = await db.execute(bank_stmt)
    bank_map = {row[0]: row[1] for row in bank_res.all()}
    bank_ids = set(bank_map.keys())

    unlinked_items: List[DiscrepancyItemResponse] = []
    total_unlinked_amount = 0.0
    auto_linkable_count = 0

    for (
        exp,
        acc_name,
        acc_curr,
        def_acc_id,
        symbol,
        asset_name,
        def_bank_name,
        linked_tx_id,
        linked_tx_amount,
        linked_tx_taxes,
        linked_funding_id
    ) in rows:
        gross_amt = float(exp.expected_amount or 0.0)
        net_amt = round(gross_amt, 2)
        total_unlinked_amount += net_amt

        if def_acc_id is not None:
            auto_linkable_count += 1

        # Search for candidate bank matches within [exp.ex_date, exp.ex_date + 90 days]
        candidate_matches: List[CandidateMatchItem] = []
        if bank_ids and exp.ex_date:
            start_d = exp.ex_date
            end_d = exp.ex_date + datetime.timedelta(days=90)

            # Check Cashflow income payments
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
                    func.abs(CashflowPayment.amount - net_amt) < (net_amt * 0.35 + 0.01) # Match within 35% tax range or exact
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

        unlinked_items.append(DiscrepancyItemResponse(
            expected_dividend_id=exp.expected_dividend_id,
            transaction_id=linked_tx_id,
            account_id=exp.account_id,
            account_name=acc_name or "",
            asset_id=exp.asset_id,
            asset_symbol=symbol or "",
            asset_name=asset_name,
            currency=acc_curr or "USD",
            transaction_date=exp.ex_date,
            quantity=float(exp.eligible_shares or 0.0),
            price_per_unit=float(exp.dividend_rate or 0.0),
            total_amount=gross_amt,
            expected_amount=float(exp.expected_amount or 0.0),
            linked_transaction_amount=float(linked_tx_amount) if linked_tx_amount is not None else None,
            taxes=float(linked_tx_taxes or 0.0),
            net_amount=net_amt,
            source=exp.source or "yfinance",
            status=exp.status or "UNMATCHED",
            suggested_funding_account_id=def_acc_id,
            suggested_funding_account_name=def_bank_name,
            candidate_matches=candidate_matches,
            notes=f"Expected dividend for {symbol} ({exp.eligible_shares} shares @ {exp.dividend_rate}/share)"
        ))

    # 2. Also check any legacy unlinked Transaction rows in Table C (fallback)
    legacy_stmt = (
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
            Transaction.funding_account_id.is_(None),
            Transaction.expected_dividend_id.is_(None)
        )
    )
    legacy_res = await db.execute(legacy_stmt)
    for l_tx, acc_name, acc_curr, def_acc_id, symbol, asset_name, def_bank_name in legacy_res.all():
        gross_amt = float(l_tx.total_amount or 0.0)
        tax_amt = float(l_tx.taxes or 0.0)
        net_amt = round(gross_amt - tax_amt, 2)
        total_unlinked_amount += net_amt

        if def_acc_id is not None:
            auto_linkable_count += 1

        # Search for candidate bank matches for legacy unlinked transaction
        l_matches: List[CandidateMatchItem] = []
        if bank_ids and l_tx.transaction_date:
            start_d = l_tx.transaction_date
            end_d = l_tx.transaction_date + datetime.timedelta(days=90)

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
                l_matches.append(CandidateMatchItem(
                    match_id=cf_id,
                    match_type="cashflow",
                    account_id=b_id,
                    account_name=bank_map.get(b_id, "Bank Account"),
                    date=cf_date,
                    amount=float(b_amt),
                    title=cf_title or "Cashflow Income"
                ))

        unlinked_items.append(DiscrepancyItemResponse(
            expected_dividend_id=None,
            transaction_id=l_tx.transaction_id,
            account_id=l_tx.account_id,
            account_name=acc_name or "",
            asset_id=l_tx.asset_id,
            asset_symbol=symbol or "",
            asset_name=asset_name,
            currency=acc_curr or "USD",
            transaction_date=l_tx.transaction_date,
            quantity=float(l_tx.quantity or 0.0),
            price_per_unit=float(l_tx.price_per_unit or 0.0),
            total_amount=gross_amt,
            expected_amount=gross_amt,
            taxes=tax_amt,
            net_amount=net_amt,
            source=l_tx.source or "manual",
            status="UNMATCHED",
            suggested_funding_account_id=def_acc_id,
            suggested_funding_account_name=def_bank_name,
            candidate_matches=l_matches,
            notes=l_tx.notes
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
    Applies bank account assignments, custom credit dates, and tax adjustments to discrepancies.
    Creates or updates real records in the transactions table (Table C) and links to ExpectedDividend (Table B).
    """
    if payload.set_default_for_demat:
        demat_id = payload.set_default_for_demat.get("demat_account_id")
        def_bank_id = payload.set_default_for_demat.get("default_dividend_account_id")
        if demat_id:
            acc_res = await db.execute(select(Account).where(Account.account_id == demat_id))
            acc = acc_res.scalar_one_or_none()
            if acc:
                acc.default_dividend_account_id = def_bank_id

    for item in payload.resolutions:
        if item.expected_dividend_id:
            exp = await db.get(ExpectedDividend, item.expected_dividend_id)
            if not exp:
                continue

            gross_amt = float(item.total_amount if item.total_amount is not None else exp.expected_amount)
            tax_amt = float(item.taxes if item.taxes is not None else 0.0)
            credit_date = item.transaction_date or exp.ex_date

            if exp.matched_transaction_id:
                # Update existing matched transaction
                mtx = await db.get(Transaction, exp.matched_transaction_id)
                if mtx:
                    mtx.funding_account_id = item.funding_account_id
                    mtx.transaction_date = credit_date
                    mtx.total_amount = gross_amt
                    mtx.taxes = tax_amt
                    if item.notes is not None:
                        mtx.notes = item.notes
                    exp.status = "MATCHED"
            else:
                # Create a new real Transaction in Table C
                new_tx = Transaction(
                    account_id=exp.account_id,
                    funding_account_id=item.funding_account_id,
                    asset_id=exp.asset_id,
                    transaction_type="dividend",
                    transaction_date=credit_date,
                    quantity=exp.eligible_shares,
                    price_per_unit=exp.dividend_rate,
                    total_amount=gross_amt,
                    fees=0.0,
                    taxes=tax_amt,
                    source="manual",
                    expected_dividend_id=exp.expected_dividend_id,
                    notes=item.notes or f"Dividend for AAPL"
                )
                db.add(new_tx)
                await db.flush()

                exp.matched_transaction_id = new_tx.transaction_id
                exp.status = "MATCHED"

        elif item.transaction_id:
            target_tx = await db.get(Transaction, item.transaction_id)
            if target_tx:
                target_tx.funding_account_id = item.funding_account_id
                if item.transaction_date is not None:
                    target_tx.transaction_date = item.transaction_date
                if item.total_amount is not None:
                    target_tx.total_amount = float(item.total_amount)
                if item.taxes is not None:
                    target_tx.taxes = float(item.taxes)
                if item.notes is not None:
                    target_tx.notes = item.notes

    await db.commit()
    await recalculate_all_lots(db)

    return {"status": "success", "resolved_count": len(payload.resolutions)}

@router.post("/dismiss", status_code=status.HTTP_200_OK)
async def dismiss_expected_dividends(
    payload: DiscrepancyActionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Marks expected dividends as DISMISSED so they do not show up in active discrepancies."""
    stmt = select(ExpectedDividend).where(ExpectedDividend.expected_dividend_id.in_(payload.expected_dividend_ids))
    res = await db.execute(stmt)
    for exp in res.scalars().all():
        exp.status = "DISMISSED"
    await db.commit()
    return {"status": "success", "dismissed_count": len(payload.expected_dividend_ids)}

@router.post("/unlink", status_code=status.HTTP_200_OK)
async def unlink_expected_dividends(
    payload: DiscrepancyActionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Unlinks expected dividends from their matched transactions without deleting the actual cash transaction in Table C."""
    stmt = select(ExpectedDividend).where(ExpectedDividend.expected_dividend_id.in_(payload.expected_dividend_ids))
    res = await db.execute(stmt)
    for exp in res.scalars().all():
        if exp.matched_transaction_id:
            tx = await db.get(Transaction, exp.matched_transaction_id)
            if tx:
                tx.expected_dividend_id = None
            exp.matched_transaction_id = None
            exp.status = "UNMATCHED"
    await db.commit()
    return {"status": "success", "unlinked_count": len(payload.expected_dividend_ids)}

@router.post("/sync-dividends", status_code=status.HTTP_200_OK)
async def trigger_dividend_sync(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Triggers Yahoo Finance dividend harvest for all stock/etf assets into Table B."""
    changes = await sync_all_dividends(db)
    return {"status": "success", "changes": changes}
