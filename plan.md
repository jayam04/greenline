# Implementation Plan: Corporate Actions Frontend

## Goal Description
The goal is to update the frontend to allow users to add Corporate Actions (Bonus Shares and Stock Splits). This will introduce a new modal component and a trigger button in the transactions ledger to submit these actions to the existing `/corporate-actions` backend endpoint.

## Proposed Changes

### `frontend/src/components/CorporateActionModal.tsx`
#### [NEW] `CorporateActionModal.tsx`
Create a new modal component similar to `TransactionModal` but tailored for Corporate Actions:
- **Asset Search**: Dropdown search to select the target asset.
- **Action Type**: Dropdown for "Split" and "Bonus".
- **Action Date**: Date picker (defaults to today).
- **Ratio Inputs**: Two numeric inputs to construct the ratio string (e.g., "New Shares" for every "Old Share", combining them into the `X:Y` format expected by the backend).
- **Notes**: Optional text area.
- **Submission**: On submit, POST to `/corporate-actions` and refresh the page or trigger the `onSuccess` callback.

### `frontend/src/app/investments/transactions/page.tsx`
#### [MODIFY] `page.tsx`
- Import the new `CorporateActionModal`.
- Add a state variable `isCorpActionModalOpen`.
- Add a new "Corporate Action" button right next to the "Add transaction" button.
- Render the `CorporateActionModal` component and hook it up to the `loadTransactions` function on success so that the recalculated lots and updated values immediately reflect in the dashboard summary.

## Verification Plan

### Automated Tests
Run frontend type checks and linting to ensure no regressions:
```bash
cd frontend && npx tsc --noEmit && npm run lint
```

### Manual Verification
- Open the Transactions page and click "Corporate Action".
- Search for a private equity or public asset.
- Select "Split", enter "2" for "1" (2:1 ratio) and submit.
- Verify the POST request succeeds.
- Verify the modal closes and the summary statistics (or holdings) update if applicable.
