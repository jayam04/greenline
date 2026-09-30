sed -i 's/r.runningBalancesAfter\[aid\] !== undefined/r.runningBalancesAfter?.[aid] !== undefined/g' /home/jayampatel/swe/greenline/frontend/src/app/cashflow/transactions/page.tsx
sed -i 's/latestRowWithAccount.runningBalancesAfter\[aid\]/latestRowWithAccount.runningBalancesAfter?.[aid] || 0/g' /home/jayampatel/swe/greenline/frontend/src/app/cashflow/transactions/page.tsx
