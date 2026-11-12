import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, ConfigDict, Field

# Auth Schemas
class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None

class UserResponse(BaseModel):
    user_id: int
    username: str
    auth0_sub: Optional[str] = None
    email: Optional[str] = None
    name: Optional[str] = None
    picture: Optional[str] = None
    created_at: Optional[datetime.datetime] = None
    updated_at: Optional[datetime.datetime] = None
    model_config = ConfigDict(from_attributes=True)

# Account Schemas
class AccountBase(BaseModel):
    account_name: str
    broker_name: Optional[str] = None
    account_type: str
    currency: str = "USD"
    default_dividend_account_id: Optional[int] = None

class AccountResponse(AccountBase):
    account_id: int
    created_at: datetime.date
    current_balance: Optional[float] = 0.0
    cash_balance: Optional[float] = 0.0
    securities_value: Optional[float] = 0.0
    default_dividend_account_name: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)

# Asset Schemas
class AssetBase(BaseModel):
    symbol: str
    isin: Optional[str] = None
    name: str
    asset_type: str
    exchange: Optional[str] = None
    sector: Optional[str] = None
    industry: Optional[str] = None
    currency: str = "USD"

class AssetResponse(AssetBase):
    asset_id: int
    model_config = ConfigDict(from_attributes=True)

# Lot Schemas
class LotResponse(BaseModel):
    lot_id: int
    account_id: int
    asset_id: int
    buy_transaction_id: int
    buy_date: datetime.date
    quantity_original: float
    quantity_remaining: float
    cost_per_unit: float
    model_config = ConfigDict(from_attributes=True)

class LotSaleResponse(BaseModel):
    lot_sale_id: int
    lot_id: int
    sell_transaction_id: int
    quantity_sold: float
    sale_price_per_unit: float
    cost_basis: float
    realized_pnl: float
    holding_period_days: Optional[int] = None
    sell_date: Optional[datetime.date] = None
    buy_date: Optional[datetime.date] = None
    asset_symbol: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)

# Price History Schemas
class PriceHistoryResponse(BaseModel):
    price_id: int
    asset_id: int
    price_date: datetime.date
    close_price: float
    source: str
    model_config = ConfigDict(from_attributes=True)

# Portfolio Summary & Holdings Schemas
class HoldingSummary(BaseModel):
    asset_id: int
    symbol: str
    name: str
    asset_type: str
    sector: Optional[str] = None
    industry: Optional[str] = None
    currency: str = "USD"
    quantity_held: float
    avg_cost_price: float
    total_cost: float
    latest_price: float
    latest_price_date: Optional[datetime.date] = None
    previous_price: float = 0.0
    change_1d: float = 0.0
    change_1d_pct: float = 0.0
    value_change_1d: float = 0.0
    current_value: float
    unrealized_pnl: float
    unrealized_pnl_pct: float
    realized_pnl: float = 0.0
    realized_pnl_pct: float = 0.0
    dividend_income: float = 0.0
    capital_gains_realized: float = 0.0
    fees_and_taxes: float = 0.0
    total_fees: float = 0.0
    total_taxes: float = 0.0
    net_pnl: float = 0.0
    net_pnl_pct: float = 0.0
    xirr: Optional[float] = None
    open_lots: List[LotResponse] = []

class PortfolioSummaryResponse(BaseModel):
    total_net_worth: float
    total_invested: float
    total_current_value: float
    cash_balance: float
    total_realized_pnl: float
    total_unrealized_pnl: float
    total_dividend_income: float = 0.0
    total_capital_gains_realized: float = 0.0
    total_value_change_1d: float = 0.0
    total_change_1d_pct: float = 0.0
    total_fees: float = 0.0
    total_taxes: float = 0.0
    portfolio_xirr: Optional[float] = None
    asset_allocation: dict
    sector_allocation: dict = {}
    top_holdings: List[HoldingSummary] = []
    closed_holdings: List[HoldingSummary] = []

class AnnualSnapshotResponse(BaseModel):
    year_label: str
    start_date: datetime.date
    end_date: datetime.date
    total_income: float
    total_expenses: float
    investments_done: float
    investments_closed: float
    net_worth_delta: float
    net_worth_delta_pct: float
    taxes_and_fees: float
    net_savings: float
    currency: str = "EUR"

# Snapshot Schemas
class AssetClassBreakdown(BaseModel):
    asset_class: str
    value: float
    model_config = ConfigDict(from_attributes=True)

class NetworthSnapshotResponse(BaseModel):
    snapshot_id: int
    snapshot_date: datetime.date
    total_invested: float
    total_current_value: float
    cash_balance: float
    total_realized_pnl: float
    total_unrealized_pnl: float
    net_worth: float
    asset_class_breakdowns: List[AssetClassBreakdown] = []
    model_config = ConfigDict(from_attributes=True)

class TriggerRecalculateRequest(BaseModel):
    user_id: int
    start_date: Optional[datetime.date] = None
    reason: Optional[str] = "manual"

# Benchmark Schemas
class BenchmarkDataPoint(BaseModel):
    price_date: datetime.date
    close_value: float

class BenchmarkResponse(BaseModel):
    benchmark_name: str
    data: List[BenchmarkDataPoint]
