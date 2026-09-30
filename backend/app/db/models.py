import datetime
from sqlalchemy import (
    Column, Integer, String, Float, Date, DateTime, ForeignKey, 
    UniqueConstraint, Text, Index, Boolean
)
from sqlalchemy.orm import relationship
from app.db.database import Base

class User(Base):
    __tablename__ = "users"
    
    user_id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class Account(Base):
    __tablename__ = "accounts"
    
    account_id = Column(Integer, primary_key=True, index=True)
    account_name = Column(String, nullable=False)
    broker_name = Column(String, nullable=True)
    account_type = Column(String, nullable=False) # demat, mutual_fund, pf, nps, crypto_exchange, bank
    currency = Column(String(3), default="USD")
    default_dividend_account_id = Column(Integer, ForeignKey("accounts.account_id", ondelete="SET NULL"), nullable=True)
    created_at = Column(Date, default=datetime.date.today)

    transactions = relationship("Transaction", back_populates="account", foreign_keys="[Transaction.account_id]", cascade="all, delete-orphan")
    lots = relationship("Lot", back_populates="account", cascade="all, delete-orphan")
    dividends = relationship("Dividend", back_populates="account", cascade="all, delete-orphan")
    default_dividend_account = relationship("Account", foreign_keys=[default_dividend_account_id], remote_side="Account.account_id")

class Asset(Base):
    __tablename__ = "assets"
    
    asset_id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String, index=True, nullable=False) # e.g. AAPL, RELIANCE
    isin = Column(String, index=True, nullable=True)
    name = Column(String, nullable=False)
    asset_type = Column(String, nullable=False) # stock, etf, mutual_fund, bond, fd, crypto, gold
    exchange = Column(String, nullable=True) # NSE, BSE, NASDAQ, NYSE, etc.
    sector = Column(String, nullable=True)
    industry = Column(String, nullable=True)
    currency = Column(String(3), default="USD")

    transactions = relationship("Transaction", back_populates="asset", cascade="all, delete-orphan")
    lots = relationship("Lot", back_populates="asset", cascade="all, delete-orphan")
    price_history = relationship("PriceHistory", back_populates="asset", cascade="all, delete-orphan")
    dividends = relationship("Dividend", back_populates="asset", cascade="all, delete-orphan")
    corporate_actions = relationship("CorporateAction", back_populates="asset", cascade="all, delete-orphan")

class Transaction(Base):
    __tablename__ = "transactions"
    
    transaction_id = Column(Integer, primary_key=True, index=True)
    account_id = Column(Integer, ForeignKey("accounts.account_id", ondelete="CASCADE"), nullable=False)
    funding_account_id = Column(Integer, ForeignKey("accounts.account_id", ondelete="SET NULL"), nullable=True)
    asset_id = Column(Integer, ForeignKey("assets.asset_id", ondelete="CASCADE"), nullable=True) # Null for cash-only entries
    transaction_type = Column(String, nullable=False) # buy, sell, dividend, bonus, split, interest, fee, deposit, withdrawal
    transaction_date = Column(Date, nullable=False, index=True)
    quantity = Column(Float, nullable=True) # Null for cash-only entries
    price_per_unit = Column(Float, nullable=True)
    total_amount = Column(Float, nullable=False) # quantity * price +- charges
    fees = Column(Float, default=0.0)
    taxes = Column(Float, default=0.0)
    source = Column(String, default="manual") # manual, yfinance_auto, csv_import
    notes = Column(Text, nullable=True)
    expected_dividend_id = Column(Integer, ForeignKey("expected_dividends.expected_dividend_id", ondelete="SET NULL"), nullable=True, index=True)

    account = relationship("Account", back_populates="transactions", foreign_keys=[account_id])
    funding_account = relationship("Account", foreign_keys=[funding_account_id])
    asset = relationship("Asset", back_populates="transactions")
    buy_lots = relationship("Lot", back_populates="buy_transaction", foreign_keys="Lot.buy_transaction_id", cascade="all, delete-orphan")
    sell_lot_sales = relationship("LotSale", back_populates="sell_transaction", foreign_keys="LotSale.sell_transaction_id", cascade="all, delete-orphan")

class Lot(Base):
    __tablename__ = "lots"
    
    lot_id = Column(Integer, primary_key=True, index=True)
    account_id = Column(Integer, ForeignKey("accounts.account_id", ondelete="CASCADE"), nullable=False)
    asset_id = Column(Integer, ForeignKey("assets.asset_id", ondelete="CASCADE"), nullable=False)
    buy_transaction_id = Column(Integer, ForeignKey("transactions.transaction_id", ondelete="CASCADE"), nullable=False)
    buy_date = Column(Date, nullable=False)
    quantity_original = Column(Float, nullable=False)
    quantity_remaining = Column(Float, nullable=False)
    cost_per_unit = Column(Float, nullable=False) # Includes fees/taxes, adjusted for splits/bonus

    account = relationship("Account", back_populates="lots")
    asset = relationship("Asset", back_populates="lots")
    buy_transaction = relationship("Transaction", foreign_keys=[buy_transaction_id], back_populates="buy_lots")
    lot_sales = relationship("LotSale", back_populates="lot", cascade="all, delete-orphan")

