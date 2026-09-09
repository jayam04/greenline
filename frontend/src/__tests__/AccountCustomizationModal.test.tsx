import { describe, it, expect, vi } from 'vitest';
import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { AccountCustomizationModal, AccountItem } from '@/components/AccountCustomizationModal';

const mockAccounts: AccountItem[] = [
  {
    account_id: 1,
    account_name: 'Groww Demat',
    account_type: 'demat',
    broker_name: 'Groww',
    currency: 'INR',
    current_balance: 57150,
  },
  {
    account_id: 2,
    account_name: 'Zerodha Demat',
    account_type: 'demat',
    broker_name: 'Zerodha',
    currency: 'INR',
    current_balance: 34400,
  },
  {
    account_id: 3,
    account_name: 'Jupiter Bank',
    account_type: 'bank',
    broker_name: 'Federal Bank',
    currency: 'INR',
    current_balance: 1089151,
  },
];

describe('AccountCustomizationModal Component', () => {
  it('renders all accounts and handles visibility toggle, reordering, and zero-balance toggle', () => {
    const handleClose = vi.fn();
    const handleSave = vi.fn();

    render(
      <AccountCustomizationModal
        isOpen={true}
        accounts={mockAccounts}
        initialOrder={[1, 2, 3]}
        initialHidden={[2]}
        initialHideZeroBalance={false}
        onClose={handleClose}
        onSave={handleSave}
      />
    );

    // Verify modal header
    expect(screen.getByText('Customize Accounts Layout')).toBeInTheDocument();

    // Verify all accounts are rendered
    expect(screen.getByText('Groww Demat')).toBeInTheDocument();
    expect(screen.getByText('Zerodha Demat')).toBeInTheDocument();
    expect(screen.getByText('Jupiter Bank')).toBeInTheDocument();

    // Check visibility toggle button for Zerodha Demat (should be currently hidden)
    const visibilityButtons = screen.getAllByRole('button', { name: /toggle visibility/i });
    expect(visibilityButtons.length).toBe(3);

    // Unhide Zerodha (click 2nd visibility button)
    fireEvent.click(visibilityButtons[1]);

    // Move 3rd account (Jupiter Bank) up
    const moveUpButtons = screen.getAllByRole('button', { name: /move up/i });
    fireEvent.click(moveUpButtons[2]); // Move 3rd item up

    // Toggle hide 0 balance accounts checkbox
    const zeroBalanceCheckbox = screen.getByLabelText(/Hide accounts with 0 balance/i);
    expect(zeroBalanceCheckbox).not.toBeChecked();
    fireEvent.click(zeroBalanceCheckbox);
    expect(zeroBalanceCheckbox).toBeChecked();

    // Click Save Changes
    const saveButton = screen.getByRole('button', { name: /save changes/i });
    fireEvent.click(saveButton);

    expect(handleSave).toHaveBeenCalledTimes(1);
    // After moving index 2 (account 3) up, order should be [1, 3, 2], hidden should be [], and hideZeroBalance true
    expect(handleSave).toHaveBeenCalledWith([1, 3, 2], [], true);
  });

  it('resets to default order and unhides all accounts when Reset is clicked', () => {
    const handleClose = vi.fn();
    const handleSave = vi.fn();

    render(
      <AccountCustomizationModal
        isOpen={true}
        accounts={mockAccounts}
        initialOrder={[3, 2, 1]}
        initialHidden={[1, 3]}
        initialHideZeroBalance={true}
        onClose={handleClose}
        onSave={handleSave}
      />
    );

    const resetButton = screen.getByRole('button', { name: /reset to default/i });
    fireEvent.click(resetButton);

    const saveButton = screen.getByRole('button', { name: /save changes/i });
    fireEvent.click(saveButton);

    // Should be restored to original accounts order [1, 2, 3], empty hidden list [], and hideZeroBalance false
    expect(handleSave).toHaveBeenCalledWith([1, 2, 3], [], false);
  });

  it('closes on Escape key press', () => {
    const handleClose = vi.fn();
    const handleSave = vi.fn();

    render(
      <AccountCustomizationModal
        isOpen={true}
        accounts={mockAccounts}
        initialOrder={[1, 2, 3]}
        initialHidden={[]}
        onClose={handleClose}
        onSave={handleSave}
      />
    );

    fireEvent.keyDown(window, { key: 'Escape', code: 'Escape' });
    expect(handleClose).toHaveBeenCalledTimes(1);
  });
});
