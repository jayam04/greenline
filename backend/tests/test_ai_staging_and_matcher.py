import datetime
import pytest
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import select

from app.db.models import (
    Base, Account, Asset, Transaction, CashflowTransaction, CashflowPayment,
    Category, ImportBatch, StagedRecord
)
from app.services.ai.matcher import match_staged_record
from app.services.ai.staging_service import (
    create_import_batch,
    stage_parsed_records,
    commit_import_batch,
    update_staged_record,
    delete_staged_record
)
from app.services.ai.chunker import chunk_tabular_data

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
async def test_import_batch_and_staged_records_crud(db_session: AsyncSession):
    # Setup test account
    acc = Account(account_name="Trading Demat", account_type="demat", currency="USD")
    db_session.add(acc)
    await db_session.commit()
    await db_session.refresh(acc)

    batch = await create_import_batch(
        db=db_session,
        filename="zerodha_trades_2025.csv",
        file_type="csv",
        target_account_id=acc.account_id,
        default_currency="USD",
        custom_instructions="Map all INFY trades to Zerodha Demat"
    )
    assert batch.batch_id is not None
    assert batch.filename == "zerodha_trades_2025.csv"
    assert batch.status == "processing"

    raw_items = [
        {
            "record_type": "investment",
            "transaction_date": datetime.date(2025, 3, 10),
            "action_type": "buy",
            "account_id": acc.account_id,
            "asset_symbol_raw": "AAPL",
            "quantity": 10.0,
            "price_per_unit": 150.0,
            "total_amount": 1500.0,
            "fees": 5.0,
            "currency": "USD",
            "notes": "Tech buy"
        }
    ]

    staged_records = await stage_parsed_records(db=db_session, batch_id=batch.batch_id, raw_records=raw_items)
    assert len(staged_records) == 1
    assert staged_records[0].asset_symbol_raw == "AAPL"
    assert staged_records[0].match_status == "new"
    assert staged_records[0].review_status == "approved"

    # Test update
    updated = await update_staged_record(
        db=db_session,
        staged_id=staged_records[0].staged_id,
        notes="Updated tech buy note",
        review_status="modified"
    )
    assert updated.notes == "Updated tech buy note"
    assert updated.review_status == "modified"

    # Test delete
    deleted = await delete_staged_record(db=db_session, staged_id=staged_records[0].staged_id)
    assert deleted is True

@pytest.mark.anyio
async def test_two_tier_matcher_exact_and_probable_matches(db_session: AsyncSession):
    # 1. Setup account and asset
    acc = Account(account_name="Main Broker", account_type="demat", currency="USD")
    ast = Asset(symbol="MSFT", name="Microsoft Corp", asset_type="stock", currency="USD")
    db_session.add_all([acc, ast])
    await db_session.commit()
    await db_session.refresh(acc)
    await db_session.refresh(ast)

    # 2. Existing transaction in database: MSFT buy on 2025-05-01, 10 shares @ 400 = 4000.0
    existing_tx = Transaction(
        account_id=acc.account_id,
        asset_id=ast.asset_id,
        transaction_type="buy",
        transaction_date=datetime.date(2025, 5, 1),
        quantity=10.0,
        price_per_unit=400.0,
        total_amount=4000.0
    )
    db_session.add(existing_tx)
    await db_session.commit()
    await db_session.refresh(existing_tx)

    batch = await create_import_batch(db=db_session, filename="broker_statement.pdf", file_type="pdf")

    # Case A: Exact Match (same date, same account, same asset, same amount)
    rec_exact = StagedRecord(
        batch_id=batch.batch_id,
        record_type="investment",
        transaction_date=datetime.date(2025, 5, 1),
        action_type="buy",
        account_id=acc.account_id,
        asset_id=ast.asset_id,
        asset_symbol_raw="MSFT",
        quantity=10.0,
        price_per_unit=400.0,
        total_amount=4000.0
    )
    match_a = await match_staged_record(db_session, rec_exact)
    assert match_a.status == "exact_match"
    assert match_a.matched_id == existing_tx.transaction_id
    assert match_a.default_review_status == "skipped"

    # Case B: Probable Match (settlement date drift: 2025-05-03 vs 2025-05-01, ±2 days)
    rec_probable = StagedRecord(
        batch_id=batch.batch_id,
        record_type="investment",
        transaction_date=datetime.date(2025, 5, 3), # T+2 settlement date
        action_type="buy",
        account_id=acc.account_id,
        asset_id=ast.asset_id,
        asset_symbol_raw="MSFT",
        quantity=10.0,
        price_per_unit=400.0,
        total_amount=4000.0
    )
    match_b = await match_staged_record(db_session, rec_probable)
    assert match_b.status == "probable_match"
    assert match_b.matched_id == existing_tx.transaction_id
    assert match_b.default_review_status == "pending"

    # Case C: New Record (different date > 2 days)
    rec_new = StagedRecord(
        batch_id=batch.batch_id,
        record_type="investment",
        transaction_date=datetime.date(2025, 5, 15),
        action_type="buy",
        account_id=acc.account_id,
        asset_id=ast.asset_id,
        asset_symbol_raw="MSFT",
        quantity=5.0,
        price_per_unit=400.0,
        total_amount=2000.0
    )
    match_c = await match_staged_record(db_session, rec_new)
    assert match_c.status == "new"
    assert match_c.matched_id is None
    assert match_c.default_review_status == "approved"

