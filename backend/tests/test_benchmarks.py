import pytest
import datetime
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from app.db.database import Base, get_db
from app.db.models import User, Benchmark
from app.api.deps import get_current_user
from app.main import app

@pytest.fixture
def anyio_backend():
    return "asyncio"

@pytest.fixture
async def test_db_session():
    test_engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    SessionMaker = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)
    async with SessionMaker() as session:
        yield session

@pytest.fixture
async def client(test_db_session):
    session = test_db_session
    mock_user = User(user_id=1, username="testuser")

    async def override_get_db():
        yield session

    async def override_get_current_user():
        return mock_user

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac, session

    app.dependency_overrides.clear()

@pytest.mark.anyio
async def test_get_benchmark_query_param(client):
    ac, session = client

    # Pre-populate benchmark entries in DB for S&P 500
    bms = [
        Benchmark(benchmark_name="S&P 500", price_date=datetime.date(2026, 8, 1), close_value=5000.0),
        Benchmark(benchmark_name="S&P 500", price_date=datetime.date(2026, 8, 2), close_value=5050.0),
        Benchmark(benchmark_name="S&P 500", price_date=datetime.date(2026, 8, 3), close_value=5100.0),
        Benchmark(benchmark_name="S&P 500", price_date=datetime.date(2026, 8, 4), close_value=5150.0),
        Benchmark(benchmark_name="S&P 500", price_date=datetime.date(2026, 8, 5), close_value=5200.0),
        Benchmark(benchmark_name="S&P 500", price_date=datetime.date(2026, 8, 6), close_value=5250.0),
    ]
    session.add_all(bms)
    await session.commit()

    # Query with query param symbol=^GSPC
    resp = await ac.get("/api/v1/benchmarks?symbol=^GSPC")
    assert resp.status_code == 200
    data = resp.json()
    assert data["benchmark_name"] == "S&P 500"
    assert len(data["data"]) == 6
    assert data["data"][0]["close_value"] == 5000.0
    assert data["data"][-1]["close_value"] == 5250.0

@pytest.mark.anyio
async def test_get_benchmark_bitcoin_query(client):
    ac, session = client

    # Pre-populate benchmark entries in DB for Bitcoin
    bms = [
        Benchmark(benchmark_name="Bitcoin", price_date=datetime.date(2026, 8, 1), close_value=60000.0),
        Benchmark(benchmark_name="Bitcoin", price_date=datetime.date(2026, 8, 2), close_value=61000.0),
        Benchmark(benchmark_name="Bitcoin", price_date=datetime.date(2026, 8, 3), close_value=62000.0),
        Benchmark(benchmark_name="Bitcoin", price_date=datetime.date(2026, 8, 4), close_value=63000.0),
        Benchmark(benchmark_name="Bitcoin", price_date=datetime.date(2026, 8, 5), close_value=64000.0),
        Benchmark(benchmark_name="Bitcoin", price_date=datetime.date(2026, 8, 6), close_value=65000.0),
    ]
    session.add_all(bms)
    await session.commit()

    resp = await ac.get("/api/v1/benchmarks?symbol=BTC-USD")
    assert resp.status_code == 200
    data = resp.json()
    assert data["benchmark_name"] == "Bitcoin"
    assert len(data["data"]) == 6
    assert data["data"][0]["close_value"] == 60000.0
