import asyncio
import datetime
from typing import List, Tuple, Optional
import yfinance as yf
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, asc
from app.db.models import Asset, Account, Transaction, CorporateAction
from app.services.fifo_engine import recalculate_all_lots

def _fetch_yfinance_dividends_sync(symbol: str) -> List[Tuple[datetime.date, float]]:
    """Synchronously fetches dividend history from yfinance."""
    try:
        ticker = yf.Ticker(symbol)
        div_series = ticker.dividends
        if div_series is None or div_series.empty:
            return []

        results: List[Tuple[datetime.date, float]] = []
        for dt_idx, val in div_series.items():
            try:
                if hasattr(dt_idx, "date"):
                    ex_d = dt_idx.date()
                else:
                    ex_d = datetime.datetime.strptime(str(dt_idx)[:10], "%Y-%m-%d").date()

                rate = float(val)
                if rate > 0:
                    results.append((ex_d, rate))
            except Exception:
                continue

        results.sort(key=lambda x: x[0])
        return results
    except Exception as e:
        print(f"Error fetching yfinance dividends for {symbol}: {e}")
        return []

async def fetch_yfinance_dividends(symbol: str) -> List[Tuple[datetime.date, float]]:
    """Async wrapper to fetch dividend distribution dates and per-share amounts."""
    return await asyncio.to_thread(_fetch_yfinance_dividends_sync, symbol)

async def calculate_shares_on_date(
    db: AsyncSession,
    asset_id: int,
    account_id: int,
    target_date: datetime.date
) -> float:
    """
    Computes exact split-adjusted share holdings for an asset in an account on target_date.
    Chronologically applies buy, sell transactions, and corporate action splits/bonuses.
    """
    # 1. Fetch buy/sell transactions on or before target_date
    tx_stmt = (
        select(Transaction)
        .where(
            Transaction.asset_id == asset_id,
            Transaction.account_id == account_id,
            Transaction.transaction_date <= target_date,
            Transaction.transaction_type.in_(["buy", "sell"])
        )
        .order_by(asc(Transaction.transaction_date), asc(Transaction.transaction_id))
    )
    tx_res = await db.execute(tx_stmt)
    txs = tx_res.scalars().all()
    if not txs:
        return 0.0

    # 2. Fetch corporate actions on or before target_date
    ca_stmt = (
        select(CorporateAction)
        .where(
            CorporateAction.asset_id == asset_id,
            CorporateAction.action_date <= target_date,
            CorporateAction.action_type.in_(["split", "bonus"])
        )
        .order_by(asc(CorporateAction.action_date), asc(CorporateAction.action_id))
    )
    ca_res = await db.execute(ca_stmt)
    actions = ca_res.scalars().all()

    # Interleave events chronologically
    events = []
    for tx in txs:
        events.append((tx.transaction_date, 0, tx))
    for ca in actions:
        events.append((ca.action_date, 1, ca))

    events.sort(key=lambda x: (x[0], x[1]))

    running_shares = 0.0
    for _, _, item in events:
        if isinstance(item, Transaction):
            qty = float(item.quantity or 0.0)
            if item.transaction_type == "buy":
                running_shares += qty
            elif item.transaction_type == "sell":
                running_shares -= qty
        elif isinstance(item, CorporateAction):
            try:
                parts = item.ratio.split(":")
                if len(parts) == 2:
                    new_num, old_den = float(parts[0]), float(parts[1])
                    multiplier = new_num / old_den if old_den > 0 else 1.0
                    running_shares *= multiplier
            except Exception:
                pass

    return max(0.0, round(running_shares, 6))

