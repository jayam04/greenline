import datetime
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import select

from app.db.models import Base, User, Account, Category, CashflowTransaction, CashflowPayment, CashflowItem, ApiKey
from app.db.database import get_db
from app.main import app
from app.services.auth_service import get_password_hash

@pytest.fixture
async def mcp_test_env():
    test_engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    TestSession = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_db():
        async with TestSession() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    # Seed User, Account, Category
    test_user = User(user_id=1, username="mcp_user", password_hash=get_password_hash("password123"))
    splitwise_acc = Account(account_id=1, account_name="Splitwise", account_type="wallet", currency="EUR")
    groceries_cat = Category(category_id=1, name="Groceries", category_type="EXPENSE", default_label="ESSENTIAL")
    salary_cat = Category(category_id=2, name="Salary", category_type="INCOME", default_label="INVESTMENT")

    async with TestSession() as session:
        session.add_all([test_user, splitwise_acc, groceries_cat, salary_cat])
        await session.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client, TestSession, test_user

    app.dependency_overrides.clear()
    await test_engine.dispose()

@pytest.mark.anyio
async def test_api_key_crud_and_multi_auth(mcp_test_env):
    client, session_factory, user = mcp_test_env

    # 1. Login to get JWT for initial web session
    login_res = await client.post("/api/v1/auth/login", data={"username": "mcp_user", "password": "password123"})
    assert login_res.status_code == 200, login_res.text
    jwt_token = login_res.json()["access_token"]
    jwt_headers = {"Authorization": f"Bearer {jwt_token}"}

    # 2. Create API key via /api/v1/auth/api-keys
    create_res = await client.post("/api/v1/auth/api-keys", headers=jwt_headers, json={"name": "ChatGPT Agent"})
    assert create_res.status_code == 201, create_res.text
    key_data = create_res.json()
    assert key_data["name"] == "ChatGPT Agent"
    raw_key = key_data["key"]
    assert raw_key.startswith("gl_mcp_")
    key_id = key_data["key_id"]

    # 3. List API keys
    list_res = await client.get("/api/v1/auth/api-keys", headers=jwt_headers)
    assert list_res.status_code == 200
    keys = list_res.json()
    assert len(keys) == 1
    assert keys[0]["key_id"] == key_id
    assert keys[0]["key_prefix"].startswith("gl_mcp_")
    assert "key" not in keys[0] # Raw key never returned in list

    # 4. Authenticate using X-API-Key header
    cat_res_x = await client.get("/api/v1/mcp/categories", headers={"X-API-Key": raw_key})
    assert cat_res_x.status_code == 200, cat_res_x.text
    cat_json = cat_res_x.json()
    assert "categories" in cat_json
    assert any(c["name"] == "Groceries" for c in cat_json["categories"])
    assert "available_accounts" in cat_json
    assert any(a["account_name"] == "Splitwise" for a in cat_json["available_accounts"])

    # 5. Authenticate using Authorization: Bearer gl_mcp_...
    cat_res_bearer = await client.get("/api/v1/mcp/categories", headers={"Authorization": f"Bearer {raw_key}"})
    assert cat_res_bearer.status_code == 200

    # 6. Revoke API key
    del_res = await client.delete(f"/api/v1/auth/api-keys/{key_id}", headers=jwt_headers)
    assert del_res.status_code == 204

    # 7. Access with revoked key should fail 401
    fail_res = await client.get("/api/v1/mcp/categories", headers={"X-API-Key": raw_key})
    assert fail_res.status_code == 401

