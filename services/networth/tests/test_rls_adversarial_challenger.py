import time
import asyncio
from typing import Dict, Any, Optional
import pytest
from httpx import AsyncClient, ASGITransport
from jose import jwt
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.config import settings
from app.api.deps import get_db, get_current_user
from app.db.models import User, Account, Asset, Transaction, Category, CashflowTransaction
from tests.conftest import TEST_PRIVATE_PEM, TEST_KEY_ID

from tests.test_e2e_auth0_rls import make_auth0_token as mint_token, mock_auth0_network


@pytest.fixture
async def raw_client(test_db_session):
    _, session_maker = test_db_session

    async def override_get_db():
        async with session_maker() as s:
            yield s

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides.pop(get_current_user, None)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest.fixture
async def shared_asset(test_db_session) -> Asset:
    _, session_maker = test_db_session
    async with session_maker() as s:
        stmt = select(Asset).where(Asset.symbol == "AAPL")
        res = await s.execute(stmt)
        asset = res.scalar_one_or_none()
        if not asset:
            asset = Asset(symbol="AAPL", name="Apple Inc.", asset_type="stock", currency="USD")
            s.add(asset)
            await s.commit()
            await s.refresh(asset)
        return asset


# ==============================================================================
# 1. IDOR ATTACK PROBES (User A attempts CRUD on User B's resources)
# ==============================================================================

