import pytest
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import text
from app.db.migrations import run_db_migrations, get_applied_migrations

@pytest.mark.anyio
async def test_db_migrations_idempotency():
    test_engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    TestSession = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)
    
    async with TestSession() as session:
        # Run migrations first time
        await run_db_migrations(session)
        applied = await get_applied_migrations(session)
        
        assert "v001_initial_schema" in applied
        assert "v002_transactions_funding_account" in applied
        assert "v003_assets_industry_column" in applied
        assert "v004_cashflow_transaction_kind" in applied
        assert "v005_signed_cashflow_amounts" in applied

        # Running migrations again should be completely idempotent and not raise errors
        await run_db_migrations(session)
        applied_again = await get_applied_migrations(session)
        assert applied == applied_again

@pytest.mark.anyio
async def test_schema_migrations_table_exists():
    test_engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    TestSession = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)
    
    async with TestSession() as session:
        await run_db_migrations(session)
        res = await session.execute(text("SELECT COUNT(*) FROM schema_migrations"))
        count = res.scalar()
        assert count >= 5