@pytest.mark.anyio
async def test_mcp_cashflow_mutate_validation_and_double_entry(mcp_test_env):
    client, session_factory, user = mcp_test_env

    # Login and create API key
    login_res = await client.post("/api/v1/auth/login", data={"username": "mcp_user", "password": "password123"})
    jwt_token = login_res.json()["access_token"]
    key_res = await client.post("/api/v1/auth/api-keys", headers={"Authorization": f"Bearer {jwt_token}"}, json={"name": "MCP"})
    api_key = key_res.json()["key"]
    auth_headers = {"X-API-Key": api_key}

    # 1. Success: Single expense with strict category_id=1 and strict account_name="Splitwise"
    valid_payload = {
        "operations": [
            {
                "action": "create",
                "date": "2026-09-10",
                "merchant": "Tesco",
                "notes": "1x Milk",
                "payments": [{"account_name": "Splitwise", "amount": -0.58}],
                "items": [{"category_id": 1, "amount": -0.58, "description": "1x Milk"}]
            }
        ]
    }
    res = await client.post("/api/v1/mcp/cashflow", headers=auth_headers, json=valid_payload)
    assert res.status_code == 200, res.text
    resp_data = res.json()
    assert len(resp_data["results"]) == 1
    created = resp_data["results"][0]
    assert created["merchant"] == "Tesco"
    assert created["total_amount"] == -0.58
    assert created["transaction_kind"] == "EXPENSE"
    cashflow_id = created["cashflow_id"]

    # 2. Reject if category_id does not exist
    bad_cat_payload = {
        "operations": [
            {
                "action": "create",
                "merchant": "Tesco",
                "payments": [{"account_name": "Splitwise", "amount": -1.00}],
                "items": [{"category_id": 9999, "amount": -1.00}]
            }
        ]
    }
    res_bad_cat = await client.post("/api/v1/mcp/cashflow", headers=auth_headers, json=bad_cat_payload)
    assert res_bad_cat.status_code == 400
    assert "category_id" in res_bad_cat.json()["detail"].lower()

    # 3. Reject if account_name does not strictly match
    bad_acc_payload = {
        "operations": [
            {
                "action": "create",
                "merchant": "Tesco",
                "payments": [{"account_name": "ImaginaryBank", "amount": -1.00}],
                "items": [{"category_id": 1, "amount": -1.00}]
            }
        ]
    }
    res_bad_acc = await client.post("/api/v1/mcp/cashflow", headers=auth_headers, json=bad_acc_payload)
    assert res_bad_acc.status_code == 400
    assert "account" in res_bad_acc.json()["detail"].lower()

    # 4. Reject if double-entry sum doesn't balance (payments != items)
    mismatch_payload = {
        "operations": [
            {
                "action": "create",
                "merchant": "Tesco",
                "payments": [{"account_name": "Splitwise", "amount": -10.00}],
                "items": [{"category_id": 1, "amount": -8.00}]
            }
        ]
    }
    res_mismatch = await client.post("/api/v1/mcp/cashflow", headers=auth_headers, json=mismatch_payload)
    assert res_mismatch.status_code == 400
    assert "balance" in res_mismatch.json()["detail"].lower()

    # 5. Reject generic merchant name
    generic_payload = {
        "operations": [
            {
                "action": "create",
                "merchant": "Expense",
                "payments": [{"account_name": "Splitwise", "amount": -2.00}],
                "items": [{"category_id": 1, "amount": -2.00}]
            }
        ]
    }
    res_generic = await client.post("/api/v1/mcp/cashflow", headers=auth_headers, json=generic_payload)
    assert res_generic.status_code == 400
    assert "merchant" in res_generic.json()["detail"].lower()

    # 6. Read statements with filters (month, bank_account, category)
    read_res = await client.get("/api/v1/mcp/cashflow?month=2026-09&bank_account=Splitwise", headers=auth_headers)
    assert read_res.status_code == 200, read_res.text
    statements = read_res.json()["statements"]
    assert len(statements) >= 1
    assert statements[0]["merchant"] == "Tesco"
    assert statements[0]["total_amount"] == -0.58

    # 7. Bulk Update and Delete
    update_del_payload = {
        "operations": [
            {
                "action": "update",
                "cashflow_id": cashflow_id,
                "merchant": "Tesco Express",
                "payments": [{"account_name": "Splitwise", "amount": -0.60}],
                "items": [{"category_id": 1, "amount": -0.60, "description": "1x Organic Milk"}]
            },
            {
                "action": "delete",
                "cashflow_id": 99999
            }
        ]
    }
    res_update = await client.post("/api/v1/mcp/cashflow", headers=auth_headers, json=update_del_payload)
    assert res_update.status_code == 200
    assert res_update.json()["results"][0]["merchant"] == "Tesco Express"
    assert res_update.json()["results"][0]["total_amount"] == -0.60
