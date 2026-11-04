import os
import asyncio
import pytest
from typing import AsyncGenerator, Tuple
import sqlalchemy.ext.asyncio as sa_async
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession, AsyncEngine
from sqlalchemy.pool import NullPool
from sqlalchemy import text, select
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.api.deps import get_db, get_current_user
from app.db.database import Base, get_tables_in_dependency_order
from app.db.models import User

TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL", 
    "oracle+oracledb://greenline_test:test_password@localhost:1521/?service_name=FREEPDB1"
)

# Patch create_async_engine so all test-created engines use NullPool on the Oracle test database
_orig_create_async_engine = sa_async.create_async_engine

def _test_create_async_engine(url, *args, **kwargs):
    kwargs["poolclass"] = NullPool
    clean_url = str(url)
    if "sqlite" in clean_url:
        clean_url = TEST_DATABASE_URL
    return _orig_create_async_engine(clean_url, *args, **kwargs)

sa_async.create_async_engine = _test_create_async_engine

def get_test_engine() -> AsyncEngine:
    return _orig_create_async_engine(
        TEST_DATABASE_URL,
        echo=False,
        poolclass=NullPool,
    )

def get_test_sessionmaker(engine: AsyncEngine = None) -> async_sessionmaker:
    if engine is None:
        engine = get_test_engine()
    return async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

from sqlalchemy.orm import Session
from sqlalchemy import event, inspect

@event.listens_for(Session, "before_flush")
def handle_test_user_zero(session, flush_context, instances):
    for obj in list(session.new):
        if isinstance(obj, User) and getattr(obj, "user_id", 0) == 0:
            row = session.connection().execute(text("SELECT COUNT(*) FROM users WHERE user_id = 0")).scalar()
            if row > 0:
                session.connection().execute(
                    text("UPDATE users SET username = :u, password_hash = :p WHERE user_id = 0"),
                    {"u": obj.username, "p": obj.password_hash}
                )
                session.expunge(obj)
                state = inspect(obj)
                state.key = session.identity_key(User, (0,))
                session.identity_map.add(state)

def pytest_sessionstart(session):
    """Synchronously create schema once for the test session and ensure user 0 exists."""
    async def _init():
        engine = get_test_engine()
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            res = await conn.execute(text("SELECT COUNT(*) FROM users WHERE user_id = 0"))
            if res.scalar() == 0:
                await conn.execute(
                    text("INSERT INTO users (user_id, username, password_hash) VALUES (0, 'system', 'hash')")
                )
        await engine.dispose()
    asyncio.run(_init())

async def clean_database_tables(session: AsyncSession):
    """Delete rows from all tables in reverse dependency order, preserving user 0."""
    try:
        from app.db.models import Transaction, ExpectedDividend, Account
        from sqlalchemy import update
        await session.execute(update(Transaction).values(expected_dividend_id=None))
        await session.execute(update(ExpectedDividend).values(matched_transaction_id=None))
        await session.execute(update(Account).values(default_dividend_account_id=None))
    except Exception:
        pass

    tables = list(reversed(get_tables_in_dependency_order()))
    for table in tables:
        if table.name == "schema_migrations":
            continue
        elif table.name == "users":
            await session.execute(table.delete().where(table.c.user_id != 0))
        else:
            await session.execute(table.delete())
    # Ensure User 0 always exists and reset its credentials to system defaults
    res = await session.execute(select(User).where(User.user_id == 0))
    u0 = res.scalars().first()
    if not u0:
        await session.execute(text("INSERT INTO users (user_id, username, password_hash) VALUES (0, 'system', 'hash')"))
    else:
        u0.username = "system"
        u0.password_hash = "hash"
    await session.commit()

@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_protocol(item, nextitem):
    """Clean database tables before and after every test run outside the test event loop."""
    async def _clean():
        engine = get_test_engine()
        SessionMaker = get_test_sessionmaker(engine)
        async with SessionMaker() as session:
            await clean_database_tables(session)
        await engine.dispose()
    try:
        asyncio.run(_clean())
    except Exception as e:
        print(f"[conftest before clean error] {e}")
    yield
    try:
        asyncio.run(_clean())
    except Exception as e:
        print(f"[conftest after clean error] {e}")

@pytest.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Yield a fresh database session."""
    engine = get_test_engine()
    SessionMaker = get_test_sessionmaker(engine)
    async with SessionMaker() as session:
        yield session
    await engine.dispose()

@pytest.fixture
async def test_db_session() -> AsyncGenerator[Tuple[AsyncSession, async_sessionmaker], None]:
    """Yields (session, sessionmaker) tuple."""
    engine = get_test_engine()
    SessionMaker = get_test_sessionmaker(engine)
    async with SessionMaker() as session:
        yield session, SessionMaker
    await engine.dispose()

@pytest.fixture
async def client(test_db_session) -> AsyncGenerator[Tuple[AsyncClient, AsyncSession, async_sessionmaker], None]:
    """Client fixture yielding (client, session, session_maker) with dependency overrides."""
    session, session_maker = test_db_session
    mock_user = User(user_id=0, username="system")

    async def override_get_db():
        yield session

    async def override_get_current_user():
        return mock_user

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac, session, session_maker

    app.dependency_overrides.clear()

@pytest.fixture
async def app_client(client) -> AsyncGenerator[AsyncClient, None]:
    """Convenience fixture yielding AsyncClient."""
    ac, _, _ = client
    yield ac
