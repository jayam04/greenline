import datetime
from typing import List, Optional, Any, Dict
from pydantic import BaseModel, Field, ConfigDict

class StagedRecordBase(BaseModel):
    record_type: str = Field("investment", description="investment or cashflow")
    transaction_date: datetime.date
    action_type: str  # buy, sell, dividend, bonus, split, income, expense, transfer
    account_id: Optional[int] = None
    account_name_raw: Optional[str] = None
    asset_id: Optional[int] = None
    asset_symbol_raw: Optional[str] = None
    asset_name_raw: Optional[str] = None
    category_id: Optional[int] = None
    category_name_raw: Optional[str] = None
    quantity: Optional[float] = None
    price_per_unit: Optional[float] = None
    total_amount: float
    fees: float = 0.0
    taxes: float = 0.0
    currency: str = "USD"
    notes: Optional[str] = None
    source_raw_text: Optional[str] = None

class StagedRecordCreate(StagedRecordBase):
    review_status: str = "approved"

class StagedRecordUpdate(BaseModel):
    transaction_date: Optional[datetime.date] = None
    action_type: Optional[str] = None
    account_id: Optional[int] = None
    asset_id: Optional[int] = None
    asset_symbol_raw: Optional[str] = None
    category_id: Optional[int] = None
    quantity: Optional[float] = None
    price_per_unit: Optional[float] = None
    total_amount: Optional[float] = None
    fees: Optional[float] = None
    taxes: Optional[float] = None
    currency: Optional[str] = None
    notes: Optional[str] = None
    review_status: Optional[str] = None  # approved, pending, skipped, modified

class StagedRecordResponse(StagedRecordBase):
    staged_id: int
    batch_id: int
    review_status: str
    match_status: str
    matched_entity_id: Optional[int] = None
    matched_entity_details: Optional[Dict[str, Any]] = None
    confidence_score: float = 1.0
    account_name: Optional[str] = None
    asset_symbol: Optional[str] = None
    asset_name: Optional[str] = None
    category_name: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

class ImportBatchResponse(BaseModel):
    batch_id: int
    filename: str
    file_type: str
    file_size_bytes: int
    status: str
    scope: str
    target_account_id: Optional[int] = None
    target_account_name: Optional[str] = None
    default_currency: str
    custom_instructions: Optional[str] = None
    progress_pct: int
    current_step: Optional[str] = None
    error_message: Optional[str] = None
    total_records: int
    new_records: int
    exact_matches: int
    probable_matches: int
    created_at: datetime.datetime
    updated_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)

class BatchCommitRequest(BaseModel):
    record_ids: Optional[List[int]] = None  # If None, commits all with review_status in ("approved", "modified")

class BatchCommitResponse(BaseModel):
    batch_id: int
    status: str
    committed_count: int
    skipped_count: int
    created_assets_count: int
    created_categories_count: int
    message: str
