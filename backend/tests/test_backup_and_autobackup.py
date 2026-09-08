import os
import json
import shutil
import tempfile
import datetime
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import select
from app.main import app
from app.db.database import Base, get_db
from app.api.deps import get_current_user
from app.db.models import (
    Account, Asset, Transaction, PriceHistory, CorporateAction, 
    ExpectedDividend, Category, CashflowTransaction, CashflowPayment, 
    CashflowItem, AppSetting, User
)
from app.services.backup_service import (
    create_backup, list_backups, check_and_trigger_autobackup, 
    restore_from_backup, delete_backup
)

@pytest.fixture
def temp_backup_env(monkeypatch):
    """Creates a temporary data and backup directory for test isolation."""
    tmp_dir = tempfile.mkdtemp(prefix="greenline_test_data_")
    backup_dir = os.path.join(tmp_dir, "backups")
    os.makedirs(backup_dir, exist_ok=True)
    db_file_path = os.path.join(tmp_dir, "investments.db")

    # Create dummy sqlite database file
    with open(db_file_path, "w") as f:
        f.write("sqlite format 3 dummy header")

    import app.config
    monkeypatch.setattr(app.config.settings, "DATA_DIR", tmp_dir)
    monkeypatch.setattr(app.config.settings, "DATABASE_FILE", "investments.db")
    monkeypatch.setattr(app.config.settings, "BACKUP_DIR", backup_dir)

    yield {
        "tmp_dir": tmp_dir,
        "backup_dir": backup_dir,
        "db_file_path": db_file_path
    }

    shutil.rmtree(tmp_dir, ignore_errors=True)

@pytest.mark.anyio
async def test_backup_service_lifecycle_and_pruning(temp_backup_env):
    test_engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    TestSession = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)

    async with TestSession() as session:
        # Seed user and app settings
        user = User(username="backup_admin", password_hash="hash")
        session.add(user)
        await session.commit()
        await session.refresh(user)

        # 1. Create manual backup
        b1 = await create_backup(session, kind="manual", note="Initial manual backup")
        assert os.path.exists(b1["filepath"])
        assert b1["kind"] == "manual"
        assert b1["filename"].startswith("greenline_backup_manual_")

        # 2. List backups
        all_backups = list_backups()
        assert len(all_backups) == 1
        assert all_backups[0]["filename"] == b1["filename"]
        assert all_backups[0]["kind"] == "manual"

        # 3. Create multiple auto-backups with max_copies = 3
        b2 = await create_backup(session, kind="auto")
        b3 = await create_backup(session, kind="auto")
        b4 = await create_backup(session, kind="auto", max_copies=3)

        all_backups_after = list_backups()
        assert len(all_backups_after) == 3  # Pruned oldest to maintain max 3 copies

        # 4. Check auto-backup trigger logic
        # If last backup was just now, check_and_trigger_autobackup should return None (not due)
        not_due = await check_and_trigger_autobackup(session)
        assert not_due is None

        # Manually backdate last_backup_timestamp in AppSetting to 2 days ago
        setting_res = await session.execute(select(AppSetting).where(AppSetting.key == "last_backup_timestamp"))
        setting = setting_res.scalar_one_or_none()
        old_time = (datetime.datetime.utcnow() - datetime.timedelta(days=2)).isoformat()
        if setting:
            setting.value = old_time
        else:
            session.add(AppSetting(key="last_backup_timestamp", value=old_time))
        await session.commit()

        # Now auto-backup should trigger
        triggered = await check_and_trigger_autobackup(session)
        assert triggered is not None
        assert triggered.startswith("greenline_backup_auto_")

        # 5. Test Delete backup
        latest_backups = list_backups()
        file_to_delete = latest_backups[0]["filename"]
        deleted = delete_backup(file_to_delete)
        assert deleted is True
        assert not os.path.exists(os.path.join(temp_backup_env["backup_dir"], file_to_delete))