class TestAdversarialIDOR:

    @pytest.mark.anyio
    async def test_idor_account_crud(self, raw_client: AsyncClient):
        """User A attempts to read, update, or delete User B's account."""
        alice_token = mint_token(sub="auth0|idor-alice", email="alice_idor@test.com")
        bob_token = mint_token(sub="auth0|idor-bob", email="bob_idor@test.com")

        # Bob creates a bank account
        res_bob = await raw_client.post(
            "/api/v1/accounts",
            headers={"Authorization": f"Bearer {bob_token}"},
            json={"account_name": "Bob Vault", "account_type": "bank", "currency": "USD"}
        )
        assert res_bob.status_code == 201
        bob_acc_id = res_bob.json()["account_id"]

        # Alice attempts to READ Bob's account -> Must return 404
        res_read = await raw_client.get(
            f"/api/v1/accounts/{bob_acc_id}",
            headers={"Authorization": f"Bearer {alice_token}"}
        )
        assert res_read.status_code == 404, f"IDOR READ breach: status {res_read.status_code}"

        # Alice attempts to UPDATE Bob's account -> Must return 404
        res_update = await raw_client.put(
            f"/api/v1/accounts/{bob_acc_id}",
            headers={"Authorization": f"Bearer {alice_token}"},
            json={"account_name": "Hacked Vault"}
        )
        assert res_update.status_code == 404, f"IDOR UPDATE breach: status {res_update.status_code}"

        # Alice attempts to DELETE Bob's account -> Must return 404
        res_del = await raw_client.delete(
            f"/api/v1/accounts/{bob_acc_id}",
            headers={"Authorization": f"Bearer {alice_token}"}
        )
        assert res_del.status_code == 404, f"IDOR DELETE breach: status {res_del.status_code}"

    @pytest.mark.anyio
    async def test_idor_transaction_crud(self, raw_client: AsyncClient, shared_asset: Asset):
        """User A attempts to read, update, or delete User B's transactions."""
        alice_token = mint_token(sub="auth0|idor-alice-tx", email="alice_tx_idor@test.com")
        bob_token = mint_token(sub="auth0|idor-bob-tx", email="bob_tx_idor@test.com")

        # Bob creates demat account & transaction
        res_bob_acc = await raw_client.post(
            "/api/v1/accounts",
            headers={"Authorization": f"Bearer {bob_token}"},
            json={"account_name": "Bob Brokerage", "account_type": "demat", "currency": "USD"}
        )
        assert res_bob_acc.status_code == 201
        bob_acc_id = res_bob_acc.json()["account_id"]

        res_bob_tx = await raw_client.post(
            "/api/v1/transactions",
            headers={"Authorization": f"Bearer {bob_token}"},
            json={
                "account_id": bob_acc_id,
                "asset_id": shared_asset.asset_id,
                "transaction_type": "buy",
                "transaction_date": "2026-10-10",
                "quantity": 5.0,
                "price_per_unit": 100.0,
                "total_amount": 500.0,
            }
        )
        assert res_bob_tx.status_code == 201
        bob_tx_id = res_bob_tx.json()["transaction_id"]

        # Alice attempts to READ Bob's transaction -> Must return 404
        res_read = await raw_client.get(
            f"/api/v1/transactions/{bob_tx_id}",
            headers={"Authorization": f"Bearer {alice_token}"}
        )
        assert res_read.status_code == 404, f"IDOR TX READ breach: status {res_read.status_code}"

        # Alice attempts to UPDATE Bob's transaction -> Must return 404
        res_update = await raw_client.put(
            f"/api/v1/transactions/{bob_tx_id}",
            headers={"Authorization": f"Bearer {alice_token}"},
            json={"quantity": 999.0}
        )
        assert res_update.status_code == 404, f"IDOR TX UPDATE breach: status {res_update.status_code}"

        # Alice attempts to DELETE Bob's transaction -> Must return 404
        res_del = await raw_client.delete(
            f"/api/v1/transactions/{bob_tx_id}",
            headers={"Authorization": f"Bearer {alice_token}"}
        )
        assert res_del.status_code == 404, f"IDOR TX DELETE breach: status {res_del.status_code}"

    @pytest.mark.anyio
    async def test_idor_cashflow_crud(self, raw_client: AsyncClient):
        """User A attempts to read, update, or delete User B's cashflow items."""
        alice_token = mint_token(sub="auth0|idor-alice-cf", email="alice_cf_idor@test.com")
        bob_token = mint_token(sub="auth0|idor-bob-cf", email="bob_cf_idor@test.com")

        # Bob creates account, category, and cashflow
        res_bob_acc = await raw_client.post(
            "/api/v1/accounts",
            headers={"Authorization": f"Bearer {bob_token}"},
            json={"account_name": "Bob Bank", "account_type": "bank", "currency": "EUR"}
        )
        bob_acc_id = res_bob_acc.json()["account_id"]

        res_bob_cat = await raw_client.post(
            "/api/v1/categories",
            headers={"Authorization": f"Bearer {bob_token}"},
            json={"name": "Bob Subscriptions", "category_type": "EXPENSE"}
        )
        bob_cat_id = res_bob_cat.json()["category_id"]

        res_bob_cf = await raw_client.post(
            "/api/v1/cashflow",
            headers={"Authorization": f"Bearer {bob_token}"},
            json={
                "transaction_date": "2026-10-15",
                "title": "Bob VPN Sub",
                "transaction_kind": "EXPENSE",
                "currency": "EUR",
                "payments": [{"account_id": bob_acc_id, "amount": -10.0}],
                "items": [{"category_id": bob_cat_id, "amount": 10.0}],
            }
        )
        assert res_bob_cf.status_code == 201
        bob_cf_id = res_bob_cf.json()["cashflow_id"]

        # Alice attempts to READ Bob's cashflow -> 404
        res_read = await raw_client.get(
            f"/api/v1/cashflow/{bob_cf_id}",
            headers={"Authorization": f"Bearer {alice_token}"}
        )
        assert res_read.status_code == 404, f"IDOR CF READ breach: status {res_read.status_code}"

        # Alice attempts to UPDATE Bob's cashflow -> 404
        res_update = await raw_client.put(
            f"/api/v1/cashflow/{bob_cf_id}",
            headers={"Authorization": f"Bearer {alice_token}"},
            json={"title": "Hacked Title"}
        )
        assert res_update.status_code == 404, f"IDOR CF UPDATE breach: status {res_update.status_code}"

        # Alice attempts to DELETE Bob's cashflow -> 404
        res_del = await raw_client.delete(
            f"/api/v1/cashflow/{bob_cf_id}",
            headers={"Authorization": f"Bearer {alice_token}"}
        )
        assert res_del.status_code == 404, f"IDOR CF DELETE breach: status {res_del.status_code}"


# ==============================================================================
# 2. CROSS-TENANT RESOURCE LINKING ATTACKS
# ==============================================================================

