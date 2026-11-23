import os
import pytest
from unittest.mock import patch


def test_networth_config_db_target_localdockerdb():
    with patch.dict(os.environ, {
        "DB_TARGET": "localdockerdb",
        "ORACLE_LOCAL_USER": "test_local_user",
        "ORACLE_LOCAL_PASSWORD": "test_local_pw",
        "ORACLE_LOCAL_DSN": "oracle:1521/FREEPDB1",
        "ORACLE_CLOUD_USER": "cloud_user",
        "ORACLE_CLOUD_PASSWORD": "cloud_pw",
        "ORACLE_CLOUD_DSN": "cloud_dsn",
    }, clear=False):
        # Remove direct ORACLE_DSN/ORACLE_USER if present
        os.environ.pop("ORACLE_DSN", None)
        os.environ.pop("ORACLE_USER", None)
        os.environ.pop("ORACLE_PASSWORD", None)

        from app.config import Settings
        s = Settings()
        assert s.DB_TARGET == "localdockerdb"
        assert s.ORACLE_USER == "test_local_user"
        assert s.ORACLE_PASSWORD == "test_local_pw"
        assert s.ORACLE_DSN == "oracle:1521/FREEPDB1"


def test_networth_config_db_target_cloud():
    with patch.dict(os.environ, {
        "DB_TARGET": "cloud",
        "ORACLE_CLOUD_USER": "cloud_admin",
        "ORACLE_CLOUD_PASSWORD": "cloud_secret_pw",
        "ORACLE_CLOUD_DSN": "(description=...cloud...)",
        "ORACLE_LOCAL_USER": "test_local_user",
        "ORACLE_LOCAL_PASSWORD": "test_local_pw",
        "ORACLE_LOCAL_DSN": "oracle:1521/FREEPDB1",
    }, clear=False):
        os.environ.pop("ORACLE_DSN", None)
        os.environ.pop("ORACLE_USER", None)
        os.environ.pop("ORACLE_PASSWORD", None)

        from app.config import Settings
        s = Settings()
        assert s.DB_TARGET == "cloud"
        assert s.ORACLE_USER == "cloud_admin"
        assert s.ORACLE_PASSWORD == "cloud_secret_pw"
        assert s.ORACLE_DSN == "(description=...cloud...)"


def test_networth_history_config_uses_separate_database_user():
    with patch.dict(os.environ, {
        "NETWORTH_HISTORY_MODE": "true",
        "DB_TARGET": "localdockerdb",
        "ORACLE_NETWORTH_HISTORY_USER": "GREENLINE_NW_HISTORY",
        "ORACLE_NETWORTH_HISTORY_PASSWORD": "history-password",
        "ORACLE_LOCAL_DSN": "oracle:1521/FREEPDB1",
        "ORACLE_SCHEMA": "ADMIN",
        "DATABASE_URL_NETWORTH_HISTORY": "",
    }, clear=False):
        from app.config import Settings
        settings = Settings()
        assert settings.ORACLE_USER == "GREENLINE_NW_HISTORY"
        assert settings.ORACLE_PASSWORD == "history-password"
        assert settings.ORACLE_DSN == "oracle:1521/FREEPDB1"
        assert settings.DATABASE_URL.startswith("oracle+oracledb://GREENLINE_NW_HISTORY:history-password@")
