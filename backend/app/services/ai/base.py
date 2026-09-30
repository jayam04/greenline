import datetime
from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

class ExtractedRecord(BaseModel):
    record_type: str = "investment"  # "investment" or "cashflow"
    transaction_date: datetime.date
    action_type: str  # buy, sell, dividend, bonus, split, income, expense, transfer
    account_name_raw: Optional[str] = None
    asset_symbol_raw: Optional[str] = None
    asset_name_raw: Optional[str] = None
    category_name_raw: Optional[str] = None
    quantity: Optional[float] = None
    price_per_unit: Optional[float] = None
    total_amount: float
    fees: float = 0.0
    taxes: float = 0.0
    currency: str = "USD"
    notes: Optional[str] = None
    confidence_score: float = 1.0
    source_raw_text: Optional[str] = None

class DocumentContext(BaseModel):
    target_account_id: Optional[int] = None
    target_account_name: Optional[str] = None
    default_currency: str = "USD"
    custom_instructions: Optional[str] = None
    existing_accounts: List[Dict[str, Any]] = Field(default_factory=list)
    existing_categories: List[Dict[str, Any]] = Field(default_factory=list)
    existing_assets: List[Dict[str, Any]] = Field(default_factory=list)

class BaseAIProvider(ABC):
    @abstractmethod
    async def parse_document_chunk(
        self,
        chunk_text: str,
        context: DocumentContext
    ) -> List[ExtractedRecord]:
        """Parses a text or tabular chunk into normalized extracted records."""
        pass
