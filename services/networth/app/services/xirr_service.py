import datetime
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, asc
import pyxirr

try:
    from ..db.models import CashFlow
except (ImportError, ValueError):
    from app.db.models import CashFlow


async def calculate_xirr_for_scope(
    db: AsyncSession,
    scope_type: str,  # "portfolio", "account", "asset"
    scope_id: Optional[int],
    current_valuation: float,
    as_of_date: Optional[datetime.date] = None,
    user_id: Optional[int] = None
) -> Optional[float]:
    """
    Computes XIRR for a given scope using pyxirr.
    Appends a synthetic positive cash flow equal to current_valuation on as_of_date.
    """
    if as_of_date is None:
        as_of_date = datetime.date.today()

    stmt = select(CashFlow).where(CashFlow.scope_type == scope_type)
    if scope_id is not None:
        stmt = stmt.where(CashFlow.scope_id == scope_id)
    if user_id is not None:
        stmt = stmt.where(CashFlow.user_id == user_id)
    stmt = stmt.order_by(asc(CashFlow.flow_date))

    result = await db.execute(stmt)
    flows: List[CashFlow] = result.scalars().all()

    dates: List[datetime.date] = []
    amounts: List[float] = []

    for f in flows:
        dates.append(f.flow_date)
        amounts.append(f.amount)

    if current_valuation > 0:
        dates.append(as_of_date)
        amounts.append(current_valuation)

    if len(dates) < 2:
        return None

    has_negative = any(a < 0 for a in amounts)
    has_positive = any(a > 0 for a in amounts)
    if not (has_negative and has_positive):
        return None

    try:
        xirr_val = pyxirr.xirr(dates, amounts)
        if xirr_val is None or str(xirr_val) == 'nan':
            return None
        return float(xirr_val)
    except Exception:
        return None
