from typing import Any, Optional, Set, Tuple

FX_RATES_TO_EUR = {
    "EUR": 1.0,
    "USD": 0.92,
    "INR": 0.0102,
    "GBP": 1.17,
    "CAD": 0.67,
    "AUD": 0.60,
    "JPY": 0.0059,
    "CHF": 1.06,
    "SGD": 0.68,
}

def convert_currency(amount: float, from_currency: str = "EUR", to_currency: str = "EUR") -> float:
    if not amount:
        return 0.0
    src = (from_currency or "EUR").strip().upper()
    dst = (to_currency or "EUR").strip().upper()
    if src == dst:
        return amount
    rate_from = FX_RATES_TO_EUR.get(src, 1.0)
    rate_to = FX_RATES_TO_EUR.get(dst, 1.0)
    in_eur = amount * rate_from
    return in_eur / rate_to

def convert_currency_to_eur(amount: float, from_currency: str = "EUR") -> float:
    return convert_currency(amount, from_currency, "EUR")

def compute_transaction_cash_movement(tx: Any, valid_account_ids: Optional[Set[int]] = None) -> Tuple[Optional[int], float]:
    """
    Computes (cash_account_id, signed_cash_change) for an investment transaction.
    - Cash account: funding_account_id if valid, otherwise tx.account_id.
    - Buy: Outflow -(qty * ppu + fees + taxes) or -total_amount.
    - Sell: Inflow (qty * ppu - fees - taxes) or (total_amount - fees - taxes).
    - Dividend: Inflow total_amount - taxes.
    - Interest: Inflow total_amount - fees - taxes.
    - Deposit: Inflow total_amount - fees - taxes.
    - Withdrawal / Fee: Outflow -(total_amount + fees + taxes).
    """
    funding_id = getattr(tx, "funding_account_id", None)
    if funding_id and (valid_account_ids is None or funding_id in valid_account_ids):
        cash_acc_id = funding_id
    else:
        cash_acc_id = getattr(tx, "account_id", None)

    ttype = (getattr(tx, "transaction_type", None) or "").lower()
    qty = float(getattr(tx, "quantity", None) or 0.0)
    ppu = float(getattr(tx, "price_per_unit", None) or 0.0)
    amt = float(getattr(tx, "total_amount", None) or 0.0)
    fees = float(getattr(tx, "fees", None) or 0.0)
    taxes = float(getattr(tx, "taxes", None) or 0.0)

    if ttype == "buy":
        trade_cash = (qty * ppu + fees + taxes) if (qty > 0 and ppu > 0) else amt
        return cash_acc_id, -trade_cash
    elif ttype == "sell":
        trade_cash = (qty * ppu - fees - taxes) if (qty > 0 and ppu > 0) else (amt - fees - taxes)
        return cash_acc_id, trade_cash
    elif ttype == "dividend":
        if not funding_id:
            return None, 0.0
        trade_cash = amt - taxes
        return cash_acc_id, trade_cash
    elif ttype == "interest":
        trade_cash = amt - fees - taxes
        return cash_acc_id, trade_cash
    elif ttype == "deposit":
        trade_cash = amt - fees - taxes
        return cash_acc_id, trade_cash
    elif ttype in ["withdrawal", "fee"]:
        trade_cash = (amt + fees + taxes) if (fees > 0 or taxes > 0) else amt
        return cash_acc_id, -trade_cash

    return cash_acc_id, 0.0

def resolve_transaction_kind(tx: Any) -> str:
    """
    Canonical derivation of transaction kind (TRANSFER, INCOME, EXPENSE).
    """
    items = getattr(tx, "items", []) or []

    is_trans = getattr(tx, "transaction_kind", None) == "TRANSFER" or any(
        (i.category and i.category.category_type == "TRANSFER") if hasattr(i, "category") else (getattr(i, "category_type", None) == "TRANSFER")
        for i in items
    )
    if is_trans:
        return "TRANSFER"

    is_inc = getattr(tx, "transaction_kind", None) == "INCOME" or any(
        (i.category and i.category.category_type == "INCOME") if hasattr(i, "category") else (getattr(i, "category_type", None) == "INCOME")
        for i in items
    )
    if is_inc:
        return "INCOME"

    t_kind = getattr(tx, "transaction_kind", None)
    if t_kind:
        return t_kind

    return "EXPENSE"
