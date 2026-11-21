import datetime
from typing import List, Optional, Any, Dict
from pydantic import BaseModel, Field, ConfigDict, model_validator

class MCPCashflowPaymentInput(BaseModel):
    account_id: Optional[int] = Field(None, description="ID of the bank or wallet account")
    account_name: Optional[str] = Field(None, description="Exact name of the bank/wallet account (strictly matched against existing accounts)")
    amount: float = Field(..., description="Signed payment amount. Negative (-) for expense/outflow, positive (+) for income/inflow")
    currency: Optional[str] = Field("EUR", description="Currency code (EUR, USD, etc.)")

class MCPCashflowItemInput(BaseModel):
    category_id: int = Field(..., description="Strict category ID from GET /api/v1/mcp/categories")
    amount: float = Field(..., description="Signed item amount. Negative (-) for expense/outflow, positive (+) for income/inflow")
    description: Optional[str] = Field(None, description="Detailed line item or item name, e.g. '1x Milk'")
    label: Optional[str] = Field(None, description="Optional classification: ESSENTIAL, DISCRETIONARY, LUXURY, INVESTMENT")

class MCPCashflowOperation(BaseModel):
    action: str = Field("create", description="Operation action: 'create', 'update', or 'delete'")
    cashflow_id: Optional[int] = Field(None, description="Required for 'update' or 'delete'")
    date: Optional[datetime.date] = Field(None, description="Transaction date (YYYY-MM-DD). Defaults to today if creating")
    merchant: Optional[str] = Field(None, description="Counterparty or merchant name only (e.g. 'Tesco', 'Employer Ltd'). Generic titles like 'Expense' are rejected")
    currency: str = Field("EUR", description="Currency code")
    notes: Optional[str] = Field(None, description="Optional transaction notes")
    payments: Optional[List[MCPCashflowPaymentInput]] = Field(None, description="List of payment methods and amounts")
    items: Optional[List[MCPCashflowItemInput]] = Field(None, description="List of category items and amounts")

class MCPCashflowMutateRequest(BaseModel):
    operations: List[MCPCashflowOperation] = Field(
        ...,
        description="List of cashflow operations to create, update, or delete. For a single transaction, provide an array containing 1 operation."
    )

    @model_validator(mode="before")
    @classmethod
    def normalize_input(cls, data: Any) -> Any:
        if isinstance(data, list):
            return {"operations": data}
        if isinstance(data, dict) and "operations" not in data:
            return {"operations": [data]}
        return data

class MCPCashflowPaymentResponse(BaseModel):
    payment_id: Optional[int] = None
    account_id: int
    account_name: str
    amount: float
    currency: str = "EUR"
    model_config = ConfigDict(from_attributes=True)

class MCPCashflowItemResponse(BaseModel):
    item_id: Optional[int] = None
    category_id: int
    category_name: str
    amount: float
    description: Optional[str] = None
    label: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)

class MCPCashflowStatement(BaseModel):
    cashflow_id: int
    date: datetime.date
    merchant: str
    total_amount: float
    currency: str
    transaction_kind: str
    notes: Optional[str] = None
    payments: List[MCPCashflowPaymentResponse] = []
    items: List[MCPCashflowItemResponse] = []
    model_config = ConfigDict(from_attributes=True)

class MCPCashflowMutateResponse(BaseModel):
    results: List[MCPCashflowStatement]
    message: str

class MCPCashflowReadResponse(BaseModel):
    statements: List[MCPCashflowStatement]
    total_count: int

class MCPCategoryItem(BaseModel):
    category_id: int
    name: str
    full_path: str
    category_type: str
    default_label: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)

class MCPAvailableAccount(BaseModel):
    account_id: int
    account_name: str
    currency: str
    account_type: str
    model_config = ConfigDict(from_attributes=True)

class MCPCategoriesResponse(BaseModel):
    categories: List[MCPCategoryItem]
    available_accounts: List[MCPAvailableAccount]
