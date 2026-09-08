import os
import re
import json
import shutil
import sqlite3
import datetime
import asyncio
from typing import List, Dict, Optional, Any, Set
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, update
from app.config import settings
from app.db.models import (
    Account, Asset, Transaction, PriceHistory, CorporateAction, 
    ExpectedDividend, Category, CashflowTransaction, CashflowPayment, 
    CashflowItem, AppSetting, Dividend, Lot, LotSale, NetworthSnapshot, 
    NetworthByAssetClass, CashFlow, XIRRCache, Benchmark
)
from app.services.fifo_engine import recalculate_all_lots
from app.services.price_engine import update_prices_for_assets
from app.services.snapshot_engine import recalculate_past_snapshots

FILENAME_REGEX = re.compile(r"^[a-zA-Z0-9_\-\.]+\.(db|json)$")
_backup_lock = asyncio.Lock()

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

def validate_and_resolve_backup_path(filename: str, must_exist: bool = True) -> str:
    """
    Validates that filename is a safe relative filename without traversal (..),
    absolute paths, or symlink escapes, and resolves its path inside BACKUP_DIR.
    Raises ValueError on invalid filenames or traversal attempts.
    Raises FileNotFoundError if must_exist is True and file is missing.
    """
    if not filename or not isinstance(filename, str):
        raise ValueError("Invalid backup filename.")

    # Reject null bytes, path separators, traversal dots, and non-matching filenames
    if (
        "\0" in filename
        or ".." in filename
        or "/" in filename
        or "\\" in filename
        or filename.startswith(".")
        or not FILENAME_REGEX.match(filename)
    ):
        raise ValueError("Invalid backup filename.")

    backup_dir = ensure_backup_dir()
    real_backup_dir = os.path.realpath(backup_dir)
    candidate_path = os.path.join(real_backup_dir, filename)

    # Disallow symlinks completely to prevent symlink escape attacks
    if os.path.islink(candidate_path):
        raise ValueError("Invalid backup filename: symlinks are not permitted.")

    real_candidate_path = os.path.realpath(candidate_path)

    # Verify candidate path stays strictly inside backup directory
    try:
        common = os.path.commonpath([real_backup_dir, real_candidate_path])
        if common != real_backup_dir:
            raise ValueError("Invalid backup filename.")
    except Exception:
        raise ValueError("Invalid backup filename.")

    if must_exist:
        if not os.path.exists(candidate_path) or not os.path.isfile(candidate_path):
            raise FileNotFoundError("Backup file not found.")

    return candidate_path

def _format_file_size(num_bytes: int) -> str:
    """Formats bytes into human readable KB/MB."""
    if num_bytes < 1024:
        return f"{num_bytes} B"
    elif num_bytes < 1024 * 1024:
        return f"{round(num_bytes / 1024, 1)} KB"
    else:
        return f"{round(num_bytes / (1024 * 1024), 2)} MB"

def list_backups() -> List[Dict[str, Any]]:
    """Returns a list of all existing backup files sorted by creation date descending."""
    backup_dir = ensure_backup_dir()
    files = []
    if not os.path.exists(backup_dir):
        return []

    for fname in os.listdir(backup_dir):
        if fname.startswith("."):
            continue
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

def prune_old_backups(max_copies: int = 10, exclude_filename: Optional[str] = None) -> int:
    """
    Removes oldest routine backups (manual or auto) if total count exceeds max_copies.
    Safety snapshots and the newest backup (exclude_filename) are preserved.
    """
    max_copies = max(1, max_copies)
    all_files = list_backups()

    prunable = [
        f for f in all_files 
        if f["kind"] in ("manual", "auto") and f["filename"] != exclude_filename
    ]

    target_count = max_copies - 1 if exclude_filename else max_copies
    target_count = max(0, target_count)

    if len(prunable) <= target_count:
        return 0

    to_remove = prunable[target_count:]
    removed_count = 0
    for f in to_remove:
        try:
            if os.path.exists(f["filepath"]) and not os.path.islink(f["filepath"]):
                os.remove(f["filepath"])
                removed_count += 1
        except Exception as e:
            print(f"[Backup Pruning Error] Failed to remove backup: {e}")

    return removed_count

