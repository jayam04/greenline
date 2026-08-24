import pytest
import datetime
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import select
from app.db.database import Base, get_db
from app.db.models import User, Account, Category, CashflowTransaction, CashflowPayment, CashflowItem
from app.api.deps import get_current_user
from app.services.cashflow_engine import build_category_lineage_map
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
        yield session, SessionMaker

@pytest.fixture
async def client(test_db_session):
    session, session_maker = test_db_session
    mock_user = User(user_id=1, username="testadmin")

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

@pytest.mark.anyio
async def test_mixed_currency_preserves_normalized_eur(client):
    ac, session, _ = client

    # Create USD and EUR accounts
    usd_acc = Account(account_name="USD Checking", account_type="bank", currency="USD")
    eur_acc = Account(account_name="EUR Checking", account_type="bank", currency="EUR")
    cat = Category(name="Electronics", category_type="EXPENSE", default_label="LUXURY")
    session.add_all([usd_acc, eur_acc, cat])
    await session.commit()
    await session.refresh(usd_acc)
    await session.refresh(eur_acc)
    await session.refresh(cat)

    # Post mixed currency split: 100 USD (92 EUR) + 50 EUR -> Total in EUR = 142 EUR
    # Client sends currency="USD" in payload (which happens when client's simple currency is USD)
    payload = {
        "transaction_date": str(datetime.date.today()),
        "title": "New Laptop Split Payment",
        "total_amount": 150.0,
        "currency": "USD",
        "transaction_kind": "EXPENSE",
        "payments": [
            {"account_id": usd_acc.account_id, "amount": 100.0},
            {"account_id": eur_acc.account_id, "amount": 50.0},
        ],
        "items": [
            {"category_id": cat.category_id, "amount": 142.0, "description": "Laptop"}
        ]
    }

    resp = await ac.post("/api/v1/cashflow/", json=payload)
    assert resp.status_code == 201
    data = resp.json()

    # The persisted currency MUST be EUR (normalized)
    assert data["currency"] == "EUR"
    # Total amount in EUR: 100 * 0.92 + 50 * 1.0 = 142.0 EUR
    assert data["total_amount"] == 142.0
    assert data["master_amount_eur"] == 142.0

    # Also test PUT with mixed payments enforces EUR
    update_payload = {
        "title": "New Laptop Split Payment Updated",
        "currency": "USD", # Client sends USD again
        "payments": [
            {"account_id": usd_acc.account_id, "amount": 200.0}, # 200 * 0.92 = 184 EUR
            {"account_id": eur_acc.account_id, "amount": 100.0}, # 100 EUR
        ],
        "items": [
            {"category_id": cat.category_id, "amount": 284.0, "description": "Laptop"}
        ]
    }
    put_resp = await ac.put(f"/api/v1/cashflow/{data['cashflow_id']}", json=update_payload)
    assert put_resp.status_code == 200
    put_data = put_resp.json()
    assert put_data["currency"] == "EUR"
    assert put_data["total_amount"] == 284.0
    assert put_data["master_amount_eur"] == 284.0

@pytest.mark.anyio
async def test_category_rejects_self_parent(client):
    ac, session, _ = client
    cat = Category(name="Food", category_type="EXPENSE")
    session.add(cat)
    await session.commit()
    await session.refresh(cat)

    resp = await ac.put(f"/api/v1/categories/{cat.category_id}", json={"parent_id": cat.category_id})
    assert resp.status_code == 400
    assert "cannot be its own parent" in resp.json()["detail"].lower()

@pytest.mark.anyio
async def test_category_rejects_descendant_cycles(client):
    ac, session, _ = client
    # Hierarchy: A -> B -> C
    cat_a = Category(name="A", category_type="EXPENSE", parent_id=None)
    session.add(cat_a)
    await session.commit()
    await session.refresh(cat_a)

    cat_b = Category(name="B", category_type="EXPENSE", parent_id=cat_a.category_id)
    session.add(cat_b)
    await session.commit()
    await session.refresh(cat_b)

    cat_c = Category(name="C", category_type="EXPENSE", parent_id=cat_b.category_id)
    session.add(cat_c)
    await session.commit()
    await session.refresh(cat_c)

    # Try setting A's parent to B (immediate child)
    resp_b = await ac.put(f"/api/v1/categories/{cat_a.category_id}", json={"parent_id": cat_b.category_id})
    assert resp_b.status_code == 400
    assert "cycle" in resp_b.json()["detail"].lower()

    # Try setting A's parent to C (deep descendant)
    resp_c = await ac.put(f"/api/v1/categories/{cat_a.category_id}", json={"parent_id": cat_c.category_id})
    assert resp_c.status_code == 400
    assert "cycle" in resp_c.json()["detail"].lower()

    # Valid parent update: setting C's parent directly to A
    resp_valid = await ac.put(f"/api/v1/categories/{cat_c.category_id}", json={"parent_id": cat_a.category_id})
    assert resp_valid.status_code == 200
    assert resp_valid.json()["parent_id"] == cat_a.category_id

@pytest.mark.anyio
async def test_delete_category_blocks_when_subcategories_exist(client):
    ac, session, _ = client
    parent_cat = Category(name="Housing", category_type="EXPENSE")
    session.add(parent_cat)
    await session.commit()
    await session.refresh(parent_cat)

    child_cat = Category(name="Rent", category_type="EXPENSE", parent_id=parent_cat.category_id)
    session.add(child_cat)
    await session.commit()
    await session.refresh(child_cat)

    # Attempting to delete parent should fail with 400 because subcategories exist
    resp = await ac.delete(f"/api/v1/categories/{parent_cat.category_id}")
    assert resp.status_code == 400
    assert "subcategories" in resp.json()["detail"].lower()

    # Child should still exist in DB
    check_child = await session.execute(select(Category).where(Category.category_id == child_cat.category_id))
    assert check_child.scalar_one_or_none() is not None

    # Delete child first, then parent can be deleted successfully
    del_child_resp = await ac.delete(f"/api/v1/categories/{child_cat.category_id}")
    assert del_child_resp.status_code == 204

    del_parent_resp = await ac.delete(f"/api/v1/categories/{parent_cat.category_id}")
    assert del_parent_resp.status_code == 204

@pytest.mark.anyio
async def test_lineage_map_cycle_safety(test_db_session):
    session, _ = test_db_session
    # Force a direct cycle into DB if malformed data existed
    cat1 = Category(name="Cycle1", category_type="EXPENSE", parent_id=None)
    session.add(cat1)
    await session.commit()
    await session.refresh(cat1)

    cat2 = Category(name="Cycle2", category_type="EXPENSE", parent_id=cat1.category_id)
    session.add(cat2)
    await session.commit()
    await session.refresh(cat2)

    # Directly modify parent_id in DB to create a cycle (cat1 -> cat2 -> cat1)
    cat1.parent_id = cat2.category_id
    await session.commit()

    # build_category_lineage_map must terminate cleanly without an infinite loop
    lineage_map = await build_category_lineage_map(session)
    assert len(lineage_map) == 2
