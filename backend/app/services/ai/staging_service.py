import json
import datetime
from typing import List, Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, func

from app.db.models import (
    ImportBatch, StagedRecord, Account, Asset, Transaction,
    CashflowTransaction, CashflowPayment, CashflowItem, Category, PriceHistory
)
from app.services.ai.matcher import match_staged_record
from app.services.fifo_engine import recalculate_all_lots
from app.services.snapshot_engine import recalculate_past_snapshots

async def create_import_batch(
    db: AsyncSession,
    filename: str,
    file_type: str,
    file_size_bytes: int = 0,
    target_account_id: Optional[int] = None,
    default_currency: str = "USD",
    custom_instructions: Optional[str] = None,
    scope: str = "unified"
) -> ImportBatch:
    batch = ImportBatch(
        filename=filename,
        file_type=file_type,
        file_size_bytes=file_size_bytes,
        status="processing",
        scope=scope,
        target_account_id=target_account_id,
        default_currency=default_currency,
        custom_instructions=custom_instructions
    )
    db.add(batch)
    await db.commit()
    await db.refresh(batch)
    return batch

async def stage_parsed_records(
    db: AsyncSession,
    batch_id: int,
    raw_records: List[Dict[str, Any]]
) -> List[StagedRecord]:
    batch_stmt = select(ImportBatch).where(ImportBatch.batch_id == batch_id)
    batch_res = await db.execute(batch_stmt)
    batch = batch_res.scalar_one_or_none()
    if not batch:
        raise ValueError(f"Batch {batch_id} not found.")

    # Pre-cache assets and accounts for symbol/id resolution
    ast_res = await db.execute(select(Asset))
    assets = ast_res.scalars().all()
    asset_sym_map = {a.symbol.upper(): a.asset_id for a in assets}

    acc_res = await db.execute(select(Account))
    accounts = acc_res.scalars().all()
    acc_name_map = {a.account_name.lower(): a.account_id for a in accounts}

    created_records = []
    new_count = 0
    exact_count = 0
    prob_count = 0

    for item in raw_records:
        rec_type = item.get("record_type", "investment")
        t_date = item.get("transaction_date")
        if isinstance(t_date, str):
            t_date = datetime.date.fromisoformat(t_date[:10])

        sym_raw = item.get("asset_symbol_raw")
        res_asset_id = item.get("asset_id")
        if not res_asset_id and sym_raw:
            res_asset_id = asset_sym_map.get(sym_raw.upper().strip())

        res_acc_id = item.get("account_id") or batch.target_account_id
        acc_raw = item.get("account_name_raw")
        if not res_acc_id and acc_raw:
            res_acc_id = acc_name_map.get(acc_raw.lower().strip())

        staged = StagedRecord(
            batch_id=batch_id,
            record_type=rec_type,
            transaction_date=t_date,
            action_type=item.get("action_type", "buy"),
            account_id=res_acc_id,
            account_name_raw=acc_raw,
            asset_id=res_asset_id,
            asset_symbol_raw=sym_raw,
            asset_name_raw=item.get("asset_name_raw"),
            category_id=item.get("category_id"),
            category_name_raw=item.get("category_name_raw"),
            quantity=item.get("quantity"),
            price_per_unit=item.get("price_per_unit"),
            total_amount=float(item.get("total_amount", 0.0)),
            fees=float(item.get("fees", 0.0)),
            taxes=float(item.get("taxes", 0.0)),
            currency=item.get("currency", batch.default_currency or "USD"),
            notes=item.get("notes"),
            source_raw_text=item.get("source_raw_text"),
            confidence_score=float(item.get("confidence_score", 1.0))
        )

        # Run Two-Tier Matcher
        match_res = await match_staged_record(db, staged)
        staged.match_status = match_res.status
        staged.matched_entity_id = match_res.matched_id
        staged.matched_entity_details = json.dumps(match_res.matched_details) if match_res.matched_details else None
        
        # User review_status preference override if provided, else default from matcher
        staged.review_status = item.get("review_status") or match_res.default_review_status

        if match_res.status == "exact_match":
            exact_count += 1
        elif match_res.status == "probable_match":
            prob_count += 1
        else:
            new_count += 1

        db.add(staged)
        created_records.append(staged)

    # Update batch summary
    batch.total_records += len(created_records)
    batch.new_records += new_count
    batch.exact_matches += exact_count
    batch.probable_matches += prob_count
    batch.status = "ready_for_review"
    batch.progress_pct = 100
    batch.current_step = "Completed AI ingestion & duplicate matching"

    await db.commit()
    for rec in created_records:
        await db.refresh(rec)

    return created_records

