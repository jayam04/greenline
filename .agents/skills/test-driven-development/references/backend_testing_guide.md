# Backend Testing Guide: Fast, Isolated Async Tests with Pytest

## Standard In-Memory Session Fixture

Use this pattern for all backend unit & service tests:

```python
import pytest
import datetime
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select

from app.db.database import Base
from app.db.models import User, Account, Asset, Transaction, Lot, PriceHistory

@pytest.mark.anyio
async def test_my_financial_feature():
    # 1. Setup isolated in-memory database
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async_session = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session() as session:
        # 2. Arrange test data
        user = User(username="admin", password_hash="hash")
        account = Account(account_name="Zerodha", account_type="demat", currency="INR")
        session.add_all([user, account])
        await session.commit()

        # 3. Act
        # Execute service function or router logic

        # 4. Assert
        # Check expected balances, lots, or P&L
```

## API Endpoint Integration Test Fixture

Use this pattern when testing FastAPI routes with `httpx.AsyncClient`:

```python
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from app.db.database import Base, get_db
from app.db.models import User
from app.api.deps import get_current_user
from app.main import app

@pytest.fixture
def anyio_backend():
    return "asyncio"

@pytest.fixture
async def test_client():
    test_engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    SessionMaker = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)
    async with SessionMaker() as session:
        mock_user = User(user_id=1, username="testuser", password_hash="dummy")

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
```
