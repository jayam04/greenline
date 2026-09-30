sed -i 's/import { TransactionModal, TransactionItem } from "@\/components\/TransactionModal";/import { TransactionModal, TransactionItem } from "@\/components\/TransactionModal";\nimport { TransactionLedger, UnifiedRowItem } from "@\/components\/TransactionLedger";/' /home/jayampatel/swe/greenline/frontend/src/app/cashflow/page.tsx

# Delete the interface UnifiedRowItem (lines 26-52 roughly, let's just find the precise lines)
perl -0777 -pi -e 's/interface UnifiedRowItem \{.*?\n\}\n//s' /home/jayampatel/swe/greenline/frontend/src/app/cashflow/page.tsx