async def sync_dividends_for_asset(db: AsyncSession, asset_id: int) -> int:
    """
    Synchronizes Yahoo Finance dividends for an asset across all holding accounts.
    Populates or updates the helper ExpectedDividend table (Table B).
    NEVER mutates or inserts into the actual Transaction ledger (Table C).
    """
    from app.db.models import ExpectedDividend

    asset_res = await db.execute(select(Asset).where(Asset.asset_id == asset_id))
    asset = asset_res.scalar_one_or_none()
    if not asset or not asset.symbol:
        return 0

    dividends_list = await fetch_yfinance_dividends(asset.symbol)
    if not dividends_list:
        return 0

    acc_stmt = (
        select(Account)
        .join(Transaction, Account.account_id == Transaction.account_id)
        .where(Transaction.asset_id == asset_id)
        .distinct()
    )
    acc_res = await db.execute(acc_stmt)
    accounts = acc_res.scalars().all()

    changes = 0
    for account in accounts:
        for ex_date, rate in dividends_list:
            shares = await calculate_shares_on_date(db, asset_id, account.account_id, ex_date)
            gross_amount = round(shares * rate, 2)

            exp_stmt = select(ExpectedDividend).where(
                ExpectedDividend.asset_id == asset_id,
                ExpectedDividend.account_id == account.account_id,
                ExpectedDividend.ex_date == ex_date
            )
            exp_res = await db.execute(exp_stmt)
            exp = exp_res.scalar_one_or_none()

            if shares > 0 and gross_amount > 0:
                if exp:
                    exp.eligible_shares = shares
                    exp.dividend_rate = rate
                    exp.expected_amount = gross_amount

                    if exp.matched_transaction_id:
                        tx_res = await db.execute(
                            select(Transaction).where(Transaction.transaction_id == exp.matched_transaction_id)
                        )
                        mtx = tx_res.scalar_one_or_none()
                        if mtx:
                            if abs(float(mtx.total_amount or 0.0) - gross_amount) > 0.01:
                                exp.status = "AMOUNT_MISMATCH"
                            else:
                                exp.status = "MATCHED"
                        else:
                            exp.matched_transaction_id = None
                            exp.status = "UNMATCHED"
                    elif exp.status not in ["DISMISSED"]:
                        exp.status = "UNMATCHED"
                    changes += 1
                else:
                    # Check if an existing confirmed dividend transaction in Table C matches
                    existing_tx_stmt = select(Transaction).where(
                        Transaction.asset_id == asset_id,
                        Transaction.account_id == account.account_id,
                        Transaction.transaction_type == "dividend",
                        Transaction.funding_account_id.is_not(None),
                        Transaction.transaction_date >= ex_date,
                        Transaction.transaction_date <= ex_date + datetime.timedelta(days=90),
                        Transaction.expected_dividend_id.is_(None)
                    )
                    existing_tx = (await db.execute(existing_tx_stmt)).scalars().first()

                    matched_id = None
                    init_status = "UNMATCHED"

                    if existing_tx and abs(float(existing_tx.total_amount or 0.0) - gross_amount) < 0.01:
                        matched_id = existing_tx.transaction_id
                        init_status = "MATCHED"

                    new_exp = ExpectedDividend(
                        asset_id=asset_id,
                        account_id=account.account_id,
                        ex_date=ex_date,
                        eligible_shares=shares,
                        dividend_rate=rate,
                        expected_amount=gross_amount,
                        currency=asset.currency or "USD",
                        source="yfinance",
                        matched_transaction_id=matched_id,
                        status=init_status
                    )
                    db.add(new_exp)
                    await db.flush()

                    if existing_tx and matched_id:
                        existing_tx.expected_dividend_id = new_exp.expected_dividend_id

                    changes += 1
            else:
                if exp:
                    if exp.matched_transaction_id:
                        exp.eligible_shares = 0.0
                        exp.expected_amount = 0.0
                        exp.status = "ORPHAN"
                        changes += 1
                    else:
                        await db.delete(exp)
                        changes += 1

    if changes > 0:
        await db.commit()

    return changes

async def sync_all_dividends(db: AsyncSession) -> int:
    """Syncs dividends for all registered stock/etf assets."""
    stmt = select(Asset).where(Asset.asset_type.in_(["stock", "etf"]))
    res = await db.execute(stmt)
    assets = res.scalars().all()
    total_changes = 0
    for asset in assets:
        try:
            ch = await sync_dividends_for_asset(db, asset.asset_id)
            total_changes += ch
        except Exception as e:
            print(f"Error syncing dividends for asset {asset.symbol}: {e}")
            continue
    return total_changes
