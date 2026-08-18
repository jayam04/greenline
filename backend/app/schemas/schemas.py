import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, ConfigDict

# Auth Schemas
class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None

class UserLogin(BaseModel):
    username: str
    password: str

class UserResponse(BaseModel):
    user_id: int
    username: str
    created_at: datetime.datetime
    model_config = ConfigDict(from_attributes=True)

# Account Schemas
class AccountBase(BaseModel):
    account_name: str
    broker_name: Optional[str] = None
    account_type: str # demat, mutual_fund, pf, nps, crypto_exchange, bank
    currency: str = "USD"

class AccountCreate(AccountBase):
    pass

class AccountUpdate(BaseModel):
    account_name: Optional[str] = None
    broker_name: Optional[str] = None
    account_type: Optional[str] = None
    currency: Optional[str] = None

class AccountResponse(AccountBase):
    account_id: int
    created_at: datetime.date
    model_config = ConfigDict(from_attributes=True)

# Asset Schemas
class AssetBase(BaseModel):
    symbol: str
    isin: Optional[str] = None
    name: str
    asset_type: str # stock, etf, mutual_fund, bond, fd, crypto, gold
    exchange: Optional[str] = None
    sector: Optional[str] = None
    industry: Optional[str] = None
    currency: str = "USD"

class AssetCreate(AssetBase):
    pass

class AssetUpdate(BaseModel):
    symbol: Optional[str] = None
    isin: Optional[str] = None
    name: Optional[str] = None
    asset_type: Optional[str] = None
    exchange: Optional[str] = None
    sector: Optional[str] = None
    industry: Optional[str] = None
    currency: Optional[str] = None

class AssetResponse(AssetBase):
    asset_id: int
    model_config = ConfigDict(from_attributes=True)

# Transaction Schemas
class TransactionCreate(BaseModel):
    account_id: int
    asset_id: Optional[int] = None
    transaction_type: str # buy, sell, dividend, bonus, split, interest, fee, deposit, withdrawal
    transaction_date: datetime.date
    quantity: Optional[float] = None
    price_per_unit: Optional[float] = None
    total_amount: float
    fees: float = 0.0
    taxes: float = 0.0
    notes: Optional[str] = None

class TransactionUpdate(BaseModel):
    account_id: Optional[int] = None
    asset_id: Optional[int] = None
    transaction_type: Optional[str] = None
    transaction_date: Optional[datetime.date] = None
    quantity: Optional[float] = None
    price_per_unit: Optional[float] = None
    total_amount: Optional[float] = None
    fees: Optional[float] = None
    taxes: Optional[float] = None
    notes: Optional[str] = None

class TransactionResponse(TransactionCreate):
    transaction_id: int
    account_name: Optional[str] = None
    account_currency: Optional[str] = "USD"
    asset_symbol: Optional[str] = None
    asset_name: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)

# Lot & LotSale Schemas
class LotResponse(BaseModel):
    lot_id: int
    account_id: int
    asset_id: int
    buy_transaction_id: int
    buy_date: datetime.date
    quantity_original: float
    quantity_remaining: float
    cost_per_unit: float
    asset_symbol: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)

class LotSaleResponse(BaseModel):
    lot_sale_id: int
    lot_id: int
    sell_transaction_id: int
    quantity_sold: float
    sale_price_per_unit: float
    cost_basis: float
    realized_pnl: float
    holding_period_days: int
    sell_date: Optional[datetime.date] = None
    buy_date: Optional[datetime.date] = None
    asset_symbol: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)

# Price History Schemas
class PriceHistoryCreate(BaseModel):
    asset_id: int
    price_date: datetime.date
    close_price: float
    source: str = "manual"

class PriceHistoryResponse(BaseModel):
    price_id: int
    asset_id: int
    price_date: datetime.date
    close_price: float
    source: str
    model_config = ConfigDict(from_attributes=True)

# Corporate Action Schemas
class CorporateActionCreate(BaseModel):
    asset_id: int
    action_type: str # split, bonus, merger, spinoff, name_change
    action_date: datetime.date
    ratio: str # e.g. "2:1"
    notes: Optional[str] = None

class CorporateActionResponse(CorporateActionCreate):
    action_id: int
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
    current_value: float
    unrealized_pnl: float
    unrealized_pnl_pct: float
    realized_pnl: float = 0.0
    realized_pnl_pct: float = 0.0
    xirr: Optional[float] = None
    open_lots: List[LotResponse] = []