class TestAdversarialCrossTenantLinking:

    @pytest.mark.anyio
    async def test_link_tx_to_victim_account_rejected(self, raw_client: AsyncClient, shared_asset: Asset):
        """User A attempts to create a transaction referencing User B's account."""
        alice_token = mint_token(sub="auth0|link-alice-1", email="alice_link1@test.com")
        bob_token = mint_token(sub="auth0|link-bob-1", email="bob_link1@test.com")

        # Bob creates demat account
        res_bob_acc = await raw_client.post(
            "/api/v1/accounts",
            headers={"Authorization": f"Bearer {bob_token}"},
            json={"account_name": "Bob Target Acc", "account_type": "demat", "currency": "USD"}
        )
        bob_acc_id = res_bob_acc.json()["account_id"]

        # Alice attempts to create transaction referencing Bob's account
        res_attack = await raw_client.post(
            "/api/v1/transactions",
            headers={"Authorization": f"Bearer {alice_token}"},
            json={
                "account_id": bob_acc_id,
                "asset_id": shared_asset.asset_id,
                "transaction_type": "buy",
                "transaction_date": "2026-10-12",
                "quantity": 10.0,
                "price_per_unit": 50.0,
                "total_amount": 500.0,
            }
        )
        assert res_attack.status_code in (400, 404), (
            f"Cross-tenant account link accepted! Status: {res_attack.status_code}, Body: {res_attack.text}"
        )

    @pytest.mark.anyio
    async def test_link_tx_funding_account_to_victim_rejected(self, raw_client: AsyncClient, shared_asset: Asset):
        """User A attempts to buy shares with User B's bank account as funding account."""
        alice_token = mint_token(sub="auth0|link-alice-2", email="alice_link2@test.com")
        bob_token = mint_token(sub="auth0|link-bob-2", email="bob_link2@test.com")

        # Alice demat account
        res_alice_acc = await raw_client.post(
            "/api/v1/accounts",
            headers={"Authorization": f"Bearer {alice_token}"},
            json={"account_name": "Alice Broker", "account_type": "demat", "currency": "USD"}
        )
        alice_acc_id = res_alice_acc.json()["account_id"]

        # Bob bank account
        res_bob_bank = await raw_client.post(
            "/api/v1/accounts",
            headers={"Authorization": f"Bearer {bob_token}"},
            json={"account_name": "Bob Savings", "account_type": "bank", "currency": "USD"}
        )
        bob_bank_id = res_bob_bank.json()["account_id"]

        # Alice attempts to fund her trade with Bob's bank
        res_attack = await raw_client.post(
            "/api/v1/transactions",
            headers={"Authorization": f"Bearer {alice_token}"},
            json={
                "account_id": alice_acc_id,
                "funding_account_id": bob_bank_id,
                "asset_id": shared_asset.asset_id,
                "transaction_type": "buy",
                "transaction_date": "2026-10-12",
                "quantity": 2.0,
                "price_per_unit": 100.0,
                "total_amount": 200.0,
            }
        )
        assert res_attack.status_code in (400, 404), (
            f"Cross-tenant funding account link accepted! Status: {res_attack.status_code}"
        )

    @pytest.mark.anyio
    async def test_link_account_default_dividend_to_victim_rejected(self, raw_client: AsyncClient):
        """User A attempts to set their default dividend account to User B's bank account."""
        alice_token = mint_token(sub="auth0|link-alice-3", email="alice_link3@test.com")
        bob_token = mint_token(sub="auth0|link-bob-3", email="bob_link3@test.com")

        res_bob_bank = await raw_client.post(
            "/api/v1/accounts",
            headers={"Authorization": f"Bearer {bob_token}"},
            json={"account_name": "Bob Bank", "account_type": "bank", "currency": "USD"}
        )
        bob_bank_id = res_bob_bank.json()["account_id"]

        res_attack = await raw_client.post(
            "/api/v1/accounts",
            headers={"Authorization": f"Bearer {alice_token}"},
            json={
                "account_name": "Alice Demat",
                "account_type": "demat",
                "currency": "USD",
                "default_dividend_account_id": bob_bank_id
            }
        )
        assert res_attack.status_code == 400, (
            f"Cross-tenant default dividend account accepted! Status: {res_attack.status_code}"
        )

    @pytest.mark.anyio
    async def test_link_cashflow_payment_to_victim_account_rejected(self, raw_client: AsyncClient):
        """User A attempts to create a cashflow payment drawing money from User B's bank account."""
        alice_token = mint_token(sub="auth0|link-alice-4", email="alice_link4@test.com")
        bob_token = mint_token(sub="auth0|link-bob-4", email="bob_link4@test.com")

        res_bob_acc = await raw_client.post(
            "/api/v1/accounts",
            headers={"Authorization": f"Bearer {bob_token}"},
            json={"account_name": "Bob Checking", "account_type": "bank", "currency": "EUR"}
        )
        bob_acc_id = res_bob_acc.json()["account_id"]

        # Alice creates category
        res_alice_cat = await raw_client.post(
            "/api/v1/categories",
            headers={"Authorization": f"Bearer {alice_token}"},
            json={"name": "Alice Utilities", "category_type": "EXPENSE"}
        )
        alice_cat_id = res_alice_cat.json()["category_id"]

        # Alice tries to create cashflow drawing from Bob's account
        res_attack = await raw_client.post(
            "/api/v1/cashflow",
            headers={"Authorization": f"Bearer {alice_token}"},
            json={
                "transaction_date": "2026-10-18",
                "title": "Drain Bob's Bank",
                "transaction_kind": "EXPENSE",
                "currency": "EUR",
                "payments": [{"account_id": bob_acc_id, "amount": -100.0}],
                "items": [{"category_id": alice_cat_id, "amount": 100.0}],
            }
        )
        assert res_attack.status_code in (400, 404), (
            f"Cross-tenant cashflow payment accepted! Status: {res_attack.status_code}, Body: {res_attack.text}"
        )

    @pytest.mark.anyio
    async def test_link_cashflow_item_to_victim_category(self, raw_client: AsyncClient):
        """
        User A creates a cashflow item pointing to User B's private category.
        Tests whether cross-tenant category linking is rejected or leaks category info.
        """
        alice_token = mint_token(sub="auth0|link-alice-5", email="alice_link5@test.com")
        bob_token = mint_token(sub="auth0|link-bob-5", email="bob_link5@test.com")

        # Alice bank
        res_alice_acc = await raw_client.post(
            "/api/v1/accounts",
            headers={"Authorization": f"Bearer {alice_token}"},
            json={"account_name": "Alice Bank", "account_type": "bank", "currency": "EUR"}
        )
        alice_acc_id = res_alice_acc.json()["account_id"]

        # Bob private category
        res_bob_cat = await raw_client.post(
            "/api/v1/categories",
            headers={"Authorization": f"Bearer {bob_token}"},
            json={"name": "Bob Confidential M&A", "category_type": "EXPENSE"}
        )
        bob_cat_id = res_bob_cat.json()["category_id"]

        # Alice attempts to create cashflow item referencing Bob's private category
        res_attack = await raw_client.post(
            "/api/v1/cashflow",
            headers={"Authorization": f"Bearer {alice_token}"},
            json={
                "transaction_date": "2026-10-19",
                "title": "Probe Category",
                "transaction_kind": "EXPENSE",
                "currency": "EUR",
                "payments": [{"account_id": alice_acc_id, "amount": -50.0}],
                "items": [{"category_id": bob_cat_id, "amount": 50.0}],
            }
        )
        # Should be rejected (400 or 404) because category belongs to Bob!
        assert res_attack.status_code in (400, 404), (
            f"VULNERABILITY: User A successfully linked to User B's private category! Status: {res_attack.status_code}"
        )

        # Also verify PUT /api/v1/cashflow/{cashflow_id} rejects victim category
        res_alice_cat = await raw_client.post(
            "/api/v1/categories",
            headers={"Authorization": f"Bearer {alice_token}"},
            json={"name": "Alice Groceries", "category_type": "EXPENSE"}
        )
        alice_cat_id = res_alice_cat.json()["category_id"]

        res_valid = await raw_client.post(
            "/api/v1/cashflow",
            headers={"Authorization": f"Bearer {alice_token}"},
            json={
                "transaction_date": "2026-10-19",
                "title": "Valid Flow",
                "transaction_kind": "EXPENSE",
                "currency": "EUR",
                "payments": [{"account_id": alice_acc_id, "amount": -20.0}],
                "items": [{"category_id": alice_cat_id, "amount": 20.0}],
            }
        )
        assert res_valid.status_code == 201
        cf_id = res_valid.json()["cashflow_id"]

        # Alice attempts update linking to Bob's private category -> Must fail 400
        res_update_attack = await raw_client.put(
            f"/api/v1/cashflow/{cf_id}",
            headers={"Authorization": f"Bearer {alice_token}"},
            json={
                "payments": [{"account_id": alice_acc_id, "amount": -20.0}],
                "items": [{"category_id": bob_cat_id, "amount": 20.0}],
            }
        )
        assert res_update_attack.status_code in (400, 404), (
            f"VULNERABILITY: User A updated cashflow to link to User B's private category! Status: {res_update_attack.status_code}"
        )

    @pytest.mark.anyio
    async def test_link_discrepancy_to_victim_funding_account_rejected(self, raw_client: AsyncClient, test_db_session, shared_asset):
        """
        User A attempts to resolve a discrepancy referencing User B's bank account as funding account.
        Must strictly return HTTP 400 with 'Funding account not found or access denied'.
        """
        alice_token = mint_token(sub="auth0|link-alice-disc", email="alice_disc@test.com")
        bob_token = mint_token(sub="auth0|link-bob-disc", email="bob_disc@test.com")

        # Bob bank account
        res_bob_bank = await raw_client.post(
            "/api/v1/accounts",
            headers={"Authorization": f"Bearer {bob_token}"},
            json={"account_name": "Bob Vault Bank", "account_type": "bank", "currency": "USD"}
        )
        bob_bank_id = res_bob_bank.json()["account_id"]

        # Alice creates a demat account
        res_alice_demat = await raw_client.post(
            "/api/v1/accounts",
            headers={"Authorization": f"Bearer {alice_token}"},
            json={"account_name": "Alice Broker", "account_type": "demat", "currency": "USD"}
        )
        alice_demat_id = res_alice_demat.json()["account_id"]

        # Alice creates a dividend transaction directly in her demat
        res_tx = await raw_client.post(
            "/api/v1/transactions",
            headers={"Authorization": f"Bearer {alice_token}"},
            json={
                "account_id": alice_demat_id,
                "asset_id": shared_asset.asset_id,
                "transaction_type": "dividend",
                "transaction_date": "2026-10-20",
                "quantity": 10.0,
                "price_per_unit": 1.0,
                "total_amount": 10.0,
            }
        )
        alice_tx_id = res_tx.json()["transaction_id"]

        # Alice attempts to resolve discrepancy using Bob's bank account as funding account
        res_resolve = await raw_client.post(
            "/api/v1/discrepancies/resolve",
            headers={"Authorization": f"Bearer {alice_token}"},
            json={
                "resolutions": [
                    {
                        "transaction_id": alice_tx_id,
                        "funding_account_id": bob_bank_id,
                    }
                ]
            }
        )
        assert res_resolve.status_code == 400
        assert "funding account" in res_resolve.json()["detail"].lower()


