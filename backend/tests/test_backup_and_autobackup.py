import os
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