@pytest.mark.anyio
async def test_atomic_commit_final_green_flag(db_session: AsyncSession):
    # Setup test account
    acc = Account(account_name="Robinhood", account_type="demat", currency="USD")
    db_session.add(acc)
    await db_session.commit()
    await db_session.refresh(acc)

    batch = await create_import_batch(db=db_session, filename="trades.csv", file_type="csv")

    raw_items = [
        # Record 1: Approved New Trade (Asset does not exist yet; should auto-create TSLA)
        {
            "record_type": "investment",
            "transaction_date": datetime.date(2025, 4, 10),
            "action_type": "buy",
            "account_id": acc.account_id,
            "asset_symbol_raw": "TSLA",
            "asset_name_raw": "Tesla Inc",
            "quantity": 5.0,
            "price_per_unit": 200.0,
            "total_amount": 1000.0,
            "fees": 2.0,
            "review_status": "approved"
        },
        # Record 2: Skipped Duplicate (Should NOT be inserted into live transactions)
        {
            "record_type": "investment",
            "transaction_date": datetime.date(2025, 4, 11),
            "action_type": "buy",
            "account_id": acc.account_id,
            "asset_symbol_raw": "TSLA",
            "quantity": 5.0,
            "price_per_unit": 200.0,
            "total_amount": 1000.0,
            "review_status": "skipped"
        }
    ]

    staged_records = await stage_parsed_records(db=db_session, batch_id=batch.batch_id, raw_records=raw_items)
    assert len(staged_records) == 2

    # Give Final Green Flag commit
    result = await commit_import_batch(db=db_session, batch_id=batch.batch_id)
    assert result["committed_count"] == 1
    assert result["skipped_count"] == 1
    assert result["status"] == "merged"

    # Verify live database
    tx_res = await db_session.execute(select(Transaction))
    live_txs = tx_res.scalars().all()
    assert len(live_txs) == 1
    assert live_txs[0].total_amount == 1000.0

    # Verify TSLA asset was created
    ast_res = await db_session.execute(select(Asset).where(Asset.symbol == "TSLA"))
    tsla = ast_res.scalar_one_or_none()
    assert tsla is not None
    assert tsla.name == "Tesla Inc"

@pytest.mark.anyio
async def test_chunk_tabular_data():
    sample_csv = "Date,Symbol,Type,Quantity,Price,Amount\n" + "\n".join(
        [f"2025-01-01,SYM{i},BUY,10,100,1000" for i in range(250)]
    )
    chunks = chunk_tabular_data(sample_csv.encode("utf-8"), mime_type="text/csv", chunk_size=100)
    assert len(chunks) == 3 # 100, 100, 50
    assert "SYM0" in chunks[0]
    assert "SYM100" in chunks[1]
