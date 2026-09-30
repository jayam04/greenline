import json
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from sqlalchemy.orm import selectinload

from app.db.database import get_db
from app.db.models import ImportBatch, StagedRecord, User, Account, Asset, Category
from app.schemas.import_schemas import (
    ImportBatchResponse, StagedRecordResponse, StagedRecordCreate,
    StagedRecordUpdate, BatchCommitRequest, BatchCommitResponse
)
from app.api.deps import get_current_user
from app.services.ai.chunker import decrypt_and_extract_pdf_pages, chunk_pdf_pages, chunk_tabular_data
from app.services.ai.providers import get_ai_provider
from app.services.ai.base import DocumentContext
from app.services.ai.staging_service import (
    create_import_batch, stage_parsed_records, update_staged_record,
    delete_staged_record, commit_import_batch
)

router = APIRouter(prefix="/import", tags=["import"])

def _build_record_response(rec: StagedRecord) -> StagedRecordResponse:
    match_details = None
    if rec.matched_entity_details:
        try:
            match_details = json.loads(rec.matched_entity_details)
        except Exception:
            pass

    return StagedRecordResponse(
        staged_id=rec.staged_id,
        batch_id=rec.batch_id,
        record_type=rec.record_type,
        transaction_date=rec.transaction_date,
        action_type=rec.action_type,
        account_id=rec.account_id,
        account_name_raw=rec.account_name_raw,
        account_name=rec.account.account_name if rec.account else None,
        asset_id=rec.asset_id,
        asset_symbol_raw=rec.asset_symbol_raw,
        asset_symbol=rec.asset.symbol if rec.asset else rec.asset_symbol_raw,
        asset_name_raw=rec.asset_name_raw,
        asset_name=rec.asset.name if rec.asset else rec.asset_name_raw,
        category_id=rec.category_id,
        category_name_raw=rec.category_name_raw,
        category_name=rec.category.name if rec.category else rec.category_name_raw,
        quantity=rec.quantity,
        price_per_unit=rec.price_per_unit,
        total_amount=rec.total_amount,
        fees=rec.fees,
        taxes=rec.taxes,
        currency=rec.currency,
        notes=rec.notes,
        source_raw_text=rec.source_raw_text,
        review_status=rec.review_status,
        match_status=rec.match_status,
        matched_entity_id=rec.matched_entity_id,
        matched_entity_details=match_details,
        confidence_score=rec.confidence_score
    )

