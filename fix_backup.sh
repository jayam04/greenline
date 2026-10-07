sed -i '/for ca in data.get("corporate_actions", \[\]):/d' backend/app/services/backup_service.py
sed -i '/ast_id = ca.get("asset_id")/d' backend/app/services/backup_service.py
sed -i '/if ast_id not in asset_ids:/d' backend/app/services/backup_service.py