async def create_backup(
    db: AsyncSession, 
    kind: str = "manual", 
    note: Optional[str] = None, 
    max_copies: Optional[int] = None
) -> Dict[str, Any]:
    """
    Creates a new timestamped backup copy of the active database file in the backups directory.
    Uses atomic temp writes and prunes excess old backups.
    """
    async with _backup_lock:
        backup_dir = ensure_backup_dir()
        db_path = get_active_db_path()
        timestamp_str = datetime.datetime.utcnow().strftime("%Y-%m-%d_%H%M%S_%f")
        backup_filename = f"greenline_backup_{kind}_{timestamp_str}.db"
        dest_path = os.path.join(backup_dir, backup_filename)
        temp_dest = os.path.join(backup_dir, f".tmp_{timestamp_str}_{backup_filename}")

        if os.path.exists(db_path):
            shutil.copy2(db_path, temp_dest)
            os.replace(temp_dest, dest_path)
        else:
            with open(temp_dest, "w") as f:
                f.write("")
            os.replace(temp_dest, dest_path)

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

        if max_copies is None:
            cfg = await get_autobackup_config(db)
            max_copies = cfg["autobackup_max_copies"]

        prune_old_backups(max_copies=max_copies, exclude_filename=backup_filename)

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

def _parse_iso_date(date_str: Any, field_name: str) -> datetime.date:
    """Parses and validates ISO date string."""
    if not isinstance(date_str, str) or not date_str.strip():
        raise ValueError(f"Invalid date format for {field_name}: '{date_str}'. Must be ISO format (YYYY-MM-DD).")
    try:
        clean = date_str.strip()
        if "T" in clean:
            return datetime.datetime.fromisoformat(clean.replace("Z", "+00:00")).date()
        return datetime.date.fromisoformat(clean[:10])
    except Exception:
        raise ValueError(f"Invalid date format for {field_name}: '{date_str}'. Must be ISO format (YYYY-MM-DD).")

def _parse_optional_iso_date(date_str: Any, field_name: str) -> Optional[datetime.date]:
    """Parses optional ISO date string or returns None."""
    if date_str is None or date_str == "":
        return None
    return _parse_iso_date(date_str, field_name)

def _parse_float(val: Any, field_name: str, allow_none: bool = False) -> Optional[float]:
    """Parses and validates a numeric float."""
    if val is None:
        if allow_none:
            return None
        raise ValueError(f"Invalid numeric value for {field_name}: None.")
    try:
        return float(val)
    except (ValueError, TypeError):
        raise ValueError(f"Invalid numeric value for {field_name}: '{val}'.")

