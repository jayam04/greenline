import os
import secrets
import pytest
from typing import AsyncGenerator, Tuple, Dict, Any
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.main import app
from app.db.database import get_db
from app.db.models import Base, User, Account, Category, Asset, ApiKey
from app.services.auth_service import get_password_hash
from app.api.deps import hash_api_key
from conftest import get_test_engine, get_test_sessionmaker


@pytest.fixture
async def e2e_session() -> AsyncGenerator[AsyncSession, None]:
    """Yields a dedicated async session for E2E tests."""
    engine = get_test_engine()
    SessionMaker = get_test_sessionmaker(engine)
    async with SessionMaker() as session:
        yield session
    await engine.dispose()


@pytest.fixture
async def e2e_seeded_env(e2e_session: AsyncSession) -> Dict[str, Any]:
    """
    Seeds a realistic ledger context for E2E opaque-box testing:
    - Primary User (user_id=1, username='e2e_primary')
    - Secondary User for cross-user isolation tests (user_id=2, username='e2e_secondary')
    - Demat and Checking Accounts
    - Standard Expense and Income Categories
    - Seeded Equity Asset (NVDA)
    """
    session = e2e_session

    # Seed primary user
    u1 = await session.get(User, 1)
    if not u1:
        u1 = User(user_id=1, username="e2e_primary", password_hash=get_password_hash("Password123!"))
        session.add(u1)
    else:
        u1.username = "e2e_primary"
        u1.password_hash = get_password_hash("Password123!")

    # Seed secondary user
    u2 = await session.get(User, 2)
    if not u2:
        u2 = User(user_id=2, username="e2e_secondary", password_hash=get_password_hash("Password123!"))
        session.add(u2)
    else:
        u2.username = "e2e_secondary"
        u2.password_hash = get_password_hash("Password123!")

    await session.commit()

    # Seed accounts
    acc_broker = Account(account_id=1, user_id=1, account_name="Interactive Brokers", account_type="demat", currency="USD")
    acc_checking = Account(account_id=2, user_id=1, account_name="Checking Account", account_type="bank", currency="EUR")
    acc_u2 = Account(account_id=3, user_id=2, account_name="Secondary Account", account_type="bank", currency="EUR")
    session.add_all([acc_broker, acc_checking, acc_u2])

    # Seed categories
    cat_groceries = Category(category_id=1, user_id=1, name="Groceries", category_type="EXPENSE", default_label="ESSENTIAL")
    cat_salary = Category(category_id=2, user_id=1, name="Salary", category_type="INCOME", default_label="INVESTMENT")
    session.add_all([cat_groceries, cat_salary])

    # Seed asset
    asset_nvda = Asset(asset_id=1, symbol="NVDA", name="NVIDIA Corporation", asset_type="EQUITY", currency="USD", exchange="NASDAQ")
    session.add(asset_nvda)

    await session.commit()

    return {
        "user_1": u1,
        "user_2": u2,
        "accounts": [acc_broker, acc_checking, acc_u2],
        "categories": [cat_groceries, cat_salary],
        "assets": [asset_nvda]
    }


@pytest.fixture
async def e2e_client() -> AsyncGenerator[AsyncClient, None]:
    """Yields an AsyncClient bound to the FastAPI application with test database override."""
    engine = get_test_engine()
    SessionMaker = get_test_sessionmaker(engine)

    async def override_get_db():
        async with SessionMaker() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    app.dependency_overrides.clear()
    await engine.dispose()


@pytest.fixture
async def e2e_primary_api_key(e2e_session: AsyncSession, e2e_seeded_env: Dict[str, Any]) -> str:
    """Provisions an active gl_mcp_ API key for primary user and returns the raw key."""
    raw_token = f"gl_mcp_{secrets.token_urlsafe(32)}"
    key_hash = hash_api_key(raw_token)
    prefix = f"{raw_token[:12]}..."

    api_key = ApiKey(
        user_id=1,
        name="E2E Primary Key",
        key_prefix=prefix,
        key_hash=key_hash,
        is_active=True
    )
    e2e_session.add(api_key)
    await e2e_session.commit()
    return raw_token


@pytest.fixture
async def e2e_secondary_api_key(e2e_session: AsyncSession, e2e_seeded_env: Dict[str, Any]) -> str:
    """Provisions an active gl_mcp_ API key for secondary user and returns the raw key."""
    raw_token = f"gl_mcp_{secrets.token_urlsafe(32)}"
    key_hash = hash_api_key(raw_token)
    prefix = f"{raw_token[:12]}..."

    api_key = ApiKey(
        user_id=2,
        name="E2E Secondary Key",
        key_prefix=prefix,
        key_hash=key_hash,
        is_active=True
    )
    e2e_session.add(api_key)
    await e2e_session.commit()
    return raw_token
