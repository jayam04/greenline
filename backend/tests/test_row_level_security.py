import datetime
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import select

from app.main import app
from app.db.database import Base, get_db
from app.api.deps import get_current_user
from app.db.models import User, Account, Asset, Transaction, Category, CashflowTransaction, CashflowPayment, CashflowItem


@pytest.mark.anyio
async def test_row_level_security_isolation():
    """Verify that User A and User B cannot view or edit each other's records."""
    test_engine = create_async_engine("oracle+oracledb://greenline_test:test_password@localhost:1521/?service_name=FREEPDB1", echo=False)
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    TestSession = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)

    # 1. Create User 0 (legacy/default user) and User 1 (new user)
    async with TestSession() as session:
        user0 = User(user_id=0, username="user0", password_hash="hash0")
        user1 = User(user_id=1, username="user1", password_hash="hash1")
        session.add_all([user0, user1])
        await session.commit()

        # Shared asset
        asset = Asset(symbol="AAPL", name="Apple Inc.", asset_type="stock", currency="USD")
        session.add(asset)
        await session.commit()
        await session.refresh(asset)

    async def override_get_db():
        async with TestSession() as s:
            yield s

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Step A: Authenticate as User 0 and create Account A
        async def auth_user0():
            return user0
        app.dependency_overrides[get_current_user] = auth_user0

        res_acc0 = await ac.post("/api/v1/accounts", json={
            "account_name": "User 0 Demat",
            "account_type": "demat",
            "currency": "USD"
        })
        assert res_acc0.status_code == 201
        acc0_id = res_acc0.json()["account_id"]

        # User 0 creates a buy transaction
        res_tx0 = await ac.post("/api/v1/transactions", json={
            "account_id": acc0_id,
            "asset_id": asset.asset_id,
            "transaction_type": "buy",
            "transaction_date": "2026-10-01",
            "quantity": 10.0,
            "price_per_unit": 150.0,
            "total_amount": 1500.0
        })
        assert res_tx0.status_code == 201
        tx0_id = res_tx0.json()["transaction_id"]

        # Step B: Authenticate as User 1
        async def auth_user1():
            return user1
        app.dependency_overrides[get_current_user] = auth_user1

        # User 1 should see NO accounts in list
        res_list1 = await ac.get("/api/v1/accounts")
        assert res_list1.status_code == 200
        assert len(res_list1.json()) == 0

        # User 1 should get 404 when querying User 0's account directly
        res_get_acc0 = await ac.get(f"/api/v1/accounts/{acc0_id}")
        assert res_get_acc0.status_code == 404

        # User 1 should get 404 when trying to update User 0's account
        res_put_acc0 = await ac.put(f"/api/v1/accounts/{acc0_id}", json={
            "account_name": "Hacked Account"
        })
        assert res_put_acc0.status_code == 404

        # User 1 should get 404 when trying to delete User 0's account
        res_del_acc0 = await ac.delete(f"/api/v1/accounts/{acc0_id}")
        assert res_del_acc0.status_code == 404

        # User 1 should see NO transactions in list
        res_tx_list1 = await ac.get("/api/v1/transactions")
        assert res_tx_list1.status_code == 200
        assert len(res_tx_list1.json()) == 0

        # User 1 should get 404 when querying User 0's transaction directly
        res_get_tx0 = await ac.get(f"/api/v1/transactions/{tx0_id}")
        assert res_get_tx0.status_code == 404

        # User 1 should NOT be able to attach a new transaction to User 0's account
        res_cross_tx = await ac.post("/api/v1/transactions", json={
            "account_id": acc0_id,
            "asset_id": asset.asset_id,
            "transaction_type": "buy",
            "transaction_date": "2026-10-02",
            "quantity": 5.0,
            "price_per_unit": 150.0,
            "total_amount": 750.0
        })
        assert res_cross_tx.status_code in (400, 403, 404)

        # Step C: User 1 creates their own account
        res_acc1 = await ac.post("/api/v1/accounts", json={
            "account_name": "User 1 Demat",
            "account_type": "demat",
            "currency": "USD"
        })
        assert res_acc1.status_code == 201
        acc1_id = res_acc1.json()["account_id"]

        # User 1 sees ONLY their account
        res_list1_updated = await ac.get("/api/v1/accounts")
        assert res_list1_updated.status_code == 200
        accounts1 = res_list1_updated.json()
        assert len(accounts1) == 1
        assert accounts1[0]["account_id"] == acc1_id

        # Switch back to User 0; verify User 0 sees ONLY User 0's account
        app.dependency_overrides[get_current_user] = auth_user0
        res_list0 = await ac.get("/api/v1/accounts")
        assert res_list0.status_code == 200
        accounts0 = res_list0.json()
        assert len(accounts0) == 1
        assert accounts0[0]["account_id"] == acc0_id

        app.dependency_overrides.clear()


