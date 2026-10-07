import asyncio
from sqlalchemy import select, delete
from app.db.database import AsyncSessionLocal
from app.db.models import Transaction, PriceHistory

async def main():
    async with AsyncSessionLocal() as session:
        # Find all dividend transactions with a price_per_unit
        stmt = select(Transaction).where(
            Transaction.transaction_type == 'dividend',
            Transaction.asset_id.isnot(None),
            Transaction.price_per_unit.isnot(None)
        )
        result = await session.execute(stmt)
        divs = result.scalars().all()
        
        deleted_count = 0
        for div in divs:
            # Look for a PriceHistory that matches exactly
            ph_stmt = select(PriceHistory).where(
                PriceHistory.asset_id == div.asset_id,
                PriceHistory.price_date == div.transaction_date,
                PriceHistory.close_price == div.price_per_unit
            )
            ph_res = await session.execute(ph_stmt)
            ph = ph_res.scalar_one_or_none()
            
            if ph:
                await session.delete(ph)
                deleted_count += 1
                print(f"Deleted erroneous PriceHistory for asset {div.asset_id} on {div.transaction_date} (price {ph.close_price})")
                
        if deleted_count > 0:
            await session.commit()
            print(f"\nSuccessfully removed {deleted_count} incorrect price history records.")
        else:
            print("No erroneous price history records found.")

asyncio.run(main())
