import datetime
from sqlalchemy import (
    Column, Integer, Identity, String as SQLString, Float, Date, DateTime, ForeignKey,
    UniqueConstraint, Text, Index
)
from sqlalchemy.orm import relationship
try:
    from .database import Base
except (ImportError, ValueError):
    from app.db.database import Base


class String(SQLString):
    """Use a bounded default width so Oracle can index string columns safely."""

    def __init__(self, length=255, **kwargs):
        super().__init__(length=length, **kwargs)


class User(Base):
    __tablename__ = "users"

    user_id = Column(Integer, Identity(), primary_key=True)
    auth0_sub = Column(String(255), unique=True, nullable=True, index=True)
    email = Column(String(255), nullable=True, index=True)
    name = Column(String(255), nullable=True)
    picture = Column(String(1024), nullable=True)
    username = Column(String(255), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    def __init__(self, **kwargs):
        if "user_id" in kwargs and kwargs["user_id"] is None:
            del kwargs["user_id"]
        elif "user_id" not in kwargs and "auth0_sub" not in kwargs:
            kwargs["user_id"] = 0
        super().__init__(**kwargs)


class Account(Base):
    __tablename__ = "accounts"

    account_id = Column(Integer, Identity(), primary_key=True)
    user_id = Column(Integer, ForeignKey("users.user_id", ondelete="CASCADE"), default=0, server_default="0", nullable=False, index=True)
    account_name = Column(String, nullable=False)
    broker_name = Column(String, nullable=True)
    account_type = Column(String, nullable=False)  # demat, mutual_fund, pf, nps, crypto_exchange, bank
    currency = Column(String(3), default="USD")
    default_dividend_account_id = Column(Integer, ForeignKey("accounts.account_id", ondelete="SET NULL"), nullable=True)
    created_at = Column(Date, default=datetime.date.today)

    transactions = relationship("Transaction", back_populates="account", foreign_keys="[Transaction.account_id]", cascade="all, delete-orphan")
    lots = relationship("Lot", back_populates="account", cascade="all, delete-orphan")
    dividends = relationship("Dividend", back_populates="account", cascade="all, delete-orphan")
    default_dividend_account = relationship("Account", foreign_keys=[default_dividend_account_id], remote_side="Account.account_id")


class Asset(Base):
    __tablename__ = "assets"

    asset_id = Column(Integer, Identity(), primary_key=True)
    symbol = Column(String, index=True, nullable=False)  # e.g. AAPL, RELIANCE
    isin = Column(String, index=True, nullable=True)
    name = Column(String, nullable=False)
    asset_type = Column(String, nullable=False)  # stock, etf, mutual_fund, bond, fd, crypto, gold
    exchange = Column(String, nullable=True)  # NSE, BSE, NASDAQ, NYSE, etc.
    sector = Column(String, nullable=True)
    industry = Column(String, nullable=True)
    currency = Column(String(3), default="USD")

    transactions = relationship("Transaction", back_populates="asset", cascade="all, delete-orphan")
    lots = relationship("Lot", back_populates="asset", cascade="all, delete-orphan")
    price_history = relationship("PriceHistory", back_populates="asset", cascade="all, delete-orphan")
    dividends = relationship("Dividend", back_populates="asset", cascade="all, delete-orphan")


class Transaction(Base):
    __tablename__ = "transactions"

    transaction_id = Column(Integer, Identity(), primary_key=True)
    user_id = Column(Integer, ForeignKey("users.user_id", ondelete="CASCADE"), default=0, server_default="0", nullable=False, index=True)
    account_id = Column(Integer, ForeignKey("accounts.account_id", ondelete="CASCADE"), nullable=False)
    funding_account_id = Column(Integer, ForeignKey("accounts.account_id", ondelete="SET NULL"), nullable=True)
    asset_id = Column(Integer, ForeignKey("assets.asset_id", ondelete="CASCADE"), nullable=True)
    transaction_type = Column(String, nullable=False)  # buy, sell, dividend, bonus, split, interest, fee, deposit, withdrawal
    transaction_date = Column(Date, nullable=False, index=True)
    quantity = Column(Float, nullable=True)
    price_per_unit = Column(Float, nullable=True)
    total_amount = Column(Float, nullable=False)
    fees = Column(Float, default=0.0)
    taxes = Column(Float, default=0.0)
    source = Column(String, default="manual")
    notes = Column(Text, nullable=True)
    expected_dividend_id = Column(Integer, nullable=True, index=True)

    account = relationship("Account", back_populates="transactions", foreign_keys=[account_id])
    funding_account = relationship("Account", foreign_keys=[funding_account_id])
    asset = relationship("Asset", back_populates="transactions")
    buy_lots = relationship("Lot", back_populates="buy_transaction", foreign_keys="Lot.buy_transaction_id", cascade="all, delete-orphan")
    sell_lot_sales = relationship("LotSale", back_populates="sell_transaction", foreign_keys="LotSale.sell_transaction_id", cascade="all, delete-orphan")


class Lot(Base):
    __tablename__ = "lots"

    lot_id = Column(Integer, Identity(), primary_key=True)
    user_id = Column(Integer, ForeignKey("users.user_id", ondelete="CASCADE"), default=0, server_default="0", nullable=False, index=True)
    account_id = Column(Integer, ForeignKey("accounts.account_id", ondelete="CASCADE"), nullable=False)
    asset_id = Column(Integer, ForeignKey("assets.asset_id", ondelete="CASCADE"), nullable=False)
    buy_transaction_id = Column(Integer, ForeignKey("transactions.transaction_id", ondelete="CASCADE"), nullable=False)
    buy_date = Column(Date, nullable=False)
    quantity_original = Column(Float, nullable=False)
    quantity_remaining = Column(Float, nullable=False)
    cost_per_unit = Column(Float, nullable=False)

    account = relationship("Account", back_populates="lots")
    asset = relationship("Asset", back_populates="lots")
    buy_transaction = relationship("Transaction", foreign_keys=[buy_transaction_id], back_populates="buy_lots")
    lot_sales = relationship("LotSale", back_populates="lot", cascade="all, delete-orphan")


class LotSale(Base):
    __tablename__ = "lot_sales"

    lot_sale_id = Column(Integer, Identity(), primary_key=True)
    user_id = Column(Integer, ForeignKey("users.user_id", ondelete="CASCADE"), default=0, server_default="0", nullable=False, index=True)
    lot_id = Column(Integer, ForeignKey("lots.lot_id"), nullable=False)
    sell_transaction_id = Column(Integer, ForeignKey("transactions.transaction_id"), nullable=False)
    quantity_sold = Column(Float, nullable=False)
    sale_price_per_unit = Column(Float, nullable=False)
    cost_basis = Column(Float, nullable=False)
    realized_pnl = Column(Float, nullable=False)
    holding_period_days = Column(Integer, nullable=False)

    lot = relationship("Lot", back_populates="lot_sales")
    sell_transaction = relationship("Transaction", foreign_keys=[sell_transaction_id], back_populates="sell_lot_sales")


class PriceHistory(Base):
    __tablename__ = "price_history"

    price_id = Column(Integer, Identity(), primary_key=True)
    user_id = Column(Integer, default=0, server_default="0", nullable=False, index=True)
    asset_id = Column(Integer, ForeignKey("assets.asset_id"), nullable=False)
    price_date = Column(Date, nullable=False)
    close_price = Column(Float, nullable=False)
    source = Column(String, default="manual")

    asset = relationship("Asset", back_populates="price_history")

    __table_args__ = (
        UniqueConstraint("asset_id", "price_date", name="uix_asset_price_date"),
    )


class Dividend(Base):
    __tablename__ = "dividends"

    dividend_id = Column(Integer, Identity(), primary_key=True)
    user_id = Column(Integer, ForeignKey("users.user_id", ondelete="CASCADE"), default=0, server_default="0", nullable=False, index=True)
    asset_id = Column(Integer, ForeignKey("assets.asset_id"), nullable=False)
    account_id = Column(Integer, ForeignKey("accounts.account_id"), nullable=False)
    ex_date = Column(Date, nullable=True)
    pay_date = Column(Date, nullable=False)
    amount_per_share = Column(Float, nullable=True)
    total_amount = Column(Float, nullable=False)
    tax_withheld = Column(Float, default=0.0)

    asset = relationship("Asset", back_populates="dividends")
    account = relationship("Account", back_populates="dividends")


class CashFlow(Base):
    __tablename__ = "cash_flows"

    cash_flow_id = Column(Integer, Identity(), primary_key=True)
    user_id = Column(Integer, ForeignKey("users.user_id", ondelete="CASCADE"), default=0, server_default="0", nullable=False, index=True)
    scope_type = Column(String, nullable=False)  # portfolio, account, asset
    scope_id = Column(Integer, nullable=True)
    flow_date = Column(Date, nullable=False)
    amount = Column(Float, nullable=False)
    flow_type = Column(String, nullable=False)

    __table_args__ = (
        Index("idx_cash_flows_scope_date", "scope_type", "scope_id", "flow_date"),
    )


class NetworthSnapshot(Base):
    __tablename__ = "networth_snapshots"

    snapshot_id = Column(Integer, Identity(), primary_key=True)
    user_id = Column(Integer, ForeignKey("users.user_id", ondelete="CASCADE"), default=0, server_default="0", nullable=False, index=True)
    snapshot_date = Column(Date, nullable=False, index=True)
    total_invested = Column(Float, nullable=False)
    total_current_value = Column(Float, nullable=False)
    cash_balance = Column(Float, nullable=False)
    total_realized_pnl = Column(Float, nullable=False)
    total_unrealized_pnl = Column(Float, nullable=False)
    net_worth = Column(Float, nullable=False)

    asset_class_breakdowns = relationship("NetworthByAssetClass", back_populates="snapshot", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("user_id", "snapshot_date", name="uix_snapshot_user_date"),
    )


class NetworthByAssetClass(Base):
    __tablename__ = "networth_by_asset_class"

    id = Column(Integer, Identity(), primary_key=True)
    user_id = Column(Integer, ForeignKey("users.user_id", ondelete="CASCADE"), default=0, server_default="0", nullable=False, index=True)
    snapshot_id = Column(Integer, ForeignKey("networth_snapshots.snapshot_id"), nullable=False)
    asset_class = Column(String, nullable=False)  # stock, etf, mutual_fund, gold, crypto, fd, cash
    value = Column(Float, nullable=False)

    snapshot = relationship("NetworthSnapshot", back_populates="asset_class_breakdowns")


class Benchmark(Base):
    __tablename__ = "benchmarks"

    id = Column(Integer, Identity(), primary_key=True)
    benchmark_name = Column(String, nullable=False)  # e.g. S&P 500, Nifty 50
    price_date = Column(Date, nullable=False)
    close_value = Column(Float, nullable=False)

    __table_args__ = (
        UniqueConstraint("benchmark_name", "price_date", name="uix_benchmark_name_date"),
    )


class XIRRCache(Base):
    __tablename__ = "xirr_cache"

    id = Column(Integer, Identity(), primary_key=True)
    user_id = Column(Integer, ForeignKey("users.user_id", ondelete="CASCADE"), default=0, server_default="0", nullable=False, index=True)
    scope_type = Column(String, nullable=False)  # portfolio, account, asset
    scope_id = Column(Integer, nullable=True)
    as_of_date = Column(Date, nullable=False)
    xirr_value = Column(Float, nullable=False)
    computed_at = Column(DateTime, default=datetime.datetime.utcnow)


class Category(Base):
    __tablename__ = "categories"

    category_id = Column(Integer, Identity(), primary_key=True)
    user_id = Column(Integer, ForeignKey("users.user_id", ondelete="CASCADE"), default=0, server_default="0", nullable=False, index=True)
    parent_id = Column(Integer, ForeignKey("categories.category_id", ondelete="SET NULL"), nullable=True)
    name = Column(String, nullable=False, index=True)
    category_type = Column(String, nullable=False, default="EXPENSE")  # INCOME, EXPENSE, INVESTMENT, TRANSFER
    default_label = Column(String, nullable=True)  # ESSENTIAL, DISCRETIONARY, LUXURY, INVESTMENT
    icon = Column(String, nullable=True)
    color = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    parent = relationship("Category", remote_side=[category_id], back_populates="subcategories")
    subcategories = relationship("Category", back_populates="parent")
    items = relationship("CashflowItem", back_populates="category")


class CashflowTransaction(Base):
    __tablename__ = "cashflow_transactions"

    cashflow_id = Column(Integer, Identity(), primary_key=True)
    user_id = Column(Integer, ForeignKey("users.user_id", ondelete="CASCADE"), default=0, server_default="0", nullable=False, index=True)
    transaction_date = Column(Date, nullable=False, index=True)
    title = Column(String, nullable=False)
    total_amount = Column(Float, nullable=False)
    currency = Column(String(3), default="EUR")
    transaction_kind = Column(String, nullable=True, default=None)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    payments = relationship("CashflowPayment", back_populates="cashflow_transaction", cascade="all, delete-orphan", lazy="selectin", order_by="CashflowPayment.payment_id")
    items = relationship("CashflowItem", back_populates="cashflow_transaction", cascade="all, delete-orphan", lazy="selectin", order_by="CashflowItem.item_id")


class CashflowPayment(Base):
    __tablename__ = "cashflow_payments"

    payment_id = Column(Integer, Identity(), primary_key=True)
    user_id = Column(Integer, ForeignKey("users.user_id", ondelete="CASCADE"), default=0, server_default="0", nullable=False, index=True)
    cashflow_id = Column(Integer, ForeignKey("cashflow_transactions.cashflow_id", ondelete="CASCADE"), nullable=False)
    account_id = Column(Integer, ForeignKey("accounts.account_id", ondelete="CASCADE"), nullable=False)
    amount = Column(Float, nullable=False)

    cashflow_transaction = relationship("CashflowTransaction", back_populates="payments")
    account = relationship("Account", lazy="selectin")


class CashflowItem(Base):
    __tablename__ = "cashflow_items"

    item_id = Column(Integer, Identity(), primary_key=True)
    user_id = Column(Integer, ForeignKey("users.user_id", ondelete="CASCADE"), default=0, server_default="0", nullable=False, index=True)
    cashflow_id = Column(Integer, ForeignKey("cashflow_transactions.cashflow_id", ondelete="CASCADE"), nullable=False)
    category_id = Column(Integer, ForeignKey("categories.category_id"), nullable=False)
    amount = Column(Float, nullable=False)
    label = Column(String, nullable=True)
    description = Column(String, nullable=True)

    cashflow_transaction = relationship("CashflowTransaction", back_populates="items")
    category = relationship("Category", back_populates="items", lazy="selectin")