@pytest.mark.anyio
async def test_backup_rest_api_endpoints(temp_backup_env):
    test_engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    TestSession = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)

    async with TestSession() as session:
        user = User(username="api_backup_user", password_hash="hash")
        session.add(user)
        await session.commit()
        await session.refresh(user)

    async def override_get_db():
        async with TestSession() as s:
            yield s

    async def override_get_current_user():
        return user

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            # 1. GET /api/v1/backup/config
            res_cfg = await ac.get("/api/v1/backup/config")
            assert res_cfg.status_code == 200
            cfg_data = res_cfg.json()
            assert "database_file" in cfg_data
            assert "autobackup_enabled" in cfg_data
            assert "autobackup_interval_hours" in cfg_data
            assert "autobackup_max_copies" in cfg_data

            # 2. PUT /api/v1/backup/config
            res_update = await ac.put("/api/v1/backup/config", json={
                "autobackup_enabled": True,
                "autobackup_interval_hours": 12,
                "autobackup_max_copies": 15
            })
            assert res_update.status_code == 200
            assert res_update.json()["autobackup_interval_hours"] == 12
            assert res_update.json()["autobackup_max_copies"] == 15

            # 3. POST /api/v1/backup/create
            res_create = await ac.post("/api/v1/backup/create", json={"note": "Manual Test Snapshot"})
            assert res_create.status_code == 200
            created_file = res_create.json()["filename"]

            # 4. GET /api/v1/backup/list
            res_list = await ac.get("/api/v1/backup/list")
            assert res_list.status_code == 200
            backups = res_list.json()["backups"]
            assert len(backups) >= 1
            assert any(b["filename"] == created_file for b in backups)

            # 5. GET /api/v1/backup/download/{filename}
            res_down = await ac.get(f"/api/v1/backup/download/{created_file}")
            assert res_down.status_code == 200

            # 6. DELETE /api/v1/backup/{filename}
            res_del = await ac.delete(f"/api/v1/backup/{created_file}")
            assert res_del.status_code == 200

    finally:
        app.dependency_overrides.clear()

@pytest.mark.anyio
async def test_backup_path_traversal_and_security(temp_backup_env):
    test_engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    TestSession = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)

    async with TestSession() as session:
        user = User(username="sec_admin", password_hash="hash")
        session.add(user)
        await session.commit()
        await session.refresh(user)

    # Create an outside secret file and a symlink pointing to it inside backup_dir
    outside_secret = os.path.join(temp_backup_env["tmp_dir"], "outside_secret.txt")
    with open(outside_secret, "w") as f:
        f.write("SUPER_SECRET_TOKEN")

    symlink_path = os.path.join(temp_backup_env["backup_dir"], "symlink_escape.db")
    try:
        os.symlink(outside_secret, symlink_path)
    except OSError:
        pass

    async def override_get_db():
        async with TestSession() as s:
            yield s

    async def override_get_current_user():
        return user

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            # 1. Traversal in download
            res_t1 = await ac.get("/api/v1/backup/download/../../etc/passwd")
            assert res_t1.status_code in [400, 404]
            assert "passwd" not in res_t1.text
            assert temp_backup_env["tmp_dir"] not in res_t1.text

            # 2. Absolute path traversal attempt
            res_t2 = await ac.get("/api/v1/backup/download//etc/passwd")
            assert res_t2.status_code in [400, 404]

            # 3. Traversal in restore
            res_t3 = await ac.post("/api/v1/backup/restore/..%2F..%2Fetc%2Fpasswd")
            assert res_t3.status_code in [400, 404]

            # 4. Traversal in delete
            res_t4 = await ac.delete("/api/v1/backup/..%2F..%2Fetc%2Fpasswd")
            assert res_t4.status_code in [400, 404]

            # 5. Symlink escape attempt
            if os.path.islink(symlink_path):
                res_sym = await ac.get("/api/v1/backup/download/symlink_escape.db")
                assert res_sym.status_code in [400, 403, 404]
                assert "SUPER_SECRET_TOKEN" not in res_sym.text

            # 6. Verify error messages do not leak server filesystem paths
            res_err = await ac.get("/api/v1/backup/download/nonexistent_backup.db")
            assert res_err.status_code == 404
            assert temp_backup_env["tmp_dir"] not in res_err.text
            assert "/data" not in res_err.text or res_err.json().get("detail") == "Backup file not found."
    finally:
        app.dependency_overrides.clear()

