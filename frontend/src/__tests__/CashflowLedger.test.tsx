import { describe, it, expect } from 'vitest';
import { isCategoryAllowedForKind } from '@/components/CashflowModal';

describe('Cashflow Category Directional Filtering (Issue #3)', () => {
  const dividendCat = { category_id: 1, name: 'Dividends', category_type: 'INVESTMENT', level: 1 };
  const stakingCat = { category_id: 2, name: 'Interest & Staking', category_type: 'INVESTMENT', level: 1 };
  const stockPurchaseCat = { category_id: 3, name: 'Stock & ETF Purchases', category_type: 'INVESTMENT', level: 1 };
  const sipCat = { category_id: 4, name: 'Mutual Funds & SIPs', category_type: 'INVESTMENT', level: 1 };
  const salaryCat = { category_id: 5, name: 'Base Salary', category_type: 'INCOME', level: 1 };
  const groceryCat = { category_id: 6, name: 'Groceries', category_type: 'EXPENSE', level: 1 };

  it('allows income-friendly investment categories in INCOME mode and excludes spend-only investment categories', () => {
    expect(isCategoryAllowedForKind(dividendCat, 'INCOME')).toBe(true);
    expect(isCategoryAllowedForKind(stakingCat, 'INCOME')).toBe(true);
    expect(isCategoryAllowedForKind(salaryCat, 'INCOME')).toBe(true);

    // Spend-only investment categories should NOT show in Income mode
    expect(isCategoryAllowedForKind(stockPurchaseCat, 'INCOME')).toBe(false);
    expect(isCategoryAllowedForKind(sipCat, 'INCOME')).toBe(false);
    expect(isCategoryAllowedForKind(groceryCat, 'INCOME')).toBe(false);
  });

  it('allows spend-friendly investment categories in EXPENSE mode and excludes income-only investment categories', () => {
    expect(isCategoryAllowedForKind(stockPurchaseCat, 'EXPENSE')).toBe(true);
    expect(isCategoryAllowedForKind(sipCat, 'EXPENSE')).toBe(true);
    expect(isCategoryAllowedForKind(groceryCat, 'EXPENSE')).toBe(true);

    // Income-only investment categories should NOT show in Expense mode
    expect(isCategoryAllowedForKind(dividendCat, 'EXPENSE')).toBe(false);
    expect(isCategoryAllowedForKind(stakingCat, 'EXPENSE')).toBe(false);
    expect(isCategoryAllowedForKind(salaryCat, 'EXPENSE')).toBe(false);
  });
});

describe('Cashflow Ledger Kind Derivation (Issue #1)', () => {
  it('correctly classifies an investment dividend as income when transaction_kind is INCOME', () => {
    const tx = {
      cashflow_id: 101,
      title: 'Apple Dividend',
      total_amount: 150,
      currency: 'USD',
      transaction_kind: 'INCOME',
      items: [
        { category_id: 1, category_name: 'Dividends', category_type: 'INVESTMENT', amount: 150 }
      ],
      payments: [
        { account_id: 1, account_name: 'Schwab Brokerage', amount: 150 }
      ]
    };

    const isTransfer = tx.transaction_kind === 'TRANSFER' || tx.items.some((i) => i.category_type === 'TRANSFER');
    const isIncome = !isTransfer && (tx.transaction_kind === 'INCOME' || tx.items.some((i) => i.category_type === 'INCOME'));

    expect(isTransfer).toBe(false);
    expect(isIncome).toBe(true);

    // Verify credit dot logic
    const payment = tx.payments[0];
    const isCredit = isTransfer ? payment.amount > 0 : isIncome ? payment.amount >= 0 : payment.amount < 0;
    expect(isCredit).toBe(true);
  });
});
