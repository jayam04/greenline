import { describe, it, expect } from 'vitest';
import React from 'react';
import { render, screen } from '@testing-library/react';

interface MockItem {
  name: string;
  category: string;
  amount: number;
  type: 'INVESTMENT' | 'EXPENSE' | 'INCOME';
}

function TestTransactionsLedger({ items }: { items: MockItem[] }) {
  return (
    <div>
      <h2>Unified Cashflow Ledger</h2>
      <table>
        <thead>
          <tr>
            <th>Description</th>
            <th>Category</th>
            <th>Type</th>
            <th>Amount</th>
          </tr>
        </thead>
        <tbody>
          {items.map((item, idx) => (
            <tr key={idx} data-testid={`tx-row-${idx}`}>
              <td>{item.name}</td>
              <td>{item.category}</td>
              <td>
                <span data-testid={`badge-${item.type}`}>{item.type}</span>
              </td>
              <td>{item.amount < 0 ? `-₹${Math.abs(item.amount).toFixed(2)}` : `+₹${item.amount.toFixed(2)}`}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

describe('Transactions Ledger Itemization Component', () => {
  it('correctly displays trade gross vs fee and tax line items', () => {
    const tradeItems: MockItem[] = [
      { name: 'GROWW.BO Stock Purchase (186 @ ₹162)', category: 'Stock & ETF Purchases', amount: -30132.00, type: 'INVESTMENT' },
      { name: 'Brokerage & Exchange Fees', category: 'Investment Fees & Charges', amount: -602.64, type: 'EXPENSE' },
      { name: 'STT & Stamp Duties', category: 'Taxes & Duties', amount: -113.00, type: 'EXPENSE' },
    ];

    render(<TestTransactionsLedger items={tradeItems} />);

    expect(screen.getByText('Unified Cashflow Ledger')).toBeInTheDocument();
    expect(screen.getByText('GROWW.BO Stock Purchase (186 @ ₹162)')).toBeInTheDocument();
    expect(screen.getByText('Brokerage & Exchange Fees')).toBeInTheDocument();
    expect(screen.getByText('STT & Stamp Duties')).toBeInTheDocument();
    expect(screen.getByText('-₹30132.00')).toBeInTheDocument();
    expect(screen.getByText('-₹602.64')).toBeInTheDocument();
    expect(screen.getByText('-₹113.00')).toBeInTheDocument();
  });
});
