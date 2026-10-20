import asyncio
from sqlalchemy import select
from app.db.database import AsyncSessionLocal
from app.db.models import CashFlow, Transaction

async def main():
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Transaction).where(Transaction.transaction_type == 'dividend'))
        divs = result.scalars().all()
        print(f"Found {len(divs)} dividend transactions")
        for d in divs:
            print(f"Dividend: Asset {d.asset_id}, Amount {d.total_amount}")
            
        if divs:
            d = divs[0]
            res2 = await session.execute(select(CashFlow).where(CashFlow.scope_type == 'asset', CashFlow.scope_id == d.asset_id))
            cfs = res2.scalars().all()
            print(f"Cashflows for Asset {d.asset_id}:")
            for cf in cfs:
                print(f"  {cf.flow_date} | {cf.flow_type} | {cf.amount}")

asyncio.run(main())