async def update_staged_record(
    db: AsyncSession,
    staged_id: int,
    **updates
) -> StagedRecord:
    stmt = select(StagedRecord).where(StagedRecord.staged_id == staged_id)
    res = await db.execute(stmt)
    rec = res.scalar_one_or_none()
    if not rec:
        raise ValueError(f"Staged record {staged_id} not found.")

    for field, val in updates.items():
        if hasattr(rec, field) and val is not None:
            setattr(rec, field, val)

    await db.commit()
    await db.refresh(rec)
    return rec

async def delete_staged_record(db: AsyncSession, staged_id: int) -> bool:
    stmt = select(StagedRecord).where(StagedRecord.staged_id == staged_id)
    res = await db.execute(stmt)
    rec = res.scalar_one_or_none()
    if not rec:
        return False

    # Adjust batch counters
    batch_stmt = select(ImportBatch).where(ImportBatch.batch_id == rec.batch_id)
    batch_res = await db.execute(batch_stmt)
    batch = batch_res.scalar_one_or_none()
    if batch:
        batch.total_records = max(0, batch.total_records - 1)
        if rec.match_status == "exact_match":
            batch.exact_matches = max(0, batch.exact_matches - 1)
        elif rec.match_status == "probable_match":
            batch.probable_matches = max(0, batch.probable_matches - 1)
        else:
            batch.new_records = max(0, batch.new_records - 1)

    await db.delete(rec)
    await db.commit()
    return True

