import datetime
from typing import List, Optional, Any
from pydantic import BaseModel, Field, ConfigDict, model_validator
from app.schemas.mcp_schemas import MCPAvailableAccount

class MCPStockAssetItem(BaseModel):
    asset_id: int
    symbol: str
    name: str
    asset_type: str
    currency: str
    exchange: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)

class MCPStockOperation(BaseModel):
    action: str = Field("create", description="Operation action: 'create', 'update', or 'delete'")
    transaction_id: Optional[int] = Field(None, description="Required for 'update' or 'delete'")

    # Account matching
    account_id: Optional[int] = Field(None, description="ID of the trading/demat/bank account")
    account_name: Optional[str] = Field(None, description="Exact name of the trading account (strictly matched against available_accounts; creating accounts is forbidden)")
    funding_account_id: Optional[int] = Field(None, description="Optional funding account ID if funded from another bank/cash account")
    funding_account_name: Optional[str] = Field(None, description="Optional funding account name")

    # Asset matching & Force Creation
    asset_id: Optional[int] = Field(None, description="ID of the stock/asset")
    symbol: Optional[str] = Field(None, description="Ticker symbol of the stock/asset (e.g. 'AAPL', 'MSFT', 'RELIANCE')")
    isin: Optional[str] = Field(None, description="Optional ISIN code of the asset")
    asset_name: Optional[str] = Field(None, description="Company/asset name, e.g. 'Apple Inc.'")
    force_create_asset: bool = Field(False, description="Set to true to force-create the asset if it does not already exist in Greenline")
    asset_type: Optional[str] = Field("stock", description="Asset type if force-creating: 'stock', 'etf', 'mutual_fund', 'bond', 'crypto'")
    asset_currency: Optional[str] = Field(None, description="Currency of the asset (defaults to account currency or USD)")
    exchange: Optional[str] = Field(None, description="Exchange if force-creating, e.g. 'NASDAQ', 'NYSE', 'NSE', 'LSE'")

    # Transaction details
    transaction_type: str = Field("buy", description="Type of transaction: 'buy', 'sell', 'dividend', 'bonus', 'split', 'deposit', 'withdrawal'")
    date: Optional[datetime.date] = Field(None, description="Date of transaction (YYYY-MM-DD). Defaults to today if creating")
    quantity: Optional[float] = Field(None, description="Number of units or shares")
    price_per_unit: Optional[float] = Field(None, description="Execution price per share/unit")
    fees: float = Field(0.0, description="Brokerage, commission, or exchange fees")
    taxes: float = Field(0.0, description="Taxes, stamp duty, or withholding tax")
    total_amount: Optional[float] = Field(None, description="Total net cash outlay or proceeds. If omitted, automatically computed from quantity, price, fees, and taxes")
    notes: Optional[str] = Field(None, description="Optional notes or trade tags")

class MCPStockMutateRequest(BaseModel):
    operations: List[MCPStockOperation] = Field(
        ...,
        description="List of stock operations to create, update, or delete. For a single transaction, provide an array containing 1 operation."
    )

    @model_validator(mode="before")
    @classmethod
    def normalize_input(cls, data: Any) -> Any:
        if isinstance(data, list):
            return {"operations": data}
        if isinstance(data, dict) and "operations" not in data:
            return {"operations": [data]}
        return data

class MCPStockTransactionResponse(BaseModel):
    transaction_id: int
    account_id: int
    account_name: str
    account_currency: str
    funding_account_id: Optional[int] = None
    funding_account_name: Optional[str] = None
    asset_id: Optional[int] = None
    asset_symbol: Optional[str] = None
    asset_name: Optional[str] = None
    transaction_type: str
    date: datetime.date
    quantity: Optional[float] = None
    price_per_unit: Optional[float] = None
    fees: float = 0.0
    taxes: float = 0.0
    total_amount: float
    notes: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)

class MCPStockMutateResponse(BaseModel):
    results: List[MCPStockTransactionResponse]
    message: str

class MCPStockReadResponse(BaseModel):
    available_assets: List[MCPStockAssetItem]
    available_accounts: List[MCPAvailableAccount]
    transactions: List[MCPStockTransactionResponse]
    total_count: int