@pytest.mark.anyio
async def test_legacy_data_user_id_zero_default():
    """Verify that rows without an explicit user_id default to user_id = 0."""
    test_engine = create_async_engine("oracle+oracledb://greenline_test:test_password@localhost:1521/?service_name=FREEPDB1", echo=False)
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    TestSession = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)

    async with TestSession() as session:
        acc = Account(account_name="Legacy Account", account_type="bank", currency="USD")
        session.add(acc)
        await session.commit()
        await session.refresh(acc)
        assert acc.user_id == 0


@pytest.mark.anyio
async def test_cashflow_and_category_rls_isolation():
    """Verify that Cashflow transactions, custom categories, and settings are isolated per user, while system categories remain visible."""
    test_engine = create_async_engine("oracle+oracledb://greenline_test:test_password@localhost:1521/?service_name=FREEPDB1", echo=False)
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    TestSession = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)

    async with TestSession() as session:
        u0 = User(user_id=0, username="u0", password_hash="h0")
        u1 = User(user_id=1, username="u1", password_hash="h1")
        # Global system category (user_id = 0)
        sys_cat = Category(user_id=0, name="System Food", category_type="EXPENSE")
        session.add_all([u0, u1, sys_cat])
        await session.commit()

    async def override_get_db():
        async with TestSession() as s:
            yield s

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # User 0 session
        app.dependency_overrides[get_current_user] = lambda: u0
        
        # User 0 creates bank account and custom category
        res_b0 = await ac.post("/api/v1/accounts", json={"account_name": "U0 Bank", "account_type": "bank", "currency": "EUR"})
        b0_id = res_b0.json()["account_id"]

        res_c0 = await ac.post("/api/v1/categories", json={"name": "U0 Secret Category", "category_type": "EXPENSE"})
        c0_id = res_c0.json()["category_id"]

        # User 0 creates cashflow transaction
        res_cf0 = await ac.post("/api/v1/cashflow", json={
            "transaction_date": "2026-10-26",
            "title": "U0 Grocery",
            "transaction_kind": "EXPENSE",
            "currency": "EUR",
            "payments": [{"account_id": b0_id, "amount": -50.0}],
            "items": [{"category_id": c0_id, "amount": 50.0}]
        })
        assert res_cf0.status_code == 201
        cf0_id = res_cf0.json()["cashflow_id"]

        # User 1 session
        app.dependency_overrides[get_current_user] = lambda: u1

        # User 1 creates their own bank account
        res_b1 = await ac.post("/api/v1/accounts", json={"account_name": "U1 Bank", "account_type": "bank", "currency": "EUR"})
        b1_id = res_b1.json()["account_id"]

        # User 1 creates custom category
        res_c1 = await ac.post("/api/v1/categories", json={"name": "U1 Secret Category", "category_type": "EXPENSE"})
        assert res_c1.status_code == 201

        # User 0 session
        app.dependency_overrides[get_current_user] = lambda: u0
        cats_res = await ac.get("/api/v1/categories")
        cat_names = [c["name"] for c in cats_res.json()]
        assert "System Food" in cat_names
        assert "U1 Secret Category" not in cat_names

        # Switch back to User 1
        app.dependency_overrides[get_current_user] = lambda: u1

        # User 1 trying to view U0 cashflow transaction -> 404
        cf_get = await ac.get(f"/api/v1/cashflow/{cf0_id}")
        assert cf_get.status_code == 404

        # User 1 trying to list cashflow -> empty list
        cf_list = await ac.get("/api/v1/cashflow")
        assert len(cf_list.json()) == 0

        # User 1 trying to create cashflow with U0's account -> 404/400
        cf_illegal = await ac.post("/api/v1/cashflow", json={
            "transaction_date": "2026-10-26",
            "title": "Cross Account Spend",
            "transaction_kind": "EXPENSE",
            "currency": "EUR",
            "payments": [{"account_id": b0_id, "amount": -10.0}],
            "items": [{"category_id": sys_cat.category_id, "amount": 10.0}]
        })
        assert cf_illegal.status_code in (400, 404)

        app.dependency_overrides.clear()
