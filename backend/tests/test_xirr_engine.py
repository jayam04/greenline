import datetime
import pytest
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.db.models import Base, CashFlow
from app.services.xirr_engine import calculate_xirr_for_scope

@pytest.fixture
async def db_session():
    test_engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    TestSession = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)
    async with TestSession() as session:
        yield session
    await test_engine.dispose()

@pytest.mark.anyio
async def test_xirr_positive_return(db_session: AsyncSession):
    # Buy 1000 on 2025-01-01, current valuation 1200 on 2026-01-01 (1 year, +20%)
    cf = CashFlow(
        scope_type="portfolio",
        scope_id=None,
        flow_date=datetime.date(2025, 1, 1),
        amount=-1000.0,
        flow_type="buy"
    )
    db_session.add(cf)
    await db_session.commit()

    xirr_val = await calculate_xirr_for_scope(
        db=db_session,
        scope_type="portfolio",
        scope_id=None,
        current_valuation=1200.0,
        as_of_date=datetime.date(2026, 1, 1)
    )
    assert xirr_val is not None
    # Annualized return should be approximately 0.20 (20%)
    assert pytest.approx(xirr_val, rel=1e-2) == 0.20

@pytest.mark.anyio
async def test_xirr_negative_return(db_session: AsyncSession):
    # Buy 1000 on 2025-01-01, current valuation 800 on 2026-01-01 (1 year, -20%)
    cf = CashFlow(
        scope_type="portfolio",
        scope_id=None,
        flow_date=datetime.date(2025, 1, 1),
        amount=-1000.0,
        flow_type="buy"
    )
    db_session.add(cf)
    await db_session.commit()

    xirr_val = await calculate_xirr_for_scope(
        db=db_session,
        scope_type="portfolio",
        scope_id=None,
        current_valuation=800.0,
        as_of_date=datetime.date(2026, 1, 1)
    )
    assert xirr_val is not None
    assert pytest.approx(xirr_val, rel=1e-2) == -0.20

@pytest.mark.anyio
async def test_xirr_multiple_cash_flows_and_irregular_dates(db_session: AsyncSession):
    # Multiple buys and dividend inflows on irregular calendar dates:
    # 2025-01-15: Initial buy -5000
    # 2025-04-03: Dividend +150
    # 2025-08-22: Second buy -2500
    # 2025-11-10: Dividend +200
    # 2026-03-01: Valuation 8500
    flows = [
        CashFlow(scope_type="portfolio", scope_id=None, flow_date=datetime.date(2025, 1, 15), amount=-5000.0, flow_type="buy"),
        CashFlow(scope_type="portfolio", scope_id=None, flow_date=datetime.date(2025, 4, 3), amount=150.0, flow_type="dividend"),
        CashFlow(scope_type="portfolio", scope_id=None, flow_date=datetime.date(2025, 8, 22), amount=-2500.0, flow_type="buy"),
        CashFlow(scope_type="portfolio", scope_id=None, flow_date=datetime.date(2025, 11, 10), amount=200.0, flow_type="dividend"),
    ]
    db_session.add_all(flows)
    await db_session.commit()

    xirr_val = await calculate_xirr_for_scope(
        db=db_session,
        scope_type="portfolio",
        scope_id=None,
        current_valuation=8500.0,
        as_of_date=datetime.date(2026, 3, 1)
    )
    assert xirr_val is not None
    assert xirr_val > 0.10
    assert xirr_val < 0.35

@pytest.mark.anyio
async def test_xirr_empty_portfolio(db_session: AsyncSession):
    # No cash flows and current valuation is 0
    xirr_val = await calculate_xirr_for_scope(
        db=db_session,
        scope_type="portfolio",
        scope_id=None,
        current_valuation=0.0,
        as_of_date=datetime.date(2026, 1, 1)
    )
    assert xirr_val is None

@pytest.mark.anyio
async def test_xirr_insufficient_cash_flows(db_session: AsyncSession):
    # Scenario A: Only 1 flow, no current valuation
    cf = CashFlow(scope_type="portfolio", scope_id=None, flow_date=datetime.date(2025, 1, 1), amount=-1000.0, flow_type="buy")
    db_session.add(cf)
    await db_session.commit()

    xirr_1 = await calculate_xirr_for_scope(
        db=db_session,
        scope_type="portfolio",
        scope_id=None,
        current_valuation=0.0,
        as_of_date=datetime.date(2026, 1, 1)
    )
    assert xirr_1 is None

    # Scenario B: Multiple flows but all are negative (no positive flow and valuation 0)
    cf2 = CashFlow(scope_type="portfolio", scope_id=None, flow_date=datetime.date(2025, 6, 1), amount=-500.0, flow_type="buy")
    db_session.add(cf2)
    await db_session.commit()

    xirr_2 = await calculate_xirr_for_scope(
        db=db_session,
        scope_type="portfolio",
        scope_id=None,
        current_valuation=0.0,
        as_of_date=datetime.date(2026, 1, 1)
    )
    assert xirr_2 is None

    # Scenario C: Multiple flows but all are positive (no negative outflow)
    test_engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    TestSession = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)
    async with TestSession() as session:
        session.add(CashFlow(scope_type="portfolio", scope_id=None, flow_date=datetime.date(2025, 1, 1), amount=100.0, flow_type="dividend"))
        await session.commit()
        xirr_3 = await calculate_xirr_for_scope(
            db=session,
            scope_type="portfolio",
            scope_id=None,
            current_valuation=500.0,
            as_of_date=datetime.date(2026, 1, 1)
        )
        assert xirr_3 is None
    await test_engine.dispose()

@pytest.mark.anyio
async def test_xirr_scope_isolation(db_session: AsyncSession):
    # Cashflows for Asset 1 vs Asset 2
    cf_asset1 = CashFlow(scope_type="asset", scope_id=1, flow_date=datetime.date(2025, 1, 1), amount=-1000.0, flow_type="buy")
    cf_asset2 = CashFlow(scope_type="asset", scope_id=2, flow_date=datetime.date(2025, 1, 1), amount=-5000.0, flow_type="buy")
    db_session.add_all([cf_asset1, cf_asset2])
    await db_session.commit()

    # Asset 1 calculation should only use asset_id 1
    xirr_asset1 = await calculate_xirr_for_scope(
        db=db_session,
        scope_type="asset",
        scope_id=1,
        current_valuation=1300.0,
        as_of_date=datetime.date(2026, 1, 1)
    )
    assert xirr_asset1 is not None
    assert pytest.approx(xirr_asset1, rel=1e-2) == 0.30

    # Asset 2 with valuation 5000 (flat return ~ 0%)
    xirr_asset2 = await calculate_xirr_for_scope(
        db=db_session,
        scope_type="asset",
        scope_id=2,
        current_valuation=5000.0,
        as_of_date=datetime.date(2026, 1, 1)
    )
    assert xirr_asset2 is not None
    assert pytest.approx(xirr_asset2, abs=1e-3) == 0.0
