import pytest
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import select
from app.db.database import Base
from app.db.models import User
from app.main import app

@pytest.mark.anyio
async def test_lifespan_handles_multiple_users_without_error(monkeypatch):
    test_engine = create_async_engine("oracle+oracledb://greenline_test:test_password@localhost:1521/?service_name=FREEPDB1", echo=False)
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    TestSession = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)

    # Pre-populate database with multiple users (simulating existing database)
    async with TestSession() as session:
        session.add(User(user_id=1, username="admin", password_hash="hash1"))
        session.add(User(user_id=2, username="another_user", password_hash="hash2"))
        await session.commit()

    async def mock_backfill():
        pass

    import app.main as main_module
    monkeypatch.setattr(main_module, "AsyncSessionLocal", TestSession)
    monkeypatch.setattr(main_module, "start_scheduler", lambda: None)
    monkeypatch.setattr(main_module, "_startup_backfill", mock_backfill)

    # Run lifespan context
    async with app.router.lifespan_context(app):
        pass

    # Verify admin user is mapped to user_id = 0
    async with TestSession() as session:
        users = (await session.execute(select(User))).scalars().all()
        user_ids = {u.user_id for u in users}
        assert 0 in user_ids
