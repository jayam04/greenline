import os
import shutil
import datetime
from typing import List, Dict, Optional, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.config import settings
from app.db.models import AppSetting

def get_active_db_path() -> str:
    """Returns the absolute filesystem path to the active SQLite database file."""
    data_dir = getattr(settings, "DATA_DIR", "./data")
    db_file = getattr(settings, "DATABASE_FILE", "investments.db")
    return os.path.abspath(os.path.join(data_dir, db_file))

def ensure_backup_dir() -> str:
    """Ensures the backup directory exists and returns its absolute path."""
    backup_dir = getattr(settings, "BACKUP_DIR", os.path.join(settings.DATA_DIR, "backups"))
    os.makedirs(backup_dir, exist_ok=True)
    return os.path.abspath(backup_dir)

def list_backups() -> List[Dict[str, Any]]:
    """Returns a list of all existing backup files sorted by creation date descending."""
    backup_dir = ensure_backup_dir()
    files = []
    if not os.path.exists(backup_dir):
        return []

    for fname in os.listdir(backup_dir):
        fpath = os.path.join(backup_dir, fname)
        if os.path.isfile(fpath) and (fname.endswith(".db") or fname.endswith(".json")):
            stat = os.stat(fpath)
            created_dt = datetime.datetime.fromtimestamp(stat.st_mtime)
            kind = "manual"
            if "auto" in fname:
                kind = "auto"
            elif "safety" in fname or "pre_restore" in fname:
                kind = "safety"

            files.append({
                "filename": fname,
                "filepath": fpath,
                "size_bytes": stat.st_size,
                "size_formatted": _format_file_size(stat.st_size),
                "created_at": created_dt.isoformat(),
                "kind": kind
            })

    files.sort(key=lambda x: x["created_at"], reverse=True)
    return files

def _format_file_size(num_bytes: int) -> str:
    """Formats bytes into human readable KB/MB."""
    if num_bytes < 1024:
        return f"{num_bytes} B"
    elif num_bytes < 1024 * 1024:
        return f"{round(num_bytes / 1024, 1)} KB"
    else:
        return f"{round(num_bytes / (1024 * 1024), 2)} MB"

async def get_autobackup_config(db: AsyncSession) -> Dict[str, Any]:
    """Retrieves current autobackup configuration and status from AppSetting table."""
    stmt = select(AppSetting).where(
        AppSetting.key.in_([
            "autobackup_enabled", 
            "autobackup_interval_hours", 
            "autobackup_max_copies", 
            "last_backup_timestamp"
        ])
    )
    res = await db.execute(stmt)
    settings_map = {s.key: s.value for s in res.scalars().all()}

    enabled = settings_map.get("autobackup_enabled", "true").lower() == "true"
    try:
        interval_hours = int(settings_map.get("autobackup_interval_hours", "24"))
    except Exception:
        interval_hours = 24

    try:
        max_copies = int(settings_map.get("autobackup_max_copies", "10"))
    except Exception:
        max_copies = 10

    last_ts = settings_map.get("last_backup_timestamp")

    # Compute next backup estimated timestamp
    next_due_iso = None
    is_overdue = False
    if last_ts:
        try:
            last_dt = datetime.datetime.fromisoformat(last_ts)
            next_dt = last_dt + datetime.timedelta(hours=interval_hours)
            next_due_iso = next_dt.isoformat()
            if datetime.datetime.utcnow() >= next_dt:
                is_overdue = True
        except Exception:
            is_overdue = True
    else:
        is_overdue = True

    return {
        "database_file": getattr(settings, "DATABASE_FILE", "investments.db"),
        "data_dir": getattr(settings, "DATA_DIR", "./data"),
        "active_db_path": get_active_db_path(),
        "autobackup_enabled": enabled,
        "autobackup_interval_hours": interval_hours,
        "autobackup_max_copies": max_copies,
        "last_backup_timestamp": last_ts,
        "next_backup_timestamp": next_due_iso,
        "is_overdue": is_overdue and enabled,
        "total_backups_count": len(list_backups())
    }

async def update_autobackup_config(
    db: AsyncSession, 
    enabled: Optional[bool] = None, 
    interval_hours: Optional[int] = None, 
    max_copies: Optional[int] = None
) -> Dict[str, Any]:
    """Updates auto-backup settings in the database."""
    updates = {}
    if enabled is not None:
        updates["autobackup_enabled"] = "true" if enabled else "false"
    if interval_hours is not None:
        updates["autobackup_interval_hours"] = str(max(1, interval_hours))
    if max_copies is not None:
        updates["autobackup_max_copies"] = str(max(1, max_copies))

    for key, val in updates.items():
        stmt = select(AppSetting).where(AppSetting.key == key)
        res = await db.execute(stmt)
        item = res.scalar_one_or_none()
        if item:
            item.value = val
        else:
            db.add(AppSetting(key=key, value=val))

    await db.commit()
    return await get_autobackup_config(db)