@pytest.mark.anyio
async def test_backup_export_import_symmetry_and_id_remapping(temp_backup_env):
    test_engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    TestSession = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)

    async with TestSession() as session:
        user = User(username="export_user", password_hash="hash")
        session.add(user)
        await session.commit()
        await session.refresh(user)

        # Seed full entity set:
        bank = Account(account_name="Checking Bank", account_type="bank", currency="USD")
        session.add(bank)
        await session.flush()

        demat = Account(
            account_name="Trading Demat", 
            account_type="demat", 
            currency="USD",
            default_dividend_account_id=bank.account_id
        )
        session.add(demat)

        asset = Asset(symbol="AAPL", name="Apple Inc.", asset_type="stock", currency="USD")
        session.add(asset)
        await session.flush()

        exp_div = ExpectedDividend(
            asset_id=asset.asset_id,
            account_id=demat.account_id,
            ex_date=datetime.date(2026, 5, 1),
            eligible_shares=10.0,
            dividend_rate=1.0,
            expected_amount=10.0,
            currency="USD",
            status="MATCHED"
        )
        session.add(exp_div)
        await session.flush()

        tx = Transaction(
            account_id=demat.account_id,
            funding_account_id=bank.account_id,
            asset_id=asset.asset_id,
            transaction_type="dividend",
            transaction_date=datetime.date(2026, 5, 5),
            total_amount=10.0,
            fees=0.0,
            taxes=1.0,
            source="manual",
            expected_dividend_id=exp_div.expected_dividend_id
        )
        session.add(tx)
        await session.flush()
        exp_div.matched_transaction_id = tx.transaction_id

        parent_cat = Category(name="Living", category_type="EXPENSE", default_label="ESSENTIAL")
        session.add(parent_cat)
        await session.flush()

        child_cat = Category(name="Groceries", category_type="EXPENSE", parent_id=parent_cat.category_id, default_label="ESSENTIAL")
        session.add(child_cat)
        await session.flush()

        cf_tx = CashflowTransaction(
            transaction_date=datetime.date(2026, 5, 10),
            title="Weekly Groceries",
            total_amount=50.0,
            currency="USD",
            transaction_kind="EXPENSE"
        )
        session.add(cf_tx)
        await session.flush()

        cf_pmt = CashflowPayment(cashflow_id=cf_tx.cashflow_id, account_id=bank.account_id, amount=50.0)
        cf_item = CashflowItem(cashflow_id=cf_tx.cashflow_id, category_id=child_cat.category_id, amount=50.0)
        session.add_all([cf_pmt, cf_item])

        ph = PriceHistory(asset_id=asset.asset_id, price_date=datetime.date(2026, 5, 1), close_price=150.0, source="manual")
        ca = CorporateAction(asset_id=asset.asset_id, action_type="split", action_date=datetime.date(2026, 6, 1), ratio="2:1")
        setting = AppSetting(key="master_currency", value="USD")
        session.add_all([ph, ca, setting])

        await session.commit()

    async def override_get_db():
        async with TestSession() as s:
            yield s

    async def override_get_current_user():
        return user

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            # 1. Export data
            res_exp = await ac.get("/api/v1/backup/export")
            assert res_exp.status_code == 200
            export_payload = res_exp.json()

            assert export_payload["version"] == "2.0"
            assert len(export_payload["accounts"]) == 2
            assert len(export_payload["assets"]) == 1
            assert len(export_payload["transactions"]) == 1
            assert len(export_payload["expected_dividends"]) == 1
            assert len(export_payload["categories"]) == 2
            assert len(export_payload["cashflow_transactions"]) == 1
            assert len(export_payload["cashflow_payments"]) == 1
            assert len(export_payload["cashflow_items"]) == 1

            # 2. Modify exported primary keys to simulate restoring into a DB with different IDs
            for a in export_payload["accounts"]:
                a["account_id"] += 1000
                if a.get("default_dividend_account_id"):
                    a["default_dividend_account_id"] += 1000
            for ast in export_payload["assets"]:
                ast["asset_id"] += 1000
            for t in export_payload["transactions"]:
                t["transaction_id"] += 1000
                t["account_id"] += 1000
                if t.get("funding_account_id"):
                    t["funding_account_id"] += 1000
                if t.get("asset_id"):
                    t["asset_id"] += 1000
                if t.get("expected_dividend_id"):
                    t["expected_dividend_id"] += 1000
            for ed in export_payload["expected_dividends"]:
                ed["expected_dividend_id"] += 1000
                ed["asset_id"] += 1000
                ed["account_id"] += 1000
                if ed.get("matched_transaction_id"):
                    ed["matched_transaction_id"] += 1000
            for c in export_payload["categories"]:
                c["category_id"] += 1000
                if c.get("parent_id"):
                    c["parent_id"] += 1000
            for ct in export_payload["cashflow_transactions"]:
                ct["cashflow_id"] += 1000
            for cp in export_payload["cashflow_payments"]:
                cp["payment_id"] += 1000
                cp["cashflow_id"] += 1000
                cp["account_id"] += 1000
            for ci in export_payload["cashflow_items"]:
                ci["item_id"] += 1000
                ci["cashflow_id"] += 1000
                ci["category_id"] += 1000
            for ph_item in export_payload["price_history"]:
                ph_item["price_id"] += 1000
                ph_item["asset_id"] += 1000
            for ca_item in export_payload["corporate_actions"]:
                ca_item["action_id"] += 1000
                ca_item["asset_id"] += 1000

            # 3. Import via POST /api/v1/backup/import
            import_json_bytes = json.dumps(export_payload).encode("utf-8")
            res_imp = await ac.post(
                "/api/v1/backup/import",
                files={"file": ("backup.json", import_json_bytes, "application/json")}
            )
            assert res_imp.status_code == 200

            # 4. Verify relationships are correctly remapped in DB
            async with TestSession() as session:
                accs = (await session.execute(select(Account).order_by(Account.account_name))).scalars().all()
                assert len(accs) == 2
                chk_bank = next(a for a in accs if a.account_name == "Checking Bank")
                tr_demat = next(a for a in accs if a.account_name == "Trading Demat")
                # Demat default dividend account must point to new bank account ID
                assert tr_demat.default_dividend_account_id == chk_bank.account_id

                cats = (await session.execute(select(Category).order_by(Category.name))).scalars().all()
                assert len(cats) == 2
                living_cat = next(c for c in cats if c.name == "Living")
                groc_cat = next(c for c in cats if c.name == "Groceries")
                # Child category parent_id must point to new parent category ID
                assert groc_cat.parent_id == living_cat.category_id

                txs = (await session.execute(select(Transaction))).scalars().all()
                assert len(txs) == 1
                restored_tx = txs[0]
                assert restored_tx.funding_account_id == chk_bank.account_id
                assert restored_tx.account_id == tr_demat.account_id

                exp_divs = (await session.execute(select(ExpectedDividend))).scalars().all()
                assert len(exp_divs) == 1
                restored_exp = exp_divs[0]
                assert restored_exp.matched_transaction_id == restored_tx.transaction_id
                assert restored_tx.expected_dividend_id == restored_exp.expected_dividend_id

                cf_pmts = (await session.execute(select(CashflowPayment))).scalars().all()
                assert len(cf_pmts) == 1
                assert cf_pmts[0].account_id == chk_bank.account_id

                cf_items = (await session.execute(select(CashflowItem))).scalars().all()
                assert len(cf_items) == 1
                assert cf_items[0].category_id == groc_cat.category_id

    finally:
        app.dependency_overrides.clear()

