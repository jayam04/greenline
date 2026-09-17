sed -i 's/import { formatCurrency } from "@\/lib\/format";/import { formatCurrency } from "@\/lib\/format";\nimport { TransactionLedger, UnifiedRowItem } from "@\/components\/TransactionLedger";/' /home/jayampatel/swe/greenline/frontend/src/app/cashflow/transactions/page.tsx

perl -0777 -pi -e 's/interface UnifiedRowItem \{.*?\n\}\n//s' /home/jayampatel/swe/greenline/frontend/src/app/cashflow/transactions/page.tsx