class PortfolioSummaryResponse(BaseModel):
    total_net_worth: float
    total_invested: float
    total_current_value: float
    cash_balance: float
    total_realized_pnl: float
    total_unrealized_pnl: float
    total_fees: float = 0.0
    total_taxes: float = 0.0
    portfolio_xirr: Optional[float] = None
    asset_allocation: dict
    sector_allocation: dict = {}
    top_holdings: List[HoldingSummary]
    closed_holdings: List[HoldingSummary] = []

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

# Benchmark Schemas
class BenchmarkDataPoint(BaseModel):
    price_date: datetime.date
    close_value: float

class BenchmarkResponse(BaseModel):
    benchmark_name: str
    data: List[BenchmarkDataPoint]

# Category Schemas
class CategoryBase(BaseModel):
    name: str
    parent_id: Optional[int] = None
    category_type: str = "EXPENSE" # INCOME, EXPENSE, INVESTMENT, TRANSFER
    default_label: Optional[str] = None # ESSENTIAL, DISCRETIONARY, LUXURY, INVESTMENT
    icon: Optional[str] = None
    color: Optional[str] = None

class CategoryCreate(CategoryBase):
    pass

class CategoryUpdate(BaseModel):
    name: Optional[str] = None
    parent_id: Optional[int] = None
    category_type: Optional[str] = None
    default_label: Optional[str] = None
    icon: Optional[str] = None
    color: Optional[str] = None

class CategoryResponse(CategoryBase):
    category_id: int
    created_at: datetime.datetime
    effective_label: Optional[str] = None
    full_path: Optional[str] = None
    level: int = 1
    model_config = ConfigDict(from_attributes=True)

class CategoryTreeResponse(CategoryResponse):
    subcategories: List['CategoryTreeResponse'] = []

# Cashflow Payment Schemas
class CashflowPaymentCreate(BaseModel):
    account_id: int
    amount: float

class CashflowPaymentResponse(BaseModel):
    payment_id: int
    cashflow_id: int
    account_id: int
    account_name: Optional[str] = None
    amount: float
    model_config = ConfigDict(from_attributes=True)

# Cashflow Item Schemas
class CashflowItemCreate(BaseModel):
    category_id: int
    amount: float
    label: Optional[str] = None # ESSENTIAL, DISCRETIONARY, LUXURY, INVESTMENT
    description: Optional[str] = None

class CashflowItemResponse(BaseModel):
    item_id: int
    cashflow_id: int
    category_id: int
    category_name: Optional[str] = None
    category_type: Optional[str] = None
    amount: float
    label: Optional[str] = None
    effective_label: Optional[str] = None
    description: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)

# Cashflow Transaction Schemas
class CashflowTransactionCreate(BaseModel):
    transaction_date: datetime.date
    title: str
    total_amount: float
    currency: str = "EUR"
    notes: Optional[str] = None
    payments: List[CashflowPaymentCreate]
    items: List[CashflowItemCreate]

class CashflowTransactionUpdate(BaseModel):
    transaction_date: Optional[datetime.date] = None
    title: Optional[str] = None
    total_amount: Optional[float] = None
    currency: Optional[str] = None
    notes: Optional[str] = None
    payments: Optional[List[CashflowPaymentCreate]] = None
    items: Optional[List[CashflowItemCreate]] = None

class CashflowTransactionResponse(BaseModel):
    cashflow_id: int
    transaction_date: datetime.date
    title: str
    total_amount: float
    currency: str = "EUR"
    notes: Optional[str] = None
    created_at: datetime.datetime
    payments: List[CashflowPaymentResponse] = []
    items: List[CashflowItemResponse] = []
    model_config = ConfigDict(from_attributes=True)

class CashflowSummaryResponse(BaseModel):
    total_income: float
    total_expenses: float
    total_invested: float
    net_savings: float
    savings_rate_pct: float
    breakdown_by_label: Dict[str, float] = {}
    top_expense_categories: List[Dict[str, Any]] = []

# Sankey Schemas
class SankeyNode(BaseModel):
    id: str
    name: str
    category_type: Optional[str] = None
    level: int = 1
    color: Optional[str] = None

class SankeyLink(BaseModel):
    source: str
    target: str
    value: float
    color: Optional[str] = None

class SankeyDataResponse(BaseModel):
    nodes: List[SankeyNode]
    links: List[SankeyLink]
    total_income: float
    total_expenses: float
    total_investments: float
    depth: int = 2

