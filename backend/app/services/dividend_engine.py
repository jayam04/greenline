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
    Creates or updates auto-generated dividends with funding_account_id=None.
    Removes orphan auto-generated dividends if shares held drops to 0.
    Preserves manual dividend entries.
    """
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

            existing_tx_stmt = select(Transaction).where(
                Transaction.asset_id == asset_id,
                Transaction.account_id == account.account_id,
                Transaction.transaction_date == ex_date,
                Transaction.transaction_type == "dividend"
            )
            existing_res = await db.execute(existing_tx_stmt)
            existing_tx = existing_res.scalar_one_or_none()

            gross_amount = round(shares * rate, 2)

            if shares > 0 and gross_amount > 0:
                if existing_tx:
                    if getattr(existing_tx, "source", None) == "yfinance_auto":
                        if (
                            abs(float(existing_tx.quantity or 0.0) - shares) > 1e-5
                            or abs(float(existing_tx.price_per_unit or 0.0) - rate) > 1e-5
                            or abs(float(existing_tx.total_amount or 0.0) - gross_amount) > 1e-2
                        ):
                            existing_tx.quantity = shares
                            existing_tx.price_per_unit = rate
                            existing_tx.total_amount = gross_amount
                            existing_tx.notes = f"Auto-generated dividend for {asset.symbol} ({shares} shares @ {rate}/share)"
                            changes += 1
                else:
                    new_div_tx = Transaction(
                        account_id=account.account_id,
                        funding_account_id=None,
                        asset_id=asset_id,
                        transaction_type="dividend",
                        transaction_date=ex_date,
                        quantity=shares,
                        price_per_unit=rate,
                        total_amount=gross_amount,
                        fees=0.0,
                        taxes=0.0,
                        source="yfinance_auto",
                        notes=f"Auto-generated dividend for {asset.symbol} ({shares} shares @ {rate}/share)"
                    )
                    db.add(new_div_tx)
                    changes += 1
            else:
                if existing_tx and getattr(existing_tx, "source", None) == "yfinance_auto":
                    await db.delete(existing_tx)
                    changes += 1

    if changes > 0:
        await db.commit()
        await recalculate_all_lots(db)

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
