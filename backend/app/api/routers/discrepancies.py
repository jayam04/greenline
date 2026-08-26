from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from sqlalchemy.orm import aliased
from app.db.database import get_db
from app.db.models import Transaction, Account, Asset, User
from app.schemas.schemas import (
    DiscrepancySummaryResponse,
    DiscrepancyItemResponse,
    DiscrepancyResolveRequest,
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
    Applies bank account assignments and optional tax/notes adjustments to unlinked dividends.
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
                if item.taxes is not None:
                    target_tx.taxes = float(item.taxes)
                if item.notes is not None:
                    target_tx.notes = item.notes

        await db.commit()
        await recalculate_all_lots(db)

    return {"status": "success", "resolved_count": len(payload.resolutions)}

@router.post("/auto-link-defaults", status_code=status.HTTP_200_OK)
async def auto_link_default_discrepancies(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Automatically links all unlinked dividend transactions whose parent Demat account has a default dividend bank account configured.
    """
    stmt = (
        select(Transaction, Account.default_dividend_account_id)
        .join(Account, Transaction.account_id == Account.account_id)
        .where(
            Transaction.transaction_type == "dividend",
            Transaction.funding_account_id.is_(None),
            Account.default_dividend_account_id.is_not(None)
        )
    )
    res = await db.execute(stmt)
    rows = res.all()

    count = 0
    for tx, def_bank_id in rows:
        tx.funding_account_id = def_bank_id
        count += 1

    if count > 0:
        await db.commit()
        await recalculate_all_lots(db)

    return {"status": "success", "linked_count": count}

@router.post("/sync-dividends", status_code=status.HTTP_200_OK)
async def trigger_dividend_sync(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Triggers Yahoo Finance dividend harvest for all stock/etf assets."""
    changes = await sync_all_dividends(db)
    return {"status": "success", "changes": changes}