async def commit_import_batch(
    db: AsyncSession,
    batch_id: int,
    record_ids: Optional[List[int]] = None
) -> Dict[str, Any]:
    """
    Executes the Final Green Flag merge:
      - Takes approved & modified records from staging.
      - Auto-creates any missing assets or categories.
      - Inserts into live Transaction or CashflowTransaction tables.
      - Auto-populates PriceHistory if price_per_unit exists.
      - Recalculates lots and net worth snapshots.
      - Marks batch as 'merged'.
    """
    batch_stmt = select(ImportBatch).where(ImportBatch.batch_id == batch_id)
    batch_res = await db.execute(batch_stmt)
    batch = batch_res.scalar_one_or_none()
    if not batch:
        raise ValueError(f"Batch {batch_id} not found.")

    query = select(StagedRecord).where(StagedRecord.batch_id == batch_id)
    if record_ids is not None:
        query = query.where(StagedRecord.staged_id.in_(record_ids))
    else:
        query = query.where(StagedRecord.review_status.in_(["approved", "modified"]))

    res = await db.execute(query)
    to_commit = res.scalars().all()

    # Query skipped count in this batch
    skipped_stmt = select(func.count(StagedRecord.staged_id)).where(
        StagedRecord.batch_id == batch_id,
        StagedRecord.review_status == "skipped"
    )
    skipped_res = await db.execute(skipped_stmt)
    skipped_count = skipped_res.scalar_one_or_none() or 0

    committed_count = 0
    created_assets = 0
    created_categories = 0
    earliest_date = None

    # Pre-fetch existing accounts, assets, categories
    ast_res = await db.execute(select(Asset))
    existing_assets = {a.symbol.upper(): a for a in ast_res.scalars().all()}

    cat_res = await db.execute(select(Category))
    existing_categories = {c.name.lower(): c for c in cat_res.scalars().all()}

    acc_res = await db.execute(select(Account))
    all_accounts = {a.account_id: a for a in acc_res.scalars().all()}
    first_acc_id = next(iter(all_accounts.keys())) if all_accounts else None

    for rec in to_commit:
        if rec.review_status == "skipped":
            skipped_count += 1
            continue

        if earliest_date is None or rec.transaction_date < earliest_date:
            earliest_date = rec.transaction_date

        acc_id = rec.account_id or batch.target_account_id or first_acc_id
        if not acc_id:
            raise ValueError("No account available for transaction. Please create an account first.")

        if rec.record_type == "investment":
            # Asset resolution / creation
            ast_id = rec.asset_id
            if not ast_id and rec.asset_symbol_raw:
                sym_clean = rec.asset_symbol_raw.upper().strip()
                if sym_clean in existing_assets:
                    ast_id = existing_assets[sym_clean].asset_id
                else:
                    new_asset = Asset(
                        symbol=sym_clean,
                        name=rec.asset_name_raw or sym_clean,
                        asset_type="stock",
                        currency=rec.currency or "USD"
                    )
                    db.add(new_asset)
                    await db.flush()
                    existing_assets[sym_clean] = new_asset
                    ast_id = new_asset.asset_id
                    created_assets += 1

            new_tx = Transaction(
                account_id=acc_id,
                asset_id=ast_id,
                transaction_type=rec.action_type.lower(),
                transaction_date=rec.transaction_date,
                quantity=rec.quantity,
                price_per_unit=rec.price_per_unit,
                total_amount=rec.total_amount,
                fees=rec.fees,
                taxes=rec.taxes,
                source="ai_import",
                notes=rec.notes
            )
            db.add(new_tx)
            await db.flush()

            # Ensure price history
            if ast_id and rec.price_per_unit and rec.price_per_unit > 0:
                ph_stmt = select(PriceHistory).where(
                    PriceHistory.asset_id == ast_id,
                    PriceHistory.price_date == rec.transaction_date
                )
                ph_res = await db.execute(ph_stmt)
                if not ph_res.scalar_one_or_none():
                    db.add(PriceHistory(
                        asset_id=ast_id,
                        price_date=rec.transaction_date,
                        close_price=rec.price_per_unit,
                        source="ai_import"
                    ))

            committed_count += 1

        else:
            # Cashflow resolution / creation
            cat_id = rec.category_id
            if not cat_id and rec.category_name_raw:
                cname = rec.category_name_raw.strip().lower()
                if cname in existing_categories:
                    cat_id = existing_categories[cname].category_id
                else:
                    cat_type = "INCOME" if rec.action_type.lower() == "income" else "EXPENSE"
                    new_cat = Category(
                        name=rec.category_name_raw.strip(),
                        category_type=cat_type
                    )
                    db.add(new_cat)
                    await db.flush()
                    existing_categories[cname] = new_cat
                    cat_id = new_cat.category_id
                    created_categories += 1

            title = rec.notes or rec.category_name_raw or f"Imported {rec.action_type}"
            new_cf = CashflowTransaction(
                transaction_date=rec.transaction_date,
                title=title,
                total_amount=rec.total_amount,
                currency=rec.currency or "USD",
                notes=rec.notes
            )
            db.add(new_cf)
            await db.flush()

            # Payment
            pmt_amount = rec.total_amount if rec.action_type.lower() == "income" else -abs(rec.total_amount)
            new_pmt = CashflowPayment(
                cashflow_id=new_cf.cashflow_id,
                account_id=acc_id,
                amount=pmt_amount
            )
            db.add(new_pmt)

            # Item
            if cat_id:
                new_item = CashflowItem(
                    cashflow_id=new_cf.cashflow_id,
                    category_id=cat_id,
                    amount=abs(rec.total_amount),
                    description=rec.notes
                )
                db.add(new_item)

            committed_count += 1

    batch.status = "merged"
    await db.commit()

    # Post-merge lot & snapshot recalculations
    try:
        await recalculate_all_lots(db)
        if earliest_date:
            await recalculate_past_snapshots(db, start_date=earliest_date)
    except Exception as e:
        print(f"[Import Commit Warning] Recalculation error: {e}")

    return {
        "batch_id": batch_id,
        "status": "merged",
        "committed_count": committed_count,
        "skipped_count": skipped_count,
        "created_assets_count": created_assets,
        "created_categories_count": created_categories,
        "message": f"Successfully merged {committed_count} records into live portfolio."
    }
