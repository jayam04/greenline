import { describe, it, expect, vi } from 'vitest';
import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { AccountModal, AssetModal } from '@/app/accounts/page';

describe('AccountModal Component', () => {
  it('renders account form fields and dismisses on Escape key', () => {
    const handleClose = vi.fn();
    const handleSuccess = vi.fn();

    render(
      <AccountModal
        isOpen={true}
        initialData={null}
        onClose={handleClose}
        onSuccess={handleSuccess}
      />
    );

    expect(screen.getByText('Add New Account')).toBeInTheDocument();
    expect(screen.getByPlaceholderText(/Zerodha Primary/i)).toBeInTheDocument();

    // Verify all major currencies are present in base currency dropdown
    expect(screen.getByText(/USD \(\$ - US Dollar\)/i)).toBeInTheDocument();
    expect(screen.getByText(/EUR \(€ - Euro\)/i)).toBeInTheDocument();
    expect(screen.getByText(/INR \(₹ - Indian Rupee\)/i)).toBeInTheDocument();
    expect(screen.getByText(/JPY \(¥ - Japanese Yen\)/i)).toBeInTheDocument();
    expect(screen.getByText(/CHF \(CHF - Swiss Franc\)/i)).toBeInTheDocument();
    expect(screen.getByText(/SGD \(S\$ - Singapore Dollar\)/i)).toBeInTheDocument();

    // Press Escape key
    fireEvent.keyDown(window, { key: 'Escape', code: 'Escape' });
    expect(handleClose).toHaveBeenCalledTimes(1);
  });

  it('renders default dividend bank account dropdown for Demat accounts', () => {
    const mockAccounts = [
      { account_id: 1, account_name: "HDFC Bank", account_type: "bank", currency: "INR" },
      { account_id: 2, account_name: "ICICI Direct", account_type: "demat", currency: "INR" },
    ];

    render(
      <AccountModal
        isOpen={true}
        initialData={null}
        allAccounts={mockAccounts}
        onClose={vi.fn()}
        onSuccess={vi.fn()}
      />
    );

    expect(screen.getByText('Default Dividend Bank Account')).toBeInTheDocument();
    expect(screen.getByText('HDFC Bank (INR)')).toBeInTheDocument();
  });
});

describe('AssetModal Component', () => {
  it('renders asset form fields including full currency list and dismisses on Escape key', () => {
    const handleClose = vi.fn();
    const handleSuccess = vi.fn();

    render(
      <AssetModal
        isOpen={true}
        initialData={null}
        onClose={handleClose}
        onSuccess={handleSuccess}
      />
    );

    expect(screen.getByText('Add Security to Master')).toBeInTheDocument();
    expect(screen.getByPlaceholderText(/AAPL, MSFT/i)).toBeInTheDocument();

    // Check trading currency options
    expect(screen.getByText(/JPY \(¥\)/i)).toBeInTheDocument();
    expect(screen.getByText(/CHF \(CHF\)/i)).toBeInTheDocument();
    expect(screen.getByText(/SGD \(S\$\)/i)).toBeInTheDocument();

    // Press Escape key
    fireEvent.keyDown(window, { key: 'Escape', code: 'Escape' });
    expect(handleClose).toHaveBeenCalledTimes(1);
  });
});
