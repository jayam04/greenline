import datetime
import pytest
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import select, text

from app.db.database import Base
from app.db.models import User, Account, Asset, ExpectedDividend, Transaction
from app.db.migrations import run_db_migrations, get_applied_migrations, _VERSIONS
from app.services.auth_service import get_or_sync_auth0_user
from app.services.dividend_engine import sync_all_dividends


TEST_DB_URL = "oracle+oracledb://greenline_test:test_password@localhost:1521/?service_name=FREEPDB1"


@pytest.fixture
async def test_session():
    test_engine = create_async_engine(TEST_DB_URL, echo=False)
    TestSession = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)
    async with TestSession() as session:
        yield session
    await test_engine.dispose()


@pytest.mark.anyio
async def test_migration_v012_in_versions():
    version_keys = [v[0] for v in _VERSIONS]
    assert "v012_auth0_user_persistence" in version_keys


@pytest.mark.anyio
async def test_migration_v012_applied(test_session: AsyncSession):
    await run_db_migrations(test_session)
    applied = await get_applied_migrations(test_session)
    assert "v012_auth0_user_persistence" in applied


@pytest.mark.anyio
async def test_user_model_auth0_fields(test_session: AsyncSession):
    user = User(
        auth0_sub="auth0|test_sub_12345",
        email="test_auth0_user@example.com",
        name="Test Auth0 User",
        picture="https://example.com/avatar.png",
        username="test_auth0_user@example.com",
        password_hash=None,
    )
    assert hasattr(user, "auth0_sub")
    assert hasattr(user, "email")
    assert hasattr(user, "name")
    assert hasattr(user, "picture")
    assert hasattr(user, "updated_at")
    assert user.password_hash is None


@pytest.mark.anyio
async def test_get_or_sync_auth0_user_lifecycle(test_session: AsyncSession):
    await run_db_migrations(test_session)
    unique_sub = f"auth0|lifecycle_{datetime.datetime.utcnow().timestamp()}"
    email = f"user_{datetime.datetime.utcnow().timestamp()}@example.com"

    # 1. Provision new user
    user1 = await get_or_sync_auth0_user(
        db=test_session,
        sub=unique_sub,
        email=email,
        name="Original Name",
        picture="https://example.com/pic1.png",
    )
    assert user1 is not None
    assert user1.auth0_sub == unique_sub
    assert user1.email == email
    assert user1.name == "Original Name"
    assert user1.picture == "https://example.com/pic1.png"
    assert user1.user_id is not None
    assert user1.password_hash is None

    # 2. Sync profile update
    user2 = await get_or_sync_auth0_user(
        db=test_session,
        sub=unique_sub,
        email=email,
        name="Updated Name",
        picture="https://example.com/pic2.png",
    )
    assert user2.user_id == user1.user_id
    assert user2.name == "Updated Name"
    assert user2.picture == "https://example.com/pic2.png"

    # 3. Account linking: local unlinked user with same email
    link_email = f"link_{datetime.datetime.utcnow().timestamp()}@example.com"
    local_user = User(
        user_id=None,
        username=link_email,
        email=link_email,
        name="Local Unlinked User",
        password_hash="some_hash",
    )
    test_session.add(local_user)
    await test_session.commit()
    await test_session.refresh(local_user)

    link_sub = f"auth0|link_{datetime.datetime.utcnow().timestamp()}"
    linked_user = await get_or_sync_auth0_user(
        db=test_session,
        sub=link_sub,
        email=link_email,
        name="Linked Name",
    )
    assert linked_user.user_id == local_user.user_id
    assert linked_user.auth0_sub == link_sub
    assert linked_user.name == "Linked Name"


@pytest.mark.anyio
async def test_expected_dividend_user_scoping(test_session: AsyncSession):
    # Create non-zero user
    u = User(
        auth0_sub=f"auth0|divuser_{datetime.datetime.utcnow().timestamp()}",
        email=f"divuser_{datetime.datetime.utcnow().timestamp()}@example.com",
        username=f"divuser_{datetime.datetime.utcnow().timestamp()}",
    )
    test_session.add(u)
    await test_session.commit()
    await test_session.refresh(u)

    account = Account(
        user_id=u.user_id,
        account_name=f"Div Test Acc {u.user_id}",
        account_type="demat",
        currency="USD",
    )
    test_session.add(account)
    await test_session.commit()
    await test_session.refresh(account)

    asset = Asset(
        symbol=f"DIV_{datetime.datetime.utcnow().timestamp()}"[:10],
        name="Div Asset",
        asset_type="stock",
        currency="USD",
    )
    test_session.add(asset)
    await test_session.commit()
    await test_session.refresh(asset)

    # Directly create an ExpectedDividend and verify it accepts user_id
    exp = ExpectedDividend(
        user_id=account.user_id,
        asset_id=asset.asset_id,
        account_id=account.account_id,
        ex_date=datetime.date.today(),
        eligible_shares=10.0,
        dividend_rate=1.5,
        expected_amount=15.0,
        currency="USD",
        source="manual",
        status="UNMATCHED",
    )
    test_session.add(exp)
    await test_session.commit()
    await test_session.refresh(exp)

    assert exp.user_id == account.user_id
    assert exp.user_id == u.user_id
