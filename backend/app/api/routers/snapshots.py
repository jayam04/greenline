from typing import List, Optional, Dict
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, asc
from sqlalchemy.orm import selectinload
import datetime
from app.db.database import get_db
from app.db.models import NetworthSnapshot, Account, User
from app.schemas.schemas import NetworthSnapshotResponse
from app.services.snapshot_engine import calculate_account_snapshots
from app.api.deps import get_current_user

router = APIRouter(prefix="/snapshots", tags=["snapshots"])

FX_RATES_TO_EUR = {
    "EUR": 1.0,
    "USD": 0.92,
    "INR": 0.0102,
    "GBP": 1.17,
    "CAD": 0.67,
    "AUD": 0.60,
    "JPY": 0.0059,
    "CHF": 1.06,
    "SGD": 0.68,
}

def to_eur(amount: float, curr: str) -> float:
    rate = FX_RATES_TO_EUR.get((curr or "EUR").upper(), 1.0)
    return amount * rate

@router.get("", response_model=List[NetworthSnapshotResponse])
@router.get("/", response_model=List[NetworthSnapshotResponse])
async def list_snapshots(
    account_id: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # 1. If specific account requested, calculate its native timeline
    if account_id is not None:
        acc_snaps = await calculate_account_snapshots(db, account_id=account_id)
        return [NetworthSnapshotResponse(**s) for s in acc_snaps]

    # 2. In Aggregated mode, fetch all accounts and aggregate them converted to EUR
    acc_stmt = select(Account)
    acc_res = await db.execute(acc_stmt)
    all_accounts = acc_res.scalars().all()

    if not all_accounts:
        stmt = (
            select(NetworthSnapshot)
            .options(selectinload(NetworthSnapshot.asset_class_breakdowns))
            .order_by(asc(NetworthSnapshot.snapshot_date))
        )
        res = await db.execute(stmt)
        return res.scalars().all()

    # Calculate timeline for each account
    account_timelines: Dict[int, Dict[datetime.date, Dict]] = {}
    all_dates_set = set()

    for acc in all_accounts:
        snaps = await calculate_account_snapshots(db, account_id=acc.account_id)
        account_timelines[acc.account_id] = {}
        for s in snaps:
            d = s["snapshot_date"]
            all_dates_set.add(d)
            account_timelines[acc.account_id][d] = s

    if not all_dates_set:
        stmt = (
            select(NetworthSnapshot)
            .options(selectinload(NetworthSnapshot.asset_class_breakdowns))
            .order_by(asc(NetworthSnapshot.snapshot_date))
        )
        res = await db.execute(stmt)
        return res.scalars().all()

    sorted_dates = sorted(list(all_dates_set))
    aggregated_snaps = []

    # Forward-fill accounts across dates so aggregated curve is smooth and complete
    last_known_acc_state: Dict[int, Dict] = {}

    for d in sorted_dates:
        tot_invested_eur = 0.0
        tot_val_eur = 0.0
        tot_cash_eur = 0.0
        tot_rpnl_eur = 0.0
        tot_upnl_eur = 0.0
        tot_nw_eur = 0.0

        for acc in all_accounts:
            curr = acc.currency or "EUR"
            if d in account_timelines[acc.account_id]:
                last_known_acc_state[acc.account_id] = account_timelines[acc.account_id][d]

            state = last_known_acc_state.get(acc.account_id)
            if state:
                tot_invested_eur += to_eur(state["total_invested"], curr)
                tot_val_eur += to_eur(state["total_current_value"], curr)
                tot_cash_eur += to_eur(state["cash_balance"], curr)
                tot_rpnl_eur += to_eur(state["total_realized_pnl"], curr)
                tot_upnl_eur += to_eur(state["total_unrealized_pnl"], curr)
                tot_nw_eur += to_eur(state["net_worth"], curr)

        aggregated_snaps.append(NetworthSnapshotResponse(
            snapshot_id=0,
            snapshot_date=d,
            total_invested=tot_invested_eur,
            total_current_value=tot_val_eur,
            cash_balance=tot_cash_eur,
            total_realized_pnl=tot_rpnl_eur,
            total_unrealized_pnl=tot_upnl_eur,
            net_worth=tot_nw_eur,
            asset_class_breakdowns=[]
        ))

    return aggregated_snaps