# ==============================================================================
# 3. BACKUP EXFILTRATION & CROSS-TENANT INTEGRITY
# ==============================================================================

class TestAdversarialBackupIsolation:

    @pytest.mark.anyio
    async def test_backup_export_data_isolation(self, raw_client: AsyncClient):
        """User A requests /api/v1/backup/export. Verify zero User B records are returned."""
        alice_token = mint_token(sub="auth0|bkp-alice-1", email="alice_bkp1@test.com")
        bob_token = mint_token(sub="auth0|bkp-bob-1", email="bob_bkp1@test.com")

        # Alice creates account
        res_a = await raw_client.post(
            "/api/v1/accounts",
            headers={"Authorization": f"Bearer {alice_token}"},
            json={"account_name": "Alice Private Ledger", "account_type": "bank", "currency": "USD"}
        )
        alice_acc_id = res_a.json()["account_id"]

        # Bob creates account
        res_b = await raw_client.post(
            "/api/v1/accounts",
            headers={"Authorization": f"Bearer {bob_token}"},
            json={"account_name": "Bob Secret Swiss Bank", "account_type": "bank", "currency": "CHF"}
        )
        bob_acc_id = res_b.json()["account_id"]

        # Alice exports portfolio data
        res_export = await raw_client.get(
            "/api/v1/backup/export",
            headers={"Authorization": f"Bearer {alice_token}"}
        )
        assert res_export.status_code == 200
        export_data = res_export.json()

        acc_ids = [a["account_id"] for a in export_data.get("accounts", [])]
        acc_names = [a["account_name"] for a in export_data.get("accounts", [])]

        assert alice_acc_id in acc_ids
        assert bob_acc_id not in acc_ids, f"DATA LEAK: Bob's account ID {bob_acc_id} leaked in Alice's export!"
        assert "Bob Secret Swiss Bank" not in acc_names, "DATA LEAK: Bob's account name leaked in Alice's export!"

    @pytest.mark.anyio
    async def test_backup_create_and_download_full_dump_leak(self, raw_client: AsyncClient):
        """
        Adversarial Test: Can an ordinary tenant (User A) trigger a server-wide backup
        via /api/v1/backup/create, or download/restore/import server records?
        Must strictly return HTTP 403 Forbidden.
        """
        alice_token = mint_token(sub="auth0|bkp-alice-attacker", email="alice_attacker@test.com")
        bob_token = mint_token(sub="auth0|bkp-bob-victim", email="bob_victim@test.com")

        # Bob stores sensitive data
        res_b = await raw_client.post(
            "/api/v1/accounts",
            headers={"Authorization": f"Bearer {bob_token}"},
            json={"account_name": "Bob Ultra Confidential Offshore", "account_type": "bank", "currency": "USD"}
        )
        assert res_b.status_code == 201

        # Alice attempts to trigger server backup -> Must return 403 Forbidden
        res_create = await raw_client.post(
            "/api/v1/backup/create",
            headers={"Authorization": f"Bearer {alice_token}"},
            json={"note": "Alice Exploit Backup"}
        )
        assert res_create.status_code == 403, (
            f"VULNERABILITY: Ordinary user was permitted to create system backup! Status: {res_create.status_code}"
        )
        assert "Admin access required" in res_create.json().get("detail", "")

        # Alice attempts to download arbitrary backup file -> Must return 403 Forbidden
        res_dl = await raw_client.get(
            "/api/v1/backup/download/greenline_backup_sample.json",
            headers={"Authorization": f"Bearer {alice_token}"}
        )
        assert res_dl.status_code == 403, (
            f"VULNERABILITY: Ordinary user was permitted to download system backup! Status: {res_dl.status_code}"
        )

        # Alice attempts to list system backups -> Must return 403 Forbidden
        res_list = await raw_client.get(
            "/api/v1/backup/list",
            headers={"Authorization": f"Bearer {alice_token}"}
        )
        assert res_list.status_code == 403, (
            f"VULNERABILITY: Ordinary user was permitted to list system backups! Status: {res_list.status_code}"
        )

        # Alice attempts to restore system backup -> Must return 403 Forbidden
        res_restore = await raw_client.post(
            "/api/v1/backup/restore/sample_backup.json",
            headers={"Authorization": f"Bearer {alice_token}"}
        )
        assert res_restore.status_code == 403, (
            f"VULNERABILITY: Ordinary user was permitted to restore system backup! Status: {res_restore.status_code}"
        )

        # Alice attempts to import system backup -> Must return 403 Forbidden
        res_import = await raw_client.post(
            "/api/v1/backup/import",
            headers={"Authorization": f"Bearer {alice_token}"},
            files={"file": ("dump.json", b"{}", "application/json")}
        )
        assert res_import.status_code == 403, (
            f"VULNERABILITY: Ordinary user was permitted to import system backup! Status: {res_import.status_code}"
        )


