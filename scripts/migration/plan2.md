# Implementation Plan: Corporate Actions as Transactions

## Goal Description
We will migrate Corporate Actions to be standard `Transaction` records with `transaction_type` set to `"split"` or `"bonus"`. This makes them natively editable and deletable directly from the transactions ledger, while preserving the mathematically accurate FIFO cost basis adjustment (instead of a $0 lot distortion). 

## Proposed Changes

### `backend/app/services/fifo_engine.py`
#### [MODIFY] `fifo_engine.py`
- We will update `process_transaction_event` to natively handle `t_type == "split"` and `t_type == "bonus"`.
- When encountering these types, the engine will query the open lots for that specific `account_id` and `asset_id`.
- It will use the transaction's `quantity` field as the multiplier (e.g. `2.0` for a 2:1 split).
- It will multiply `lot.quantity_remaining` and `lot.quantity_original` by the multiplier, and divide `lot.cost_per_unit` by the multiplier.
- We will remove the old logic that fetched from the `corporate_actions` table.

### `backend/app/api/routers/transactions.py`
#### [MODIFY] `transactions.py`
- In `create_transaction` and `update_transaction`, if the type is "split" or "bonus" and the asset is "Private Equity", we will automatically adjust the `PriceHistory` (divide by the multiplier).
- Since they are normal transactions, `recalculate_past_snapshots` will automatically be triggered accurately.
- Remove the hacky pseudo-transaction injection in `list_transactions`.

### `frontend/src/components/TransactionModal.tsx`
#### [MODIFY] `TransactionModal.tsx`
- Add "Stock Split" and "Bonus Shares" back into the main `TransactionType` dropdown.
- When these are selected, hide `price_per_unit`, `total_amount`, `fees`, and `taxes`.
- Change the `quantity` label to "Split Multiplier" (e.g., enter 2 for a 2:1 split).
- Submit them seamlessly to the `/transactions` endpoint.

### `frontend/src/app/investments/transactions/page.tsx`
#### [MODIFY] `page.tsx`
- Remove the separate "Corporate Action" button and modal entirely.
- Restore the native Edit/Delete buttons for splits and bonuses.

### `backend/app/db/models.py` & `backend/app/api/routers/corporate_actions.py`
#### [DELETE] `CorporateActionModal.tsx` & `/corporate-actions` logic
- We will deprecate the standalone corporate actions router and frontend modal.

## Verification Plan
1. Add a Stock Split transaction using the main modal (multiplier 2.0).
2. Verify it appears natively in the ledger.
3. Edit the split transaction to multiplier 3.0 and verify lots recalculate.
4. Delete the split transaction and verify the lots return to normal.