@router.post("/upload", response_model=ImportBatchResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(...),
    password: Optional[str] = Form(None),
    target_account_id: Optional[int] = Form(None),
    default_currency: str = Form("USD"),
    custom_instructions: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    content = await file.read()
    filename = file.filename or "upload"
    file_type = filename.split(".")[-1].lower() if "." in filename else "csv"

    # 1. Create Staging Batch
    batch = await create_import_batch(
        db=db,
        filename=filename,
        file_type=file_type,
        file_size_bytes=len(content),
        target_account_id=target_account_id,
        default_currency=default_currency,
        custom_instructions=custom_instructions
    )

    # 2. Extract Chunks based on file type
    chunks = []
    try:
        if file_type == "pdf":
            pages = decrypt_and_extract_pdf_pages(content, password=password)
            chunks = chunk_pdf_pages(pages, pages_per_chunk=3)
        elif file_type in ["csv", "xlsx", "xls", "tsv"]:
            mime = "text/csv" if file_type in ["csv", "tsv"] else "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            chunks = chunk_tabular_data(content, mime_type=mime, chunk_size=150)
        else:
            chunks = [content.decode("utf-8", errors="ignore")]
    except Exception as e:
        batch.status = "failed"
        batch.error_message = str(e)
        await db.commit()
        raise HTTPException(status_code=400, detail=str(e))

    # 3. Build Document Context
    acc_res = await db.execute(select(Account))
    accounts = [{"account_id": a.account_id, "account_name": a.account_name, "currency": a.currency} for a in acc_res.scalars().all()]
    cat_res = await db.execute(select(Category))
    categories = [{"category_id": c.category_id, "name": c.name} for c in cat_res.scalars().all()]
    ast_res = await db.execute(select(Asset))
    assets = [{"asset_id": a.asset_id, "symbol": a.symbol, "name": a.name} for a in ast_res.scalars().all()]

    target_acc_name = None
    if target_account_id:
        target_acc = next((a["account_name"] for a in accounts if a["account_id"] == target_account_id), None)
        target_acc_name = target_acc

    context = DocumentContext(
        target_account_id=target_account_id,
        target_account_name=target_acc_name,
        default_currency=default_currency,
        custom_instructions=custom_instructions,
        existing_accounts=accounts,
        existing_categories=categories,
        existing_assets=assets
    )

    # 4. Parse Chunks through AI Provider
    ai_provider = get_ai_provider()
    all_raw_records = []
    for chunk in chunks:
        try:
            extracted = await ai_provider.parse_document_chunk(chunk, context)
            all_raw_records.extend([e.model_dump() for e in extracted])
        except Exception as e:
            print(f"[AI Parse Error on Chunk] {e}")

    # 5. Stage records with Two-Tier Matcher
    if all_raw_records:
        await stage_parsed_records(db=db, batch_id=batch.batch_id, raw_records=all_raw_records)
    else:
        batch.status = "ready_for_review"
        batch.progress_pct = 100
        batch.current_step = "Parsed 0 records"
        await db.commit()

    await db.refresh(batch)
    return batch

@router.get("/batches", response_model=List[ImportBatchResponse])
async def list_import_batches(
    limit: int = 20,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    stmt = (
        select(ImportBatch)
        .options(selectinload(ImportBatch.target_account))
        .order_by(desc(ImportBatch.created_at))
        .limit(limit)
        .offset(offset)
    )
    res = await db.execute(stmt)
    batches = res.scalars().all()
    results = []
    for b in batches:
        resp = ImportBatchResponse.model_validate(b)
        if b.target_account:
            resp.target_account_name = b.target_account.account_name
        results.append(resp)
    return results

@router.get("/batches/{batch_id}", response_model=ImportBatchResponse)
async def get_import_batch(
    batch_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    stmt = select(ImportBatch).options(selectinload(ImportBatch.target_account)).where(ImportBatch.batch_id == batch_id)
    res = await db.execute(stmt)
    batch = res.scalar_one_or_none()
    if not batch:
        raise HTTPException(status_code=404, detail="Import batch not found.")
    resp = ImportBatchResponse.model_validate(batch)
    if batch.target_account:
        resp.target_account_name = batch.target_account.account_name
    return resp

@router.get("/batches/{batch_id}/records", response_model=List[StagedRecordResponse])
async def list_staged_records(
    batch_id: int,
    status_filter: Optional[str] = Query(None, description="approved, pending, skipped, modified"),
    match_filter: Optional[str] = Query(None, description="new, exact_match, probable_match"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    stmt = (
        select(StagedRecord)
        .options(
            selectinload(StagedRecord.account),
            selectinload(StagedRecord.asset),
            selectinload(StagedRecord.category)
        )
        .where(StagedRecord.batch_id == batch_id)
        .order_by(StagedRecord.transaction_date.desc(), StagedRecord.staged_id.desc())
    )
    if status_filter:
        stmt = stmt.where(StagedRecord.review_status == status_filter)
    if match_filter:
        stmt = stmt.where(StagedRecord.match_status == match_filter)

    res = await db.execute(stmt)
    records = res.scalars().all()
    return [_build_record_response(r) for r in records]

@router.patch("/batches/{batch_id}/records/{staged_id}", response_model=StagedRecordResponse)
async def edit_staged_record(
    batch_id: int,
    staged_id: int,
    update_in: StagedRecordUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        updated = await update_staged_record(db, staged_id, **update_in.model_dump(exclude_unset=True))
        # Re-fetch with relationships
        stmt = (
            select(StagedRecord)
            .options(
                selectinload(StagedRecord.account),
                selectinload(StagedRecord.asset),
                selectinload(StagedRecord.category)
            )
            .where(StagedRecord.staged_id == staged_id)
        )
        res = await db.execute(stmt)
        refreshed = res.scalar_one()
        return _build_record_response(refreshed)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.delete("/batches/{batch_id}/records/{staged_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_staged_record(
    batch_id: int,
    staged_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    success = await delete_staged_record(db, staged_id)
    if not success:
        raise HTTPException(status_code=404, detail="Staged record not found.")

@router.post("/batches/{batch_id}/records", response_model=StagedRecordResponse, status_code=status.HTTP_201_CREATED)
async def add_manual_staged_record(
    batch_id: int,
    record_in: StagedRecordCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    created_list = await stage_parsed_records(db, batch_id, [record_in.model_dump()])
    if not created_list:
        raise HTTPException(status_code=400, detail="Failed to add staged record.")
    
    stmt = (
        select(StagedRecord)
        .options(
            selectinload(StagedRecord.account),
            selectinload(StagedRecord.asset),
            selectinload(StagedRecord.category)
        )
        .where(StagedRecord.staged_id == created_list[0].staged_id)
    )
    res = await db.execute(stmt)
    return _build_record_response(res.scalar_one())

@router.post("/batches/{batch_id}/commit", response_model=BatchCommitResponse)
async def commit_batch(
    batch_id: int,
    commit_req: Optional[BatchCommitRequest] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    The Final Green Flag: merges approved staged records into the live ledger,
    recalculates lots & snapshots, and marks batch as merged.
    """
    rec_ids = commit_req.record_ids if commit_req else None
    try:
        res = await commit_import_batch(db, batch_id, record_ids=rec_ids)
        return BatchCommitResponse(**res)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
