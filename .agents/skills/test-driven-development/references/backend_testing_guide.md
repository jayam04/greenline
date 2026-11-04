# Backend Testing Guide: Fast, Isolated Async Tests with Pytest and Oracle

## Standard Session Fixture (Oracle Free)

Use standard fixtures provided by `backend/tests/conftest.py`:

```python
import pytest
import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.models import User, Account, Asset, Transaction, Lot, PriceHistory

@pytest.mark.anyio
async def test_my_financial_feature(db_session: AsyncSession):
    # 1. Arrange test data
    user = User(username="admin", password_hash="hash")
    account = Account(account_name="Zerodha", account_type="demat", currency="INR", user_id=0)
    db_session.add_all([user, account])
    await db_session.commit()

    # 2. Act
    # Execute service function or router logic

    # 3. Assert
    # Check expected balances, lots, or P&L
```

## API Endpoint Integration Test Fixture

Use the `client` or `app_client` fixtures provided by `conftest.py`:

```python
import pytest
from httpx import AsyncClient

@pytest.mark.anyio
async def test_endpoint(app_client: AsyncClient):
    res = await app_client.get("/api/v1/accounts")
    assert res.status_code == 200
```

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
