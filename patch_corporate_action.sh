sed -i 's/, CorporateAction//g' backend/app/services/backup_service.py
sed -i 's/CorporateAction,//g' backend/app/services/backup_service.py
sed -i '/await db.execute(delete(CorporateAction))/d' backend/app/services/backup_service.py
sed -i '/raise ValueError(f"Invalid foreign key: CorporateAction/d' backend/app/services/backup_service.py
# remove CorporateAction addition in backup_service
sed -i '/db.add(CorporateAction(/,/))/d' backend/app/services/backup_service.py

sed -i 's/, CorporateAction//g' backend/app/api/routers/backup.py
sed -i 's/CorporateAction,//g' backend/app/api/routers/backup.py
sed -i '/cas = (await db.execute(select(CorporateAction))).scalars().all()/d' backend/app/api/routers/backup.py
sed -i 's/CorporateAction//g' backend/app/scripts/seed_demo_data.py

sed -i 's/, CorporateAction//g' backend/tests/test_backup_and_autobackup.py
sed -i 's/CorporateAction,//g' backend/tests/test_backup_and_autobackup.py
sed -i '/ca = CorporateAction/d' backend/tests/test_backup_and_autobackup.py
sed -i '/session.add(ca)/d' backend/tests/test_backup_and_autobackup.py
sed -i '/session.add(CorporateAction/d' backend/tests/test_backup_and_autobackup.py
sed -i '/cas = (await session.execute(select(CorporateAction)))/d' backend/tests/test_backup_and_autobackup.py

sed -i 's/, CorporateAction//g' backend/tests/test_dividend_engine.py
sed -i 's/CorporateAction,//g' backend/tests/test_dividend_engine.py
sed -i '/session.add(CorporateAction(/,/))/d' backend/tests/test_dividend_engine.py