@pytest.mark.anyio
async def test_backup_validation_and_atomic_rollback(temp_backup_env):
    test_engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    TestSession = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)

    async with TestSession() as session:
        user = User(username="val_user", password_hash="hash")
        session.add(user)
        # Seed an account that must NOT be deleted if validation fails
        acc = Account(account_name="Protected Account", account_type="bank", currency="USD")
        session.add(acc)
        await session.commit()
        await session.refresh(acc)
        initial_acc_id = acc.account_id

    async def override_get_db():
        async with TestSession() as s:
            yield s

    async def override_get_current_user():
        return user

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            # 1. Reject unsupported version
            bad_ver_payload = json.dumps({"version": "99.0", "accounts": [], "transactions": []}).encode("utf-8")
            res_v = await ac.post("/api/v1/backup/import", files={"file": ("bad_ver.json", bad_ver_payload, "application/json")})
            assert res_v.status_code == 400
            assert "Unsupported backup version" in res_v.json()["detail"]

            # 2. Reject missing transactions
            bad_keys_payload = json.dumps({"version": "2.0", "accounts": []}).encode("utf-8")
            res_k = await ac.post("/api/v1/backup/import", files={"file": ("bad_keys.json", bad_keys_payload, "application/json")})
            assert res_k.status_code == 400

            # 3. Reject broken foreign key reference in backup (e.g. transaction points to missing account)
            bad_fk_payload = json.dumps({
                "version": "2.0",
                "accounts": [{"account_id": 1, "account_name": "Acc 1", "account_type": "bank", "currency": "USD"}],
                "transactions": [{
                    "transaction_id": 10,
                    "account_id": 9999,  # Missing!
                    "transaction_type": "deposit",
                    "transaction_date": "2026-01-01",
                    "total_amount": 100.0
                }]
            }).encode("utf-8")
            res_fk = await ac.post("/api/v1/backup/import", files={"file": ("bad_fk.json", bad_fk_payload, "application/json")})
            assert res_fk.status_code == 400
            assert "foreign key" in res_fk.json()["detail"].lower() or "missing" in res_fk.json()["detail"].lower()

            # 4. Verify existing database rows were untouched by atomic rollback
            async with TestSession() as session:
                existing_acc = await session.get(Account, initial_acc_id)
                assert existing_acc is not None
                assert existing_acc.account_name == "Protected Account"
    finally:
        app.dependency_overrides.clear()