class LotSale(Base):
    __tablename__ = "lot_sales"
    
    lot_sale_id = Column(Integer, primary_key=True, index=True)
    lot_id = Column(Integer, ForeignKey("lots.lot_id"), nullable=False)
    sell_transaction_id = Column(Integer, ForeignKey("transactions.transaction_id"), nullable=False)
    quantity_sold = Column(Float, nullable=False)
    sale_price_per_unit = Column(Float, nullable=False)
    cost_basis = Column(Float, nullable=False) # quantity_sold * lot.cost_per_unit
    realized_pnl = Column(Float, nullable=False) # (sale - cost_basis)
    holding_period_days = Column(Integer, nullable=False) # sale_date - buy_date

    lot = relationship("Lot", back_populates="lot_sales")
    sell_transaction = relationship("Transaction", foreign_keys=[sell_transaction_id], back_populates="sell_lot_sales")

class PriceHistory(Base):
    __tablename__ = "price_history"
    
    price_id = Column(Integer, primary_key=True, index=True)
    asset_id = Column(Integer, ForeignKey("assets.asset_id"), nullable=False)
    price_date = Column(Date, nullable=False)
    close_price = Column(Float, nullable=False)
    source = Column(String, default="manual") # API/manual/yfinance

    asset = relationship("Asset", back_populates="price_history")

    __table_args__ = (
        UniqueConstraint("asset_id", "price_date", name="uix_asset_price_date"),
        Index("idx_price_history_asset_date", "asset_id", "price_date"),
    )

class Dividend(Base):
    __tablename__ = "dividends"
    
    dividend_id = Column(Integer, primary_key=True, index=True)
    asset_id = Column(Integer, ForeignKey("assets.asset_id"), nullable=False)
    account_id = Column(Integer, ForeignKey("accounts.account_id"), nullable=False)
    ex_date = Column(Date, nullable=True)
    pay_date = Column(Date, nullable=False)
    amount_per_share = Column(Float, nullable=True)
    total_amount = Column(Float, nullable=False)
    tax_withheld = Column(Float, default=0.0)

    asset = relationship("Asset", back_populates="dividends")
    account = relationship("Account", back_populates="dividends")

class ExpectedDividend(Base):
    __tablename__ = "expected_dividends"
    
    expected_dividend_id = Column(Integer, primary_key=True, index=True)
    asset_id = Column(Integer, ForeignKey("assets.asset_id", ondelete="CASCADE"), nullable=False, index=True)
    account_id = Column(Integer, ForeignKey("accounts.account_id", ondelete="CASCADE"), nullable=False, index=True)
    ex_date = Column(Date, nullable=False, index=True)
    pay_date = Column(Date, nullable=True)
    eligible_shares = Column(Float, nullable=False, default=0.0)
    dividend_rate = Column(Float, nullable=False, default=0.0)
    expected_amount = Column(Float, nullable=False, default=0.0)
    currency = Column(String(3), nullable=False, default="USD")
    source = Column(String, default="yfinance")
    matched_transaction_id = Column(Integer, ForeignKey("transactions.transaction_id", ondelete="SET NULL"), nullable=True, index=True)
    status = Column(String, nullable=False, default="UNMATCHED") # UNMATCHED, MATCHED, AMOUNT_MISMATCH, DISMISSED, ORPHAN
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    asset = relationship("Asset")
    account = relationship("Account")
    matched_transaction = relationship("Transaction", foreign_keys=[matched_transaction_id])

    __table_args__ = (
        UniqueConstraint("asset_id", "account_id", "ex_date", name="uix_expected_dividend_asset_account_date"),
    )

class CorporateAction(Base):
    __tablename__ = "corporate_actions"
    
    action_id = Column(Integer, primary_key=True, index=True)
    asset_id = Column(Integer, ForeignKey("assets.asset_id"), nullable=False)
    action_type = Column(String, nullable=False) # split, bonus, merger, spinoff, name_change
    action_date = Column(Date, nullable=False)
    ratio = Column(String, nullable=False) # e.g. "2:1" or "1:2"
    notes = Column(Text, nullable=True)

    asset = relationship("Asset", back_populates="corporate_actions")

