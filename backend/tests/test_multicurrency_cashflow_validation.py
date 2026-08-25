import datetime
import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from app.db.database import Base
from app.db.models import Account, Category, User
from app.schemas.schemas import CashflowTransactionCreate, CashflowPaymentCreate, CashflowItemCreate
from app.api.routers.cashflow import create_cashflow_transaction

@pytest.mark.anyio
async def test_server_validation_rejects_unbalanced_cashflow():
    test_engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        
    TestSession = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)
    
    async with TestSession() as session:
        # 1. Create account & category
        acc = Account(account_name="Checking", account_type="bank", currency="EUR")
        cat = Category(name="Groceries", category_type="EXPENSE", default_label="ESSENTIAL")
        session.add_all([acc, cat])
        await session.commit()
        await session.refresh(acc)
        await session.refresh(cat)

        dummy_user = User(user_id=1, username="test_user", password_hash="hash")

        # Unbalanced: Payment is -50 EUR, but Item is 100 EUR
        tx_unbalanced = CashflowTransactionCreate(
            transaction_date=datetime.date(2025, 1, 1),
            title="Unbalanced Grocery",
            currency="EUR",
            payments=[CashflowPaymentCreate(account_id=acc.account_id, amount=-50.0)],
            items=[CashflowItemCreate(category_id=cat.category_id, amount=100.0, description="Items")]
        )

        with pytest.raises(HTTPException) as exc_info:
            await create_cashflow_transaction(tx_unbalanced, db=session, current_user=dummy_user)
        assert exc_info.value.status_code == 400
        assert "do not match category allocations" in exc_info.value.detail

@pytest.mark.anyio
async def test_multicurrency_transfer_validation():
    test_engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        
    TestSession = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)
    
    async with TestSession() as session:
        # EUR account (rate 1.0) and USD account (rate 0.92)
        acc_eur = Account(account_name="EUR Bank", account_type="bank", currency="EUR")
        acc_usd = Account(account_name="USD Bank", account_type="bank", currency="USD")
        trans_cat = Category(name="Internal Transfer", category_type="TRANSFER", default_label="ESSENTIAL")
        session.add_all([acc_eur, acc_usd, trans_cat])
        await session.commit()
        await session.refresh(acc_eur)
        await session.refresh(acc_usd)
        await session.refresh(trans_cat)

        dummy_user = User(user_id=1, username="test_user", password_hash="hash")

        # 1. Valid transfer: -100 EUR (100 EUR) -> +108.70 USD (100 EUR)
        valid_transfer = CashflowTransactionCreate(
            transaction_date=datetime.date(2025, 1, 2),
            title="EUR to USD FX Transfer",
            currency="EUR",
            transaction_kind="TRANSFER",
            payments=[
                CashflowPaymentCreate(account_id=acc_eur.account_id, amount=-100.0),
                CashflowPaymentCreate(account_id=acc_usd.account_id, amount=108.70)
            ],
            items=[CashflowItemCreate(category_id=trans_cat.category_id, amount=100.0, description="Transfer")]
        )
        res = await create_cashflow_transaction(valid_transfer, db=session, current_user=dummy_user)
        assert res.transaction_kind == "TRANSFER"

        # 2. Divergent invalid transfer: -100 EUR (100 EUR) -> +50 USD (46 EUR) -> >5% difference
        invalid_transfer = CashflowTransactionCreate(
            transaction_date=datetime.date(2025, 1, 3),
            title="Bad FX Transfer",
            currency="EUR",
            transaction_kind="TRANSFER",
            payments=[
                CashflowPaymentCreate(account_id=acc_eur.account_id, amount=-100.0),
                CashflowPaymentCreate(account_id=acc_usd.account_id, amount=50.0)
            ],
            items=[CashflowItemCreate(category_id=trans_cat.category_id, amount=100.0, description="Transfer")]
        )
        with pytest.raises(HTTPException) as exc_info:
            await create_cashflow_transaction(invalid_transfer, db=session, current_user=dummy_user)
        assert exc_info.value.status_code == 400
        assert "differ by more than 5% FX tolerance" in exc_info.value.detail