@pytest.mark.anyio
async def test_sqlite_file_restore_atomic_and_safety_backup(temp_backup_env):
    import sqlite3
    db_path = temp_backup_env["db_file_path"]
    backup_dir = temp_backup_env["backup_dir"]

    if os.path.exists(db_path):
        os.remove(db_path)

    # 1. Initialize active DB with valid SQLite table and data
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE test_table (id INT PRIMARY KEY, val TEXT);")
    conn.execute("INSERT INTO test_table VALUES (1, 'active_initial');")
    conn.commit()
    conn.close()

    # 2. Create backup SQLite file with different data
    backup_fname = "greenline_backup_manual_restore_source.db"
    backup_fpath = os.path.join(backup_dir, backup_fname)
    b_conn = sqlite3.connect(backup_fpath)
    b_conn.execute("CREATE TABLE test_table (id INT PRIMARY KEY, val TEXT);")
    b_conn.execute("INSERT INTO test_table VALUES (2, 'restored_data');")
    b_conn.commit()
    b_conn.close()

    test_engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with test_engine.begin() as conn_async:
        await conn_async.run_sync(Base.metadata.create_all)
    TestSession = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)

    async with TestSession() as session:
        user = User(username="sqlite_restore_user", password_hash="hash")
        session.add(user)
        await session.commit()
        await session.refresh(user)

    async def override_get_db():
        async with TestSession() as s:
            yield s

    async def override_get_current_user():
        return user

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            res = await ac.post(f"/api/v1/backup/restore/{backup_fname}")
            assert res.status_code == 200
            data = res.json()
            assert data["status"] == "success"
            assert data["restored_from"] == backup_fname
            safety_file = data.get("safety_backup")
            assert safety_file is not None
            assert safety_file.startswith("greenline_pre_restore_safety_")

            # Verify active DB has replaced data
            chk_conn = sqlite3.connect(db_path)
            rows = chk_conn.execute("SELECT id, val FROM test_table").fetchall()
            chk_conn.close()
            assert len(rows) == 1
            assert rows[0] == (2, "restored_data")

            # Verify safety backup file has active_initial data
            safety_full_path = os.path.join(backup_dir, safety_file)
            assert os.path.exists(safety_full_path)
            s_conn = sqlite3.connect(safety_full_path)
            s_rows = s_conn.execute("SELECT id, val FROM test_table").fetchall()
            s_conn.close()
            assert len(s_rows) == 1
            assert s_rows[0] == (1, "active_initial")
    finally:
        app.dependency_overrides.clear()

