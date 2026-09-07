import { describe, it, expect, vi } from 'vitest';
import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { SankeyChart, SankeyData } from '@/components/SankeyChart';

// Mock ThemeProvider
vi.mock('@/components/ThemeProvider', () => ({
  useTheme: () => ({
    theme: 'light',
    resolvedTheme: 'light',
    setTheme: vi.fn(),
  }),
}));

describe('SankeyChart Component - Multi-Layer Architecture', () => {
  it('renders 3 columns for depth 1 (in -> sustained -> out)', () => {
    const mockDataDepth1: SankeyData = {
      depth: 1,
      total_income: 5000,
      total_expenses: 450,
      total_investments: 1500,
      nodes: [
        { id: 'in_1_income', name: 'Income', level: 1, category_type: 'INCOME', color: '#10B981' },
        { id: 'node_cash_inflow', name: 'Total Inflow Pool', level: 2, color: '#10B981' },
        { id: 'out_3_essential', name: 'Essential', level: 3, category_type: 'EXPENSE', color: '#10B981' },
        { id: 'out_3_investments', name: 'Investments', level: 3, category_type: 'INVESTMENT', color: '#3B82F6' },
        { id: 'out_3_retained', name: 'Retained Cash / Added to Savings', level: 3, color: '#059669' },
      ],
      links: [
        { source: 'in_1_income', target: 'node_cash_inflow', value: 5000, color: '#10B981' },
        { source: 'node_cash_inflow', target: 'out_3_essential', value: 450, color: '#10B981' },
        { source: 'node_cash_inflow', target: 'out_3_investments', value: 1500, color: '#3B82F6' },
        { source: 'node_cash_inflow', target: 'out_3_retained', value: 3050, color: '#10B981' },
      ],
    };

    render(<SankeyChart data={mockDataDepth1} currency="EUR" />);

    expect(screen.getByText('Income')).toBeDefined();
    expect(screen.getByText('Total Inflow Pool')).toBeDefined();
    expect(screen.getByText('Essential')).toBeDefined();
    expect(screen.getByText('Investments')).toBeDefined();
    expect(screen.getByText('Retained Cash / Added to Savings')).toBeDefined();
  });

  it('renders 5 columns for depth 2 (insub1 -> in -> sustained -> out -> outsub1)', () => {
    const mockDataDepth2: SankeyData = {
      depth: 2,
      total_income: 5000,
      total_expenses: 450,
      total_investments: 1500,
      nodes: [
        // Level 1: insub1
        { id: 'in_1_salary', name: 'Salary', level: 1, category_type: 'INCOME', color: '#34D399' },
        // Level 2: in
        { id: 'in_2_income', name: 'Income', level: 2, category_type: 'INCOME', color: '#10B981' },
        // Level 3: sustained
        { id: 'node_cash_inflow', name: 'Total Inflow Pool', level: 3, color: '#10B981' },
        // Level 4: out
        { id: 'out_4_essential', name: 'Essential', level: 4, category_type: 'EXPENSE', color: '#10B981' },
        { id: 'out_4_investments', name: 'Investments', level: 4, category_type: 'INVESTMENT', color: '#3B82F6' },
        // Level 5: outsub1
        { id: 'out_5_food', name: 'Food & Dining', level: 5, category_type: 'EXPENSE', color: '#10B981' },
        { id: 'out_5_stock', name: 'Stock & ETF Purchases', level: 5, category_type: 'INVESTMENT', color: '#3B82F6' },
      ],
      links: [
        { source: 'in_1_salary', target: 'in_2_income', value: 5000, color: '#34D399' },
        { source: 'in_2_income', target: 'node_cash_inflow', value: 5000, color: '#10B981' },
        { source: 'node_cash_inflow', target: 'out_4_essential', value: 450, color: '#10B981' },
        { source: 'node_cash_inflow', target: 'out_4_investments', value: 1500, color: '#3B82F6' },
        { source: 'out_4_essential', target: 'out_5_food', value: 450, color: '#10B981' },
        { source: 'out_4_investments', target: 'out_5_stock', value: 1500, color: '#3B82F6' },
      ],
    };

    render(<SankeyChart data={mockDataDepth2} currency="EUR" />);

    expect(screen.getByText('Salary')).toBeDefined();
    expect(screen.getByText('Income')).toBeDefined();
    expect(screen.getByText('Total Inflow Pool')).toBeDefined();
    expect(screen.getByText('Essential')).toBeDefined();
    expect(screen.getByText('Food & Dining')).toBeDefined();
    expect(screen.getByText('Investments')).toBeDefined();
    expect(screen.getByText('Stock & ETF Purchases')).toBeDefined();
  });

  it('renders 7 columns for depth 3 (insub2 -> insub1 -> in -> sustained -> out -> outsub1 -> outsub2)', () => {
    const mockDataDepth3: SankeyData = {
      depth: 3,
      total_income: 5000,
      total_expenses: 450,
      total_investments: 1500,
      nodes: [
        { id: 'in_1_base', name: 'Base Salary', level: 1, category_type: 'INCOME' },
        { id: 'in_2_salary', name: 'Salary', level: 2, category_type: 'INCOME' },
        { id: 'in_3_income', name: 'Income', level: 3, category_type: 'INCOME' },
        { id: 'node_cash_inflow', name: 'Total Inflow Pool', level: 4 },
        { id: 'out_5_essential', name: 'Essential', level: 5, category_type: 'EXPENSE' },
        { id: 'out_6_food', name: 'Food & Dining', level: 6, category_type: 'EXPENSE' },
        { id: 'out_7_groc', name: 'Groceries', level: 7, category_type: 'EXPENSE' },
      ],
      links: [
        { source: 'in_1_base', target: 'in_2_salary', value: 5000 },
        { source: 'in_2_salary', target: 'in_3_income', value: 5000 },
        { source: 'in_3_income', target: 'node_cash_inflow', value: 5000 },
        { source: 'node_cash_inflow', target: 'out_5_essential', value: 450 },
        { source: 'out_5_essential', target: 'out_6_food', value: 450 },
        { source: 'out_6_food', target: 'out_7_groc', value: 450 },
      ],
    };

    render(<SankeyChart data={mockDataDepth3} currency="EUR" />);

    expect(screen.getByText('Base Salary')).toBeDefined();
    expect(screen.getByText('Salary')).toBeDefined();
    expect(screen.getByText('Income')).toBeDefined();
    expect(screen.getByText('Total Inflow Pool')).toBeDefined();
    expect(screen.getByText('Essential')).toBeDefined();
    expect(screen.getByText('Food & Dining')).toBeDefined();
    expect(screen.getByText('Groceries')).toBeDefined();
  });
});