class CashFlow(Base):
    __tablename__ = "cash_flows"
    
    cash_flow_id = Column(Integer, primary_key=True, index=True)
    scope_type = Column(String, nullable=False) # portfolio, account, asset
    scope_id = Column(Integer, nullable=True) # account_id or asset_id depending on scope_type
    flow_date = Column(Date, nullable=False)
    amount = Column(Float, nullable=False) # Negative = money in (buy/deposit), Positive = money out (sell/withdrawal/dividend)
    flow_type = Column(String, nullable=False) # buy, sell, dividend, deposit, withdrawal, mark_to_market

    __table_args__ = (
        Index("idx_cash_flows_scope_date", "scope_type", "scope_id", "flow_date"),
    )

class NetworthSnapshot(Base):
    __tablename__ = "networth_snapshots"
    
    snapshot_id = Column(Integer, primary_key=True, index=True)
    snapshot_date = Column(Date, unique=True, nullable=False)
    total_invested = Column(Float, nullable=False)
    total_current_value = Column(Float, nullable=False)
    cash_balance = Column(Float, nullable=False)
    total_realized_pnl = Column(Float, nullable=False)
    total_unrealized_pnl = Column(Float, nullable=False)
    net_worth = Column(Float, nullable=False)

    asset_class_breakdowns = relationship("NetworthByAssetClass", back_populates="snapshot", cascade="all, delete-orphan")

class NetworthByAssetClass(Base):
    __tablename__ = "networth_by_asset_class"
    
    id = Column(Integer, primary_key=True, index=True)
    snapshot_id = Column(Integer, ForeignKey("networth_snapshots.snapshot_id"), nullable=False)
    asset_class = Column(String, nullable=False) # stock, etf, mutual_fund, gold, crypto, fd, cash
    value = Column(Float, nullable=False)

    snapshot = relationship("NetworthSnapshot", back_populates="asset_class_breakdowns")

class Benchmark(Base):
    __tablename__ = "benchmarks"
    
    id = Column(Integer, primary_key=True, index=True)
    benchmark_name = Column(String, nullable=False) # e.g. S&P 500, Nifty 50
    price_date = Column(Date, nullable=False)
    close_value = Column(Float, nullable=False)

    __table_args__ = (
        UniqueConstraint("benchmark_name", "price_date", name="uix_benchmark_name_date"),
    )

class XIRRCache(Base):
    __tablename__ = "xirr_cache"
    
    id = Column(Integer, primary_key=True, index=True)
    scope_type = Column(String, nullable=False) # portfolio, account, asset
    scope_id = Column(Integer, nullable=True)
    as_of_date = Column(Date, nullable=False)
    xirr_value = Column(Float, nullable=False)
    computed_at = Column(DateTime, default=datetime.datetime.utcnow)

# Income & Expense Cashflow Models
class Category(Base):
    __tablename__ = "categories"

    category_id = Column(Integer, primary_key=True, index=True)
    parent_id = Column(Integer, ForeignKey("categories.category_id", ondelete="SET NULL"), nullable=True)
    name = Column(String, nullable=False, index=True)
    category_type = Column(String, nullable=False, default="EXPENSE") # INCOME, EXPENSE, INVESTMENT, TRANSFER
    default_label = Column(String, nullable=True) # ESSENTIAL, DISCRETIONARY, LUXURY, INVESTMENT
    icon = Column(String, nullable=True)
    color = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    parent = relationship("Category", remote_side=[category_id], back_populates="subcategories")
    subcategories = relationship("Category", back_populates="parent")
    items = relationship("CashflowItem", back_populates="category")

class CashflowTransaction(Base):
    __tablename__ = "cashflow_transactions"

    cashflow_id = Column(Integer, primary_key=True, index=True)
    transaction_date = Column(Date, nullable=False, index=True)
    title = Column(String, nullable=False)
    total_amount = Column(Float, nullable=False)
    currency = Column(String(3), default="EUR")
    transaction_kind = Column(String, nullable=True, default=None)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    payments = relationship("CashflowPayment", back_populates="cashflow_transaction", cascade="all, delete-orphan", lazy="selectin")
    items = relationship("CashflowItem", back_populates="cashflow_transaction", cascade="all, delete-orphan", lazy="selectin")

class CashflowPayment(Base):
    __tablename__ = "cashflow_payments"

    payment_id = Column(Integer, primary_key=True, index=True)
    cashflow_id = Column(Integer, ForeignKey("cashflow_transactions.cashflow_id", ondelete="CASCADE"), nullable=False)
    account_id = Column(Integer, ForeignKey("accounts.account_id", ondelete="CASCADE"), nullable=False)
    amount = Column(Float, nullable=False)

    cashflow_transaction = relationship("CashflowTransaction", back_populates="payments")
    account = relationship("Account", lazy="selectin")