def validate_backup_payload(data: dict) -> None:
    """
    Pre-destruction validation for JSON backup payloads.
    Enforces schema versioning, structure integrity, date formats, and referential constraints.
    Raises ValueError before any database mutations occur.
    """
    if not isinstance(data, dict):
        raise ValueError("Backup payload must be a JSON object.")

    version = str(data.get("version", "1.0"))
    if version not in ("1.0", "2.0"):
        raise ValueError(f"Unsupported backup version '{version}'. Supported versions: 1.0, 2.0")

    if "accounts" not in data or not isinstance(data["accounts"], list):
        raise ValueError("Invalid portfolio backup format. Missing 'accounts' collection.")
    if "transactions" not in data or not isinstance(data["transactions"], list):
        raise ValueError("Invalid portfolio backup format. Missing 'transactions' collection.")

    collections = [
        ("accounts", "account_id", "Account"),
        ("assets", "asset_id", "Asset"),
        ("transactions", "transaction_id", "Transaction"),
        ("expected_dividends", "expected_dividend_id", "Expected Dividend"),
        ("categories", "category_id", "Category"),
        ("cashflow_transactions", "cashflow_id", "Cashflow Transaction"),
        ("cashflow_payments", "payment_id", "Cashflow Payment"),
        ("cashflow_items", "item_id", "Cashflow Item"),
        ("price_history", "price_id", "Price History"),
        ("corporate_actions", "action_id", "Corporate Action"),
    ]

    for coll_name, id_key, entity_label in collections:
        seen_ids = set()
        for item in data.get(coll_name, []):
            if not isinstance(item, dict):
                raise ValueError(f"Invalid record in {coll_name}: expected object.")
            item_id = item.get(id_key)
            if item_id is not None:
                if item_id in seen_ids:
                    raise ValueError(f"Duplicate {entity_label} ID {item_id} found in backup.")
                seen_ids.add(item_id)

    # Validate accounts
    for acc in data.get("accounts", []):
        if not acc.get("account_name"):
            raise ValueError("Invalid account: missing account_name.")
        if not acc.get("account_type"):
            raise ValueError("Invalid account: missing account_type.")
        if "created_at" in acc and acc["created_at"]:
            _parse_optional_iso_date(acc["created_at"], "account.created_at")

    # Validate assets
    for ast in data.get("assets", []):
        if not ast.get("symbol"):
            raise ValueError("Invalid asset: missing symbol.")
        if not ast.get("name"):
            raise ValueError("Invalid asset: missing name.")
        if not ast.get("asset_type"):
            raise ValueError("Invalid asset: missing asset_type.")

    # Validate transactions
    for tx in data.get("transactions", []):
        if not tx.get("transaction_type"):
            raise ValueError("Invalid transaction: missing transaction_type.")
        _parse_iso_date(tx.get("transaction_date"), "transaction.transaction_date")
        _parse_float(tx.get("total_amount"), "transaction.total_amount")
        if tx.get("quantity") is not None:
            _parse_float(tx.get("quantity"), "transaction.quantity")
        if tx.get("price_per_unit") is not None:
            _parse_float(tx.get("price_per_unit"), "transaction.price_per_unit")
        if tx.get("fees") is not None:
            _parse_float(tx.get("fees"), "transaction.fees")
        if tx.get("taxes") is not None:
            _parse_float(tx.get("taxes"), "transaction.taxes")

    # Validate categories
    for cat in data.get("categories", []):
        if not cat.get("name"):
            raise ValueError("Invalid category: missing name.")

    # Validate expected dividends
    for ed in data.get("expected_dividends", []):
        if ed.get("ex_date"):
            _parse_iso_date(ed.get("ex_date"), "expected_dividend.ex_date")
        if ed.get("pay_date"):
            _parse_optional_iso_date(ed.get("pay_date"), "expected_dividend.pay_date")
        if ed.get("expected_amount") is not None:
            _parse_float(ed.get("expected_amount"), "expected_dividend.expected_amount")

    # Validate cashflows
    for ct in data.get("cashflow_transactions", []):
        if not ct.get("title"):
            raise ValueError("Invalid cashflow transaction: missing title.")
        _parse_iso_date(ct.get("transaction_date"), "cashflow_transaction.transaction_date")
        _parse_float(ct.get("total_amount"), "cashflow_transaction.total_amount")

    for cp in data.get("cashflow_payments", []):
        _parse_float(cp.get("amount"), "cashflow_payment.amount")

    for ci in data.get("cashflow_items", []):
        _parse_float(ci.get("amount"), "cashflow_item.amount")

    # Validate price history
    for ph in data.get("price_history", []):
        _parse_iso_date(ph.get("price_date"), "price_history.price_date")
        _parse_float(ph.get("close_price"), "price_history.close_price")

    # Validate corporate actions
    for ca in data.get("corporate_actions", []):
        _parse_iso_date(ca.get("action_date"), "corporate_action.action_date")
        if not ca.get("action_type"):
            raise ValueError("Invalid corporate action: missing action_type.")

    # Referential integrity checks
    account_ids = {a["account_id"] for a in data.get("accounts", []) if "account_id" in a}
    asset_ids = {a["asset_id"] for a in data.get("assets", []) if "asset_id" in a}
    category_ids = {c["category_id"] for c in data.get("categories", []) if "category_id" in c}
    cashflow_ids = {ct["cashflow_id"] for ct in data.get("cashflow_transactions", []) if "cashflow_id" in ct}
    expected_div_ids = {ed["expected_dividend_id"] for ed in data.get("expected_dividends", []) if "expected_dividend_id" in ed}
    transaction_ids = {t["transaction_id"] for t in data.get("transactions", []) if "transaction_id" in t}

    for acc in data.get("accounts", []):
        def_div = acc.get("default_dividend_account_id")
        if def_div is not None and def_div not in account_ids:
            raise ValueError(f"Invalid foreign key: Account {acc.get('account_id')} refers to missing default_dividend_account_id {def_div}")

    for cat in data.get("categories", []):
        pid = cat.get("parent_id")
        if pid is not None and pid not in category_ids:
            raise ValueError(f"Invalid foreign key: Category {cat.get('category_id')} refers to missing parent_id {pid}")

    for tx in data.get("transactions", []):
        tx_id = tx.get("transaction_id", "?")
        acc_id = tx.get("account_id")
        if acc_id not in account_ids:
            raise ValueError(f"Invalid foreign key: Transaction {tx_id} refers to missing account_id {acc_id}")
        funding_id = tx.get("funding_account_id")
        if funding_id is not None and funding_id not in account_ids:
            raise ValueError(f"Invalid foreign key: Transaction {tx_id} refers to missing funding_account_id {funding_id}")
        ast_id = tx.get("asset_id")
        if ast_id is not None and ast_id not in asset_ids:
            raise ValueError(f"Invalid foreign key: Transaction {tx_id} refers to missing asset_id {ast_id}")
        ed_id = tx.get("expected_dividend_id")
        if ed_id is not None and ed_id not in expected_div_ids:
            raise ValueError(f"Invalid foreign key: Transaction {tx_id} refers to missing expected_dividend_id {ed_id}")

    for ed in data.get("expected_dividends", []):
        ed_id = ed.get("expected_dividend_id", "?")
        acc_id = ed.get("account_id")
        if acc_id not in account_ids:
            raise ValueError(f"Invalid foreign key: ExpectedDividend {ed_id} refers to missing account_id {acc_id}")
        ast_id = ed.get("asset_id")
        if ast_id not in asset_ids:
            raise ValueError(f"Invalid foreign key: ExpectedDividend {ed_id} refers to missing asset_id {ast_id}")
        matched_tx = ed.get("matched_transaction_id")
        if matched_tx is not None and matched_tx not in transaction_ids:
            raise ValueError(f"Invalid foreign key: ExpectedDividend {ed_id} refers to missing matched_transaction_id {matched_tx}")

    for cp in data.get("cashflow_payments", []):
        cp_id = cp.get("payment_id", "?")
        cf_id = cp.get("cashflow_id")
        if cf_id not in cashflow_ids:
            raise ValueError(f"Invalid foreign key: CashflowPayment {cp_id} refers to missing cashflow_id {cf_id}")
        acc_id = cp.get("account_id")
        if acc_id not in account_ids:
            raise ValueError(f"Invalid foreign key: CashflowPayment {cp_id} refers to missing account_id {acc_id}")

    for ci in data.get("cashflow_items", []):
        ci_id = ci.get("item_id", "?")
        cf_id = ci.get("cashflow_id")
        if cf_id not in cashflow_ids:
            raise ValueError(f"Invalid foreign key: CashflowItem {ci_id} refers to missing cashflow_id {cf_id}")
        cat_id = ci.get("category_id")
        if cat_id not in category_ids:
            raise ValueError(f"Invalid foreign key: CashflowItem {ci_id} refers to missing category_id {cat_id}")

    for ph in data.get("price_history", []):
        ast_id = ph.get("asset_id")
        if ast_id not in asset_ids:
            raise ValueError(f"Invalid foreign key: PriceHistory refers to missing asset_id {ast_id}")

    for ca in data.get("corporate_actions", []):
        ast_id = ca.get("asset_id")
        if ast_id not in asset_ids:
            raise ValueError(f"Invalid foreign key: CorporateAction refers to missing asset_id {ast_id}")

