sed -i '/# Validate corporate actions/d' backend/app/services/backup_service.py
sed -i '/valid_action_types = {"split", "bonus", "dividend", "merger", "spinoff", "spin_off", "name_change", "rights"}/d' backend/app/services/backup_service.py
sed -i '/_parse_iso_date(ca.get("action_date"), "corporate_action.action_date")/d' backend/app/services/backup_service.py
sed -i '/action_type = ca.get("action_type")/d' backend/app/services/backup_service.py
sed -i '/if not action_type:/d' backend/app/services/backup_service.py
sed -i '/raise ValueError("Invalid corporate action: missing action_type.")/d' backend/app/services/backup_service.py
sed -i '/if action_type.lower() not in valid_action_types:/d' backend/app/services/backup_service.py
sed -i '/raise ValueError(f"Invalid corporate action_type '{action_type}'.")/d' backend/app/services/backup_service.py
