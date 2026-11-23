import datetime

from sqlalchemy.dialects import oracle

from app.db.models import CashflowTransaction
from app.api.routers.cashflow import (
    _build_paginated_cashflow_statement,
    _build_preceding_trade_balance_statement,
)


def test_preceding_trade_balance_query_aggregates_by_account_in_oracle():
    statement = _build_preceding_trade_balance_statement(23, datetime.date(2026, 1, 5))
    sql = str(statement.compile(dialect=oracle.dialect())).upper()

    assert "SUM(" in sql
    assert "GROUP BY" in sql
    assert "TRANSACTIONS.USER_ID" in sql
    assert "TRANSACTIONS.TRANSACTION_DATE" in sql
    assert "TRANSACTIONS.TRANSACTION_ID" not in sql


def test_paginated_cashflow_query_returns_total_count_with_page_rows():
    statement = _build_paginated_cashflow_statement(
        [CashflowTransaction.user_id == 23],
        offset=80,
        page_size=20,
    )
    sql = str(statement.compile(dialect=oracle.dialect())).upper()

    assert "COUNT(*) OVER ()" in sql
    assert "OFFSET" in sql and "FETCH FIRST" in sql
