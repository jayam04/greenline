import datetime
from typing import Optional, Dict, Any
from dataclasses import dataclass
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, func

from app.db.models import StagedRecord, Transaction, CashflowTransaction, CashflowPayment, Account, Asset, Category

@dataclass
class MatchResult:
    status: str  # "new", "exact_match", "probable_match"
    matched_id: Optional[int]
    matched_details: Optional[Dict[str, Any]]
    default_review_status: str  # "approved", "pending", "skipped"

async def match_staged_record(db: AsyncSession, record: StagedRecord) -> MatchResult:
    """
    Evaluates incoming staged record against existing production ledger records.
    Applies Two-Tier Matching:
      - Tier 1 (Exact): Same date, same account, same amount (+/- 0.01), same asset/action.
      - Tier 2 (Probable): Date within +/- 2 days (settlement delay) with same amount, OR same date and amount with slight difference.
      - Tier 3 (New): No matches found.
    """
    if record.record_type == "investment":
        return await _match_investment_record(db, record)
    else:
        return await _match_cashflow_record(db, record)

async def _match_investment_record(db: AsyncSession, record: StagedRecord) -> MatchResult:
    # 1. Search for potential candidate transactions within +/- 2 days
    start_date = record.transaction_date - datetime.timedelta(days=2)
    end_date = record.transaction_date + datetime.timedelta(days=2)

    stmt = (
        select(
            Transaction,
            Account.account_name,
            Asset.symbol,
            Asset.name.label("asset_name")
        )
        .outerjoin(Account, Transaction.account_id == Account.account_id)
        .outerjoin(Asset, Transaction.asset_id == Asset.asset_id)
        .where(
            Transaction.transaction_date >= start_date,
            Transaction.transaction_date <= end_date
        )
    )
    if record.account_id:
        stmt = stmt.where(
            or_(
                Transaction.account_id == record.account_id,
                Transaction.funding_account_id == record.account_id
            )
        )

    res = await db.execute(stmt)
    candidates = res.all()

    exact_candidate = None
    probable_candidate = None

    for tx, acc_name, sym, ast_name in candidates:
        amt_diff = abs(tx.total_amount - record.total_amount)
        same_date = (tx.transaction_date == record.transaction_date)
        same_amount = (amt_diff < 0.01)
        close_amount = (amt_diff <= max(1.0, record.total_amount * 0.02)) # Within 2% or 1 unit (e.g. fees)

        same_asset = False
        if record.asset_id and tx.asset_id:
            same_asset = (record.asset_id == tx.asset_id)
        elif record.asset_symbol_raw and sym:
            same_asset = (record.asset_symbol_raw.upper().strip() == sym.upper().strip())

        # Exact match condition
        if same_date and same_amount and (same_asset or record.action_type in ["deposit", "withdrawal"]):
            exact_candidate = (tx, acc_name, sym, ast_name)
            break

        # Probable match condition (same amount within +/- 2 days, or exact date with slight fee difference)
        if same_amount and same_asset:
            probable_candidate = (tx, acc_name, sym, ast_name, "Date settlement offset (±2 days)")
        elif same_date and close_amount and same_asset:
            probable_candidate = (tx, acc_name, sym, ast_name, f"Fee discrepancy (diff: {round(amt_diff, 2)})")

    if exact_candidate:
        tx, acc_name, sym, ast_name = exact_candidate
        details = {
            "entity_type": "transaction",
            "transaction_id": tx.transaction_id,
            "transaction_date": str(tx.transaction_date),
            "account_name": acc_name,
            "asset_symbol": sym,
            "asset_name": ast_name,
            "transaction_type": tx.transaction_type,
            "quantity": tx.quantity,
            "price_per_unit": tx.price_per_unit,
            "total_amount": tx.total_amount,
            "fees": tx.fees,
            "notes": tx.notes
        }
        return MatchResult(
            status="exact_match",
            matched_id=tx.transaction_id,
            matched_details=details,
            default_review_status="skipped"
        )

    if probable_candidate:
        tx, acc_name, sym, ast_name, reason = probable_candidate
        details = {
            "entity_type": "transaction",
            "transaction_id": tx.transaction_id,
            "transaction_date": str(tx.transaction_date),
            "account_name": acc_name,
            "asset_symbol": sym,
            "asset_name": ast_name,
            "transaction_type": tx.transaction_type,
            "quantity": tx.quantity,
            "price_per_unit": tx.price_per_unit,
            "total_amount": tx.total_amount,
            "fees": tx.fees,
            "notes": tx.notes,
            "match_reason": reason
        }
        return MatchResult(
            status="probable_match",
            matched_id=tx.transaction_id,
            matched_details=details,
            default_review_status="pending"
        )

    return MatchResult(
        status="new",
        matched_id=None,
        matched_details=None,
        default_review_status="approved"
    )

async def _match_cashflow_record(db: AsyncSession, record: StagedRecord) -> MatchResult:
    start_date = record.transaction_date - datetime.timedelta(days=2)
    end_date = record.transaction_date + datetime.timedelta(days=2)

    stmt = (
        select(CashflowTransaction, CashflowPayment.amount, CashflowPayment.account_id, Account.account_name)
        .join(CashflowPayment, CashflowTransaction.cashflow_id == CashflowPayment.cashflow_id)
        .outerjoin(Account, CashflowPayment.account_id == Account.account_id)
        .where(
            CashflowTransaction.transaction_date >= start_date,
            CashflowTransaction.transaction_date <= end_date
        )
    )
    if record.account_id:
        stmt = stmt.where(CashflowPayment.account_id == record.account_id)

    res = await db.execute(stmt)
    candidates = res.all()

    exact_cand = None
    probable_cand = None

    for ct, pmt_amt, acc_id, acc_name in candidates:
        amt_diff = abs(abs(pmt_amt) - abs(record.total_amount))
        same_date = (ct.transaction_date == record.transaction_date)
        same_amount = (amt_diff < 0.01)

        if same_date and same_amount:
            exact_cand = (ct, pmt_amt, acc_name)
            break
        elif same_amount:
            probable_cand = (ct, pmt_amt, acc_name, "Date clearance delay (±2 days)")

    if exact_cand:
        ct, pmt_amt, acc_name = exact_cand
        details = {
            "entity_type": "cashflow",
            "cashflow_id": ct.cashflow_id,
            "transaction_date": str(ct.transaction_date),
            "title": ct.title,
            "account_name": acc_name,
            "amount": pmt_amt,
            "total_amount": ct.total_amount,
            "currency": ct.currency
        }
        return MatchResult(
            status="exact_match",
            matched_id=ct.cashflow_id,
            matched_details=details,
            default_review_status="skipped"
        )

    if probable_cand:
        ct, pmt_amt, acc_name, reason = probable_cand
        details = {
            "entity_type": "cashflow",
            "cashflow_id": ct.cashflow_id,
            "transaction_date": str(ct.transaction_date),
            "title": ct.title,
            "account_name": acc_name,
            "amount": pmt_amt,
            "total_amount": ct.total_amount,
            "currency": ct.currency,
            "match_reason": reason
        }
        return MatchResult(
            status="probable_match",
            matched_id=ct.cashflow_id,
            matched_details=details,
            default_review_status="pending"
        )

    return MatchResult(
        status="new",
        matched_id=None,
        matched_details=None,
        default_review_status="approved"
    )