def prune_old_backups(max_copies: int = 10) -> int:
    """Removes oldest backups if total backup files count exceeds max_copies."""
    all_files = list_backups()
    if len(all_files) <= max_copies:
        return 0

    to_remove = all_files[max_copies:]
    removed_count = 0
    for f in to_remove:
        try:
            if os.path.exists(f["filepath"]):
                os.remove(f["filepath"])
                removed_count += 1
        except Exception as e:
            print(f"[Backup Pruning Error] Failed to remove {f['filepath']}: {e}")

    return removed_count

async def create_backup(
    db: AsyncSession, 
    kind: str = "manual", 
    note: Optional[str] = None, 
    max_copies: Optional[int] = None
) -> Dict[str, Any]:
    """
    Creates a new timestamped backup copy of the active database file in the backups directory.
    Prunes excess old backups and records last_backup_timestamp.
    """
    backup_dir = ensure_backup_dir()
    db_path = get_active_db_path()
    timestamp_str = datetime.datetime.utcnow().strftime("%Y-%m-%d_%H%M%S_%f")
    backup_filename = f"greenline_backup_{kind}_{timestamp_str}.db"
    dest_path = os.path.join(backup_dir, backup_filename)

    if os.path.exists(db_path):
        shutil.copy2(db_path, dest_path)
    else:
        # If DB file not yet created on disk, create placeholder
        with open(dest_path, "w") as f:
            f.write("")

    stat = os.stat(dest_path)
    now_iso = datetime.datetime.utcnow().isoformat()

    # Update last_backup_timestamp in AppSetting
    stmt = select(AppSetting).where(AppSetting.key == "last_backup_timestamp")
    res = await db.execute(stmt)
    ts_setting = res.scalar_one_or_none()
    if ts_setting:
        ts_setting.value = now_iso
    else:
        db.add(AppSetting(key="last_backup_timestamp", value=now_iso))
    await db.commit()

    # Get max copies setting if not provided
    if max_copies is None:
        cfg = await get_autobackup_config(db)
        max_copies = cfg["autobackup_max_copies"]

    prune_old_backups(max_copies=max_copies)

    return {
        "filename": backup_filename,
        "filepath": dest_path,
        "size_bytes": stat.st_size,
        "size_formatted": _format_file_size(stat.st_size),
        "created_at": now_iso,
        "kind": kind,
        "note": note
    }

async def check_and_trigger_autobackup(db: AsyncSession) -> Optional[str]:
    """
    Evaluates whether an automated backup is due based on interval settings.
    Triggers creation and returns the backup filename if executed, or None if not due.
    """
    cfg = await get_autobackup_config(db)
    if not cfg["autobackup_enabled"]:
        return None

    if cfg["is_overdue"]:
        backup_res = await create_backup(db, kind="auto", max_copies=cfg["autobackup_max_copies"])
        print(f"[AutoBackup] Automatically created snapshot: {backup_res['filename']}")
        return backup_res["filename"]

    return None

async def restore_from_backup(filename: str, db: AsyncSession) -> Dict[str, Any]:
    """
    Restores the active database from a specified backup file.
    Creates a pre-restore safety copy first before overwriting.
    """
    backup_dir = ensure_backup_dir()
    backup_path = os.path.join(backup_dir, filename)

    if not os.path.exists(backup_path):
        raise FileNotFoundError(f"Backup file '{filename}' not found in backup storage.")

    db_path = get_active_db_path()

    # Take pre-restore safety snapshot if current DB exists
    safety_filename = None
    if os.path.exists(db_path):
        ts_str = datetime.datetime.utcnow().strftime("%Y-%m-%d_%H%M%S_%f")
        safety_filename = f"greenline_pre_restore_safety_{ts_str}.db"
        safety_path = os.path.join(backup_dir, safety_filename)
        shutil.copy2(db_path, safety_path)

    # Overwrite active database file
    shutil.copy2(backup_path, db_path)

    return {
        "status": "success",
        "restored_from": filename,
        "safety_backup": safety_filename,
        "restored_at": datetime.datetime.utcnow().isoformat()
    }

def delete_backup(filename: str) -> bool:
    """Deletes a specific backup file from the backups directory."""
    backup_dir = ensure_backup_dir()
    target_path = os.path.join(backup_dir, filename)
    if os.path.exists(target_path):
        os.remove(target_path)
        return True
    return False