async def restore_from_json_data(data: dict, db: AsyncSession) -> Dict[str, Any]:
    """
    Restores complete portfolio data from a JSON structure.
    Pre-validates all records before touching the database, creates a pre-restore safety copy,
    performs atomic deletion/insertion with full ID remapping across all 11 entities,
    and recalculates FIFO lots and historical snapshots.
    """
    validate_backup_payload(data)

    async with _backup_lock:
        db_path = get_active_db_path()
        backup_dir = ensure_backup_dir()

        # Take pre-restore safety backup if active DB file exists on disk
        safety_filename = None
        if os.path.exists(db_path) and os.path.getsize(db_path) > 0:
            ts_str = datetime.datetime.utcnow().strftime("%Y-%m-%d_%H%M%S_%f")
            safety_filename = f"greenline_pre_restore_safety_{ts_str}.db"
            safety_path = os.path.join(backup_dir, safety_filename)
            temp_safety = os.path.join(backup_dir, f".tmp_safety_{ts_str}.db")
            try:
                shutil.copy2(db_path, temp_safety)
                os.replace(temp_safety, safety_path)
            except Exception as e:
                print(f"[Backup] Warning: Could not create pre-restore safety backup: {e}")

        account_map: Dict[int, int] = {}
        asset_map: Dict[int, int] = {}
        category_map: Dict[int, int] = {}
        cashflow_map: Dict[int, int] = {}
        exp_div_map: Dict[int, int] = {}
        tx_map: Dict[int, int] = {}
        earliest_tx_date: Optional[datetime.date] = None

        try:
            # 1. Clear existing transactional & master data in dependency order
            try:
                await db.execute(update(ExpectedDividend).values(matched_transaction_id=None))
                await db.execute(update(Transaction).values(expected_dividend_id=None, funding_account_id=None))
                await db.execute(update(Account).values(default_dividend_account_id=None))
                await db.execute(update(Category).values(parent_id=None))
                await db.flush()
            except Exception:
                pass

            await db.execute(delete(CashflowItem))
            await db.execute(delete(CashflowPayment))
            await db.execute(delete(CashflowTransaction))
            await db.execute(delete(NetworthByAssetClass))
            await db.execute(delete(NetworthSnapshot))
            await db.execute(delete(CashFlow))
            await db.execute(delete(XIRRCache))
            await db.execute(delete(Benchmark))
            await db.execute(delete(LotSale))
            await db.execute(delete(Lot))
            await db.execute(delete(Dividend))
            await db.execute(delete(ExpectedDividend))
            await db.execute(delete(Transaction))
            await db.execute(delete(CorporateAction))
            await db.execute(delete(PriceHistory))
            await db.execute(delete(Category))
            await db.execute(delete(Account))
            await db.execute(delete(Asset))
            await db.flush()

            # 2. Insert Accounts (without self-referential FK initially)
            acc_tuples = []
            for acc in data.get("accounts", []):
                c_date = _parse_optional_iso_date(acc.get("created_at"), "account.created_at") or datetime.date.today()
                new_acc = Account(
                    account_name=acc["account_name"],
                    broker_name=acc.get("broker_name"),
                    account_type=acc["account_type"],
                    currency=acc.get("currency", "USD"),
                    default_dividend_account_id=None,
                    created_at=c_date
                )
                db.add(new_acc)
                acc_tuples.append((new_acc, acc))
            await db.flush()
            for new_acc, acc in acc_tuples:
                account_map[acc["account_id"]] = new_acc.account_id

            for new_acc, acc in acc_tuples:
                old_div_id = acc.get("default_dividend_account_id")
                if old_div_id and old_div_id in account_map:
                    new_acc.default_dividend_account_id = account_map[old_div_id]
            await db.flush()

            # 3. Insert Assets
            ast_tuples = []
            for ast in data.get("assets", []):
                new_ast = Asset(
                    symbol=ast["symbol"].upper().strip(),
                    isin=ast.get("isin"),
                    name=ast["name"],
                    asset_type=ast["asset_type"],
                    exchange=ast.get("exchange"),
                    sector=ast.get("sector"),
                    industry=ast.get("industry"),
                    currency=ast.get("currency", "USD")
                )
                db.add(new_ast)
                ast_tuples.append((new_ast, ast))
            await db.flush()
            for new_ast, ast in ast_tuples:
                asset_map[ast["asset_id"]] = new_ast.asset_id

            # 4. Insert Categories (without self-referential parent_id initially)
            cat_tuples = []
            for cat in data.get("categories", []):
                new_cat = Category(
                    name=cat["name"],
                    category_type=cat.get("category_type", "EXPENSE"),
                    default_label=cat.get("default_label"),
                    parent_id=None,
                    icon=cat.get("icon"),
                    color=cat.get("color")
                )
                db.add(new_cat)
                cat_tuples.append((new_cat, cat))
            await db.flush()
            for new_cat, cat in cat_tuples:
                category_map[cat["category_id"]] = new_cat.category_id

            for new_cat, cat in cat_tuples:
                old_pid = cat.get("parent_id")
                if old_pid and old_pid in category_map:
                    new_cat.parent_id = category_map[old_pid]
            await db.flush()

            # 5. Insert Corporate Actions
            for ca in data.get("corporate_actions", []):
                mapped_ast_id = asset_map.get(ca["asset_id"])
                if mapped_ast_id:
                    ca_date = _parse_iso_date(ca["action_date"], "corporate_action.action_date")
                    db.add(CorporateAction(
                        asset_id=mapped_ast_id,
                        action_type=ca["action_type"],
                        action_date=ca_date,
                        ratio=ca.get("ratio", "1:1"),
                        notes=ca.get("notes")
                    ))

            # 6. Insert Price History
            for ph in data.get("price_history", []):
                mapped_ast_id = asset_map.get(ph["asset_id"])
                if mapped_ast_id:
                    p_date = _parse_iso_date(ph["price_date"], "price_history.price_date")
                    db.add(PriceHistory(
                        asset_id=mapped_ast_id,
                        price_date=p_date,
                        close_price=float(ph["close_price"]),
                        source=ph.get("source", "manual")
                    ))

            # 7. Insert Expected Dividends (without mutual matched_transaction_id initially)
            ed_tuples = []
            for ed in data.get("expected_dividends", []):
                mapped_ast_id = asset_map.get(ed["asset_id"])
                mapped_acc_id = account_map.get(ed["account_id"])
                if mapped_ast_id and mapped_acc_id:
                    ex_dt = _parse_iso_date(ed["ex_date"], "expected_dividend.ex_date")
                    pay_dt = _parse_optional_iso_date(ed.get("pay_date"), "expected_dividend.pay_date")
                    new_ed = ExpectedDividend(
                        asset_id=mapped_ast_id,
                        account_id=mapped_acc_id,
                        ex_date=ex_dt,
                        pay_date=pay_dt,
                        eligible_shares=float(ed.get("eligible_shares", 0.0)),
                        dividend_rate=float(ed.get("dividend_rate", 0.0)),
                        expected_amount=float(ed.get("expected_amount", 0.0)),
                        currency=ed.get("currency", "USD"),
                        source=ed.get("source", "manual"),
                        matched_transaction_id=None,
                        status=ed.get("status", "UNMATCHED")
                    )
                    db.add(new_ed)
                    ed_tuples.append((new_ed, ed))
            await db.flush()
            for new_ed, ed in ed_tuples:
                exp_div_map[ed["expected_dividend_id"]] = new_ed.expected_dividend_id

            # 8. Insert Transactions
            tx_tuples = []
            for tx in data.get("transactions", []):
                mapped_acc_id = account_map.get(tx["account_id"])
                mapped_funding_id = account_map.get(tx.get("funding_account_id")) if tx.get("funding_account_id") else None
                mapped_ast_id = asset_map.get(tx.get("asset_id")) if tx.get("asset_id") else None
                mapped_ed_id = exp_div_map.get(tx.get("expected_dividend_id")) if tx.get("expected_dividend_id") else None

                t_date = _parse_iso_date(tx["transaction_date"], "transaction.transaction_date")
                if earliest_tx_date is None or t_date < earliest_tx_date:
                    earliest_tx_date = t_date

                new_tx = Transaction(
                    account_id=mapped_acc_id,
                    funding_account_id=mapped_funding_id,
                    asset_id=mapped_ast_id,
                    transaction_type=tx["transaction_type"],
                    transaction_date=t_date,
                    quantity=float(tx["quantity"]) if tx.get("quantity") is not None else None,
                    price_per_unit=float(tx["price_per_unit"]) if tx.get("price_per_unit") is not None else None,
                    total_amount=float(tx["total_amount"]),
                    fees=float(tx.get("fees", 0.0)),
                    taxes=float(tx.get("taxes", 0.0)),
                    source=tx.get("source", "manual"),
                    notes=tx.get("notes"),
                    expected_dividend_id=mapped_ed_id
                )
                db.add(new_tx)
                tx_tuples.append((new_tx, tx))
            await db.flush()
            for new_tx, tx in tx_tuples:
                tx_map[tx["transaction_id"]] = new_tx.transaction_id

            # Remap ExpectedDividend.matched_transaction_id to newly inserted transaction ID
            for new_ed, ed in ed_tuples:
                old_matched_tx = ed.get("matched_transaction_id")
                if old_matched_tx and old_matched_tx in tx_map:
                    new_ed.matched_transaction_id = tx_map[old_matched_tx]
            await db.flush()

            # 9. Insert Cashflow Transactions
            cf_tuples = []
            for ct in data.get("cashflow_transactions", []):
                ct_date = _parse_iso_date(ct["transaction_date"], "cashflow_transaction.transaction_date")
                new_ct = CashflowTransaction(
                    transaction_date=ct_date,
                    title=ct["title"],
                    total_amount=float(ct["total_amount"]),
                    currency=ct.get("currency", "EUR"),
                    transaction_kind=ct.get("transaction_kind"),
                    notes=ct.get("notes")
                )
                db.add(new_ct)
                cf_tuples.append((new_ct, ct))
            await db.flush()
            for new_ct, ct in cf_tuples:
                cashflow_map[ct["cashflow_id"]] = new_ct.cashflow_id

            # 10. Insert Cashflow Payments and Items
            for cp in data.get("cashflow_payments", []):
                mapped_cf_id = cashflow_map.get(cp["cashflow_id"])
                mapped_acc_id = account_map.get(cp["account_id"])
                if mapped_cf_id and mapped_acc_id:
                    db.add(CashflowPayment(
                        cashflow_id=mapped_cf_id,
                        account_id=mapped_acc_id,
                        amount=float(cp["amount"])
                    ))

            for ci in data.get("cashflow_items", []):
                mapped_cf_id = cashflow_map.get(ci["cashflow_id"])
                mapped_cat_id = category_map.get(ci["category_id"])
                if mapped_cf_id and mapped_cat_id:
                    db.add(CashflowItem(
                        cashflow_id=mapped_cf_id,
                        category_id=mapped_cat_id,
                        amount=float(ci["amount"]),
                        label=ci.get("label"),
                        description=ci.get("description")
                    ))

            # 11. Insert or update AppSettings
            for s in data.get("app_settings", []):
                stmt = select(AppSetting).where(AppSetting.key == s["key"])
                res = await db.execute(stmt)
                setting_obj = res.scalar_one_or_none()
                if setting_obj:
                    setting_obj.value = str(s["value"])
                else:
                    db.add(AppSetting(key=s["key"], value=str(s["value"])))

            # Handle v1.0 dividends if present
            for d in data.get("dividends", []):
                mapped_ast_id = asset_map.get(d["asset_id"])
                mapped_acc_id = account_map.get(d["account_id"])
                if mapped_ast_id and mapped_acc_id:
                    ex_dt = _parse_optional_iso_date(d.get("ex_date"), "dividend.ex_date")
                    pay_dt = _parse_iso_date(d["pay_date"], "dividend.pay_date")
                    db.add(Dividend(
                        asset_id=mapped_ast_id,
                        account_id=mapped_acc_id,
                        ex_date=ex_dt,
                        pay_date=pay_dt,
                        amount_per_share=float(d["amount_per_share"]) if d.get("amount_per_share") is not None else None,
                        total_amount=float(d["total_amount"]),
                        tax_withheld=float(d.get("tax_withheld", 0.0))
                    ))

            await db.commit()
        except Exception:
            await db.rollback()
            raise

        # Post-commit recalculations
        try:
            await recalculate_all_lots(db)
        except Exception as e:
            print(f"[Backup Restore] Warning: Lot recalculation failed: {e}")

        try:
            if earliest_tx_date:
                await recalculate_past_snapshots(db, start_date=earliest_tx_date)
            else:
                await recalculate_past_snapshots(db, start_date=datetime.date.today())
        except Exception as e:
            print(f"[Backup Restore] Warning: Snapshot recalculation failed: {e}")

        return {
            "message": "Portfolio backup imported successfully.",
            "imported": {
                "accounts": len(data.get("accounts", [])),
                "assets": len(data.get("assets", [])),
                "transactions": len(data.get("transactions", [])),
                "expected_dividends": len(data.get("expected_dividends", [])),
                "categories": len(data.get("categories", []))
            }
        }