# ==============================================================================
# 4. CONCURRENT USER PROVISIONING RACE CONDITIONS
# ==============================================================================

class TestConcurrentProvisioningRace:

    @pytest.mark.anyio
    async def test_concurrent_jit_provisioning_same_sub(self, raw_client: AsyncClient, test_db_session):
        """
        Concurrency Stress Test:
        10 simultaneous incoming HTTP requests with the exact same unprovisioned Auth0 sub.
        Verify no race condition crashes, no duplicate users, and all return 200.
        """
        race_sub = "auth0|race-concurrent-sub-999"
        race_token = mint_token(sub=race_sub, email="race_sub_999@test.com", name="Race Test")

        async def make_req():
            return await raw_client.get(
                "/api/v1/accounts",
                headers={"Authorization": f"Bearer {race_token}"}
            )

        responses = await asyncio.gather(*(make_req() for _ in range(10)), return_exceptions=True)

        for i, r in enumerate(responses):
            assert not isinstance(r, Exception), f"Request {i} raised exception: {r}"
            assert r.status_code == 200, f"Request {i} failed with status {r.status_code}: {r.text}"

        # Verify exactly 1 user record created in DB
        _, session_maker = test_db_session
        async with session_maker() as s:
            stmt = select(User).where(User.auth0_sub == race_sub)
            res = await s.execute(stmt)
            users = res.scalars().all()
            assert len(users) == 1, f"Concurrency race created {len(users)} duplicate User rows!"

    @pytest.mark.anyio
    async def test_whitespace_sub_token_rejected(self, raw_client: AsyncClient):
        """
        Adversarial Test: Token presenting whitespace-only or empty sub claim
        must be rejected with HTTP 401 Unauthorized.
        """
        for bad_sub in ["", "   ", " \t \n "]:
            bad_token = mint_token(sub=bad_sub, email="bad_sub@test.com")
            res = await raw_client.get(
                "/api/v1/accounts",
                headers={"Authorization": f"Bearer {bad_token}"}
            )
            assert res.status_code == 401, f"Expected 401 for sub='{bad_sub}', got {res.status_code}"