@pytest.mark.anyio
async def test_sqlite_restore_corrupted_file_rejection(temp_backup_env):
    backup_dir = temp_backup_env["backup_dir"]
    corrupt_fname = "greenline_backup_corrupted.db"
    corrupt_path = os.path.join(backup_dir, corrupt_fname)
    # Write invalid data that has sqlite header but corrupt sqlite structures
    with open(corrupt_path, "wb") as f:
        f.write(b"SQLite format 3\x00INVALID_HEADER_DATA_CORRUPTED_BLOCK")

    test_engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with test_engine.begin() as conn_async:
        await conn_async.run_sync(Base.metadata.create_all)
    TestSession = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)

    async with TestSession() as session:
        user = User(username="corrupt_restore_user", password_hash="hash")
        session.add(user)
        await session.commit()
        await session.refresh(user)

    async def override_get_db():
        async with TestSession() as s:
            yield s

    async def override_get_current_user():
        return user

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            res = await ac.post(f"/api/v1/backup/restore/{corrupt_fname}")
            assert res.status_code in [400, 500]
    finally:
        app.dependency_overrides.clear()

@pytest.mark.anyio
async def test_retention_pruning_preserves_safety_backups(temp_backup_env):
    from app.services.backup_service import prune_old_backups
    backup_dir = temp_backup_env["backup_dir"]

    # Create 3 routine backups and 2 safety backups
    for i in range(3):
        fpath = os.path.join(backup_dir, f"greenline_backup_manual_2026-01-0{i+1}_000000.db")
        with open(fpath, "w") as f:
            f.write("dummy")

    for i in range(2):
        fpath = os.path.join(backup_dir, f"greenline_pre_restore_safety_2026-01-0{i+1}_000000.db")
        with open(fpath, "w") as f:
            f.write("safety")

    # Prune with max_copies = 1
    removed = prune_old_backups(max_copies=1)
    assert removed == 2  # 2 manual backups pruned

    remaining = os.listdir(backup_dir)
    # Both safety backups MUST still exist
    assert any("pre_restore_safety_2026-01-01" in fname for fname in remaining)
    assert any("pre_restore_safety_2026-01-02" in fname for fname in remaining)
    # Exactly 1 manual backup remaining
    manual_remaining = [f for f in remaining if "manual" in f]
    assert len(manual_remaining) == 1

@pytest.mark.anyio
async def test_scheduler_reschedule_job():
    from app.scheduler import scheduler, reschedule_autobackup_job

    # Schedule with 12 hours
    reschedule_autobackup_job(interval_hours=12, enabled=True)
    job = scheduler.get_job("autobackup_job")
    assert job is not None
    assert job.id == "autobackup_job"

    # Reschedule with 6 hours - duplicate prevention
    reschedule_autobackup_job(interval_hours=6, enabled=True)
    all_jobs = [j for j in scheduler.get_jobs() if j.id == "autobackup_job"]
    assert len(all_jobs) == 1

    # Disable job
    reschedule_autobackup_job(enabled=False)

