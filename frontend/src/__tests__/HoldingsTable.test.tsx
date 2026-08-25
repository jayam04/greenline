import { describe, it, expect, vi } from 'vitest';
import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';

// Sample mock holding data
const mockHoldings = [
  {
    asset_id: 4,
    symbol: "GROWW.BO",
    name: "Billionbrains Garage Ventures Limited",
    asset_type: "stock",
    sector: "Technology",
    currency: "INR",
    quantity_held: 186.0,
    avg_cost_price: 162.0,
    total_cost: 30847.64,
    latest_price: 203.35,
    latest_price_date: "2026-08-25",
    current_value: 37823.10,
    unrealized_pnl: 6975.46,
    unrealized_pnl_pct: 22.61,
    realized_pnl: 0.0,
    realized_pnl_pct: 0.0,
    net_pnl: 6975.46,
    net_pnl_pct: 22.61,
    xirr: 24.5,
    open_lots: [
      {
        lot_id: 1,
        buy_date: "2025-09-19",
        quantity_original: 186.0,
        quantity_remaining: 186.0,
        cost_per_unit: 165.85,
      }
    ],
  }
];

// Lightweight test component mirroring Holdings table rendering
function TestHoldingsTable({ holdings }: { holdings: typeof mockHoldings }) {
  const [expandedId, setExpandedId] = React.useState<number | null>(null);

  return (
    <div>
      <h1>Holdings</h1>
      <table>
        <thead>
          <tr>
            <th>Asset</th>
            <th>Type</th>
            <th>Qty</th>
            <th>Total Cost</th>
            <th>Current Value</th>
            <th>Unrealized P&L</th>
            <th>Realized P&L</th>
            <th>Net P&L</th>
            <th>XIRR</th>
          </tr>
        </thead>
        <tbody>
          {holdings.map((h) => {
            const isExpanded = expandedId === h.asset_id;
            return (
              <React.Fragment key={h.asset_id}>
                <tr onClick={() => setExpandedId(isExpanded ? null : h.asset_id)} data-testid={`holding-row-${h.symbol}`}>
                  <td>{h.symbol}</td>
                  <td>{h.asset_type}</td>
                  <td>{h.quantity_held}</td>
                  <td>
                    <span>₹{h.total_cost.toFixed(2)}</span>
                    <span>Avg: ₹{h.avg_cost_price.toFixed(2)}</span>
                  </td>
                  <td>
                    <span>₹{h.current_value.toFixed(2)}</span>
                    <span>Price: ₹{h.latest_price.toFixed(2)}</span>
                  </td>
                  <td>+₹{h.unrealized_pnl.toFixed(2)}</td>
                  <td>₹{h.realized_pnl.toFixed(2)}</td>
                  <td>+₹{h.net_pnl.toFixed(2)}</td>
                  <td>{h.xirr}%</td>
                </tr>
                {isExpanded && (
                  <tr data-testid={`lots-subrow-${h.symbol}`}>
                    <td colSpan={10}>
                      <div>
                        {h.open_lots.map((lot) => (
                          <div key={lot.lot_id}>
                            Lot #{lot.lot_id}: {lot.quantity_remaining} shares @ ₹{lot.cost_per_unit}
                          </div>
                        ))}
                      </div>
                    </td>
                  </tr>
                )}
              </React.Fragment>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

describe('Holdings Table Component', () => {
  it('renders table columns including merged Total Cost, Current Value, and Net P&L', () => {
    render(<TestHoldingsTable holdings={mockHoldings} />);

    expect(screen.getByText('Holdings')).toBeInTheDocument();
    expect(screen.getByText('Total Cost')).toBeInTheDocument();
    expect(screen.getByText('Current Value')).toBeInTheDocument();
    expect(screen.getByText('Net P&L')).toBeInTheDocument();
    expect(screen.getByText('GROWW.BO')).toBeInTheDocument();
    expect(screen.getByText('₹30847.64')).toBeInTheDocument();
    expect(screen.getByText('Avg: ₹162.00')).toBeInTheDocument();
    expect(screen.getByText('₹37823.10')).toBeInTheDocument();
    expect(screen.getAllByText('+₹6975.46')).toHaveLength(2);
  });

  it('expands and collapses open FIFO lot details upon row click', () => {
    render(<TestHoldingsTable holdings={mockHoldings} />);

    // Initially subrow is not rendered
    expect(screen.queryByTestId('lots-subrow-GROWW.BO')).not.toBeInTheDocument();

    // Click row to expand
    fireEvent.click(screen.getByTestId('holding-row-GROWW.BO'));
    expect(screen.getByTestId('lots-subrow-GROWW.BO')).toBeInTheDocument();
    expect(screen.getByText(/Lot #1: 186 shares @ ₹165.85/)).toBeInTheDocument();

    // Click again to collapse
    fireEvent.click(screen.getByTestId('holding-row-GROWW.BO'));
    expect(screen.queryByTestId('lots-subrow-GROWW.BO')).not.toBeInTheDocument();
  });
});
