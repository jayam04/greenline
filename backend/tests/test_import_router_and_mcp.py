import datetime
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import select

from app.db.models import Base, User, Account, Asset, Transaction
from app.db.database import get_db
from app.main import app
from app.api.deps import get_current_user
from app.mcp.server import (
    get_ledger_context,
    search_existing_transactions,
    create_staging_batch,
    stage_transactions,
    commit_batch
)

@pytest.fixture
async def app_client():
    test_engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    TestSession = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_db():
        async with TestSession() as session:
            yield session

    test_user = User(user_id=1, username="testadmin", password_hash="hash")
    async def override_get_current_user():
        return test_user

    # Seed initial account and test user
    async with TestSession() as session:
        session.add(test_user)
        session.add(Account(account_id=1, account_name="Interactive Brokers", account_type="demat", currency="USD"))
        await session.commit()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    app.dependency_overrides.clear()
    await test_engine.dispose()

@pytest.mark.anyio
async def test_import_upload_and_review_workflow(app_client: AsyncClient):
    csv_content = b"Date,Symbol,Type,Quantity,Price,Amount\n2025-06-01,NVDA,BUY,10,120,1200\n"
    files = {"file": ("nvda_trade.csv", csv_content, "text/csv")}
    data = {
        "target_account_id": "1",
        "default_currency": "USD",
        "custom_instructions": "Flag any non-NVDA as miscellaneous"
    }

    # 1. Upload CSV document
    res = await app_client.post("/api/v1/import/upload", files=files, data=data)
    assert res.status_code == 201
    batch_data = res.json()
    batch_id = batch_data["batch_id"]
    assert batch_data["total_records"] == 1
    assert batch_data["new_records"] == 1

    # 2. List batches
    batches_res = await app_client.get("/api/v1/import/batches")
    assert batches_res.status_code == 200
    assert len(batches_res.json()) >= 1

    # 3. List staged records
    records_res = await app_client.get(f"/api/v1/import/batches/{batch_id}/records")
    assert records_res.status_code == 200
    records = records_res.json()
    assert len(records) == 1
    staged_id = records[0]["staged_id"]
    assert records[0]["asset_symbol"] == "NVDA"
    assert records[0]["match_status"] == "new"
    assert records[0]["review_status"] == "approved"

    # 4. Modify staged record (Inline edit test)
    edit_res = await app_client.patch(
        f"/api/v1/import/batches/{batch_id}/records/{staged_id}",
        json={"notes": "Reviewed and confirmed by user", "fees": 3.5}
    )
    assert edit_res.status_code == 200
    assert edit_res.json()["notes"] == "Reviewed and confirmed by user"
    assert edit_res.json()["fees"] == 3.5

    # 5. Add a manual staged record
    add_res = await app_client.post(
        f"/api/v1/import/batches/{batch_id}/records",
        json={
            "record_type": "investment",
            "transaction_date": "2025-06-02",
            "action_type": "buy",
            "account_id": 1,
            "asset_symbol_raw": "AMD",
            "quantity": 5.0,
            "price_per_unit": 100.0,
            "total_amount": 500.0,
            "review_status": "approved"
        }
    )
    assert add_res.status_code == 201
    assert add_res.json()["asset_symbol_raw"] == "AMD"

    # 6. Execute Final Green Flag (commit)
    commit_res = await app_client.post(f"/api/v1/import/batches/{batch_id}/commit", json={})
    assert commit_res.status_code == 200
    commit_data = commit_res.json()
    assert commit_data["committed_count"] == 2
    assert commit_data["status"] == "merged"

@pytest.mark.anyio
async def test_mcp_server_tools_direct(app_client: AsyncClient, monkeypatch):
    # Test mcp tool functions using in-memory session override
    from app.db.database import get_db
    override_gen = app.dependency_overrides[get_db]
    async def get_test_session():
        async for s in override_gen():
            return s
    
    class TestSessionContext:
        async def __aenter__(self):
            self.s = await get_test_session()
            return self.s
        async def __aexit__(self, *args):
            pass

    monkeypatch.setattr("app.mcp.server.AsyncSessionLocal", lambda: TestSessionContext())

    context = await get_ledger_context()
    assert "accounts" in context
    assert "categories" in context
    assert "assets" in context

    # Test search existing transactions
    txs = await search_existing_transactions()
    assert isinstance(txs, list)