class CashflowItem(Base):
    __tablename__ = "cashflow_items"

    item_id = Column(Integer, primary_key=True, index=True)
    cashflow_id = Column(Integer, ForeignKey("cashflow_transactions.cashflow_id", ondelete="CASCADE"), nullable=False)
    category_id = Column(Integer, ForeignKey("categories.category_id", ondelete="RESTRICT"), nullable=False)
    amount = Column(Float, nullable=False)
    label = Column(String, nullable=True) # Overrides category default_label if set (ESSENTIAL, DISCRETIONARY, LUXURY, INVESTMENT)
    description = Column(String, nullable=True)

    cashflow_transaction = relationship("CashflowTransaction", back_populates="items")
    category = relationship("Category", back_populates="items", lazy="selectin")

class AppSetting(Base):
    __tablename__ = "app_settings"

    key = Column(String, primary_key=True, index=True)
    value = Column(Text, nullable=False)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

class ImportBatch(Base):
    __tablename__ = "import_batches"

    batch_id = Column(Integer, primary_key=True, index=True)
    filename = Column(String, nullable=False)
    file_type = Column(String, nullable=False)  # pdf, csv, xlsx, image, json
    file_size_bytes = Column(Integer, default=0)
    status = Column(String, nullable=False, default="processing")  # processing, ready_for_review, partially_merged, merged, discarded, failed
    scope = Column(String, nullable=False, default="unified")

    target_account_id = Column(Integer, ForeignKey("accounts.account_id", ondelete="SET NULL"), nullable=True)
    default_currency = Column(String(3), default="USD")
    custom_instructions = Column(Text, nullable=True)

    progress_pct = Column(Integer, default=0)
    current_step = Column(String, nullable=True)
    error_message = Column(Text, nullable=True)

    total_records = Column(Integer, default=0)
    new_records = Column(Integer, default=0)
    exact_matches = Column(Integer, default=0)
    probable_matches = Column(Integer, default=0)

    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    target_account = relationship("Account")
    records = relationship("StagedRecord", back_populates="batch", cascade="all, delete-orphan", lazy="selectin")

class StagedRecord(Base):
    __tablename__ = "staged_records"

    staged_id = Column(Integer, primary_key=True, index=True)
    batch_id = Column(Integer, ForeignKey("import_batches.batch_id", ondelete="CASCADE"), nullable=False, index=True)

    record_type = Column(String, nullable=False)  # investment | cashflow
    review_status = Column(String, nullable=False, default="pending")  # approved, pending, skipped, modified
    match_status = Column(String, nullable=False, default="new")  # new, exact_match, probable_match

    matched_entity_id = Column(Integer, nullable=True)  # transaction_id or cashflow_id
    matched_entity_details = Column(Text, nullable=True)  # JSON snapshot of existing transaction

    confidence_score = Column(Float, default=1.0)

    # Normalized fields
    transaction_date = Column(Date, nullable=False, index=True)
    action_type = Column(String, nullable=False)  # buy, sell, dividend, split, income, expense, transfer

    account_id = Column(Integer, ForeignKey("accounts.account_id", ondelete="SET NULL"), nullable=True)
    account_name_raw = Column(String, nullable=True)

    asset_id = Column(Integer, ForeignKey("assets.asset_id", ondelete="SET NULL"), nullable=True)
    asset_symbol_raw = Column(String, nullable=True)
    asset_name_raw = Column(String, nullable=True)

    category_id = Column(Integer, ForeignKey("categories.category_id", ondelete="SET NULL"), nullable=True)
    category_name_raw = Column(String, nullable=True)

    quantity = Column(Float, nullable=True)
    price_per_unit = Column(Float, nullable=True)
    total_amount = Column(Float, nullable=False)
    fees = Column(Float, default=0.0)
    taxes = Column(Float, default=0.0)
    currency = Column(String(3), default="USD")
    notes = Column(Text, nullable=True)
    source_raw_text = Column(Text, nullable=True)

    batch = relationship("ImportBatch", back_populates="records")
    account = relationship("Account", lazy="selectin")
    asset = relationship("Asset", lazy="selectin")
    category = relationship("Category", lazy="selectin")

    __table_args__ = (
        Index("ix_staged_records_batch_status", "batch_id", "review_status"),
    )

class ApiKey(Base):
    __tablename__ = "api_keys"

    key_id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False)
    name = Column(String, nullable=False)
    key_prefix = Column(String, nullable=False) # e.g. gl_mcp_3a9f...
    key_hash = Column(String, nullable=False, unique=True, index=True) # SHA-256 hex digest
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    last_used_at = Column(DateTime, nullable=True)

    user = relationship("User", lazy="selectin")