async def restore_from_sqlite_file(backup_path: str, filename: str) -> Dict[str, Any]:
    """
    Restores the active database file from an existing SQLite backup file.
    Validates SQLite file integrity, performs pre-restore safety copy,
    disposes the connection pool, and executes atomic file swap.
    """
    async with _backup_lock:
        db_path = get_active_db_path()
        backup_dir = ensure_backup_dir()

        # Check SQLite integrity if file is non-empty
        if os.path.exists(backup_path) and os.path.getsize(backup_path) > 0:
            with open(backup_path, "rb") as f:
                header = f.read(16)
            if header.startswith(b"SQLite format 3\x00"):
                try:
                    conn = sqlite3.connect(backup_path)
                    res = conn.execute("PRAGMA integrity_check;").fetchall()
                    conn.close()
                    if not res or res[0][0].lower() != "ok":
                        raise ValueError("Backup database file failed integrity check.")
                except sqlite3.DatabaseError as dbe:
                    raise ValueError("Backup file is not a valid SQLite database.")

        # Create pre-restore safety snapshot
        safety_filename = None
        safety_path = None
        if os.path.exists(db_path) and os.path.getsize(db_path) > 0:
            ts_str = datetime.datetime.utcnow().strftime("%Y-%m-%d_%H%M%S_%f")
            safety_filename = f"greenline_pre_restore_safety_{ts_str}.db"
            safety_path = os.path.join(backup_dir, safety_filename)
            temp_safety = os.path.join(backup_dir, f".tmp_safety_{ts_str}.db")
            try:
                shutil.copy2(db_path, temp_safety)
                os.replace(temp_safety, safety_path)
            except Exception as e:
                print(f"[Backup] Warning: Could not create pre-restore safety backup: {e}")

        # Invalidate SQLAlchemy connection pool before replacing database file
        from app.db.database import engine
        if engine is not None:
            await engine.dispose()

        # Atomic replacement via temporary file swap
        ts_swap = datetime.datetime.utcnow().strftime("%Y-%m-%d_%H%M%S_%f")
        temp_active = f"{db_path}.tmp_restore_{ts_swap}"
        try:
            shutil.copy2(backup_path, temp_active)
            os.replace(temp_active, db_path)
        except Exception:
            if os.path.exists(temp_active):
                try:
                    os.remove(temp_active)
                except OSError:
                    pass
            # Rollback to safety copy if available
            if safety_path and os.path.exists(safety_path):
                shutil.copy2(safety_path, db_path)
            raise ValueError("Failed to replace active database file.")

        return {
            "status": "success",
            "restored_from": filename,
            "safety_backup": safety_filename,
            "restored_at": datetime.datetime.utcnow().isoformat()
        }

async def restore_from_backup(filename: str, db: AsyncSession) -> Dict[str, Any]:
    """
    Restores active database from a specified backup file (.db or .json).
    Routes to appropriate restore handler.
    """
    validated_path = validate_and_resolve_backup_path(filename, must_exist=True)

    if filename.endswith(".json"):
        with open(validated_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        import_res = await restore_from_json_data(data, db)
        return {
            "status": "success",
            "restored_from": filename,
            "restored_at": datetime.datetime.utcnow().isoformat(),
            "details": import_res
        }
    elif filename.endswith(".db"):
        return await restore_from_sqlite_file(validated_path, filename)
    else:
        raise ValueError("Unsupported backup format. Only .db and .json files are supported.")

def delete_backup(filename: str) -> bool:
    """Deletes a specific backup file from the backups directory."""
    target_path = validate_and_resolve_backup_path(filename, must_exist=True)
    if os.path.exists(target_path) and os.path.isfile(target_path):
        os.remove(target_path)
        return True
    return False
