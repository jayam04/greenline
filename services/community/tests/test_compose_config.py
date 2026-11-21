import os
import pytest
from unittest.mock import patch


def test_community_config_db_target_localdockerdb():
    with patch.dict(os.environ, {
        "DB_TARGET": "localdockerdb",
        "ORACLE_LOCAL_USER": "test_local_user",
        "ORACLE_LOCAL_PASSWORD": "test_local_pw",
        "ORACLE_LOCAL_DSN": "oracle:1521/FREEPDB1",
    }, clear=False):
        os.environ.pop("ORACLE_DSN", None)
        os.environ.pop("ORACLE_USER", None)
        os.environ.pop("ORACLE_PASSWORD", None)
        os.environ.pop("ORACLE_COMMUNITY_USER", None)
        os.environ.pop("COMMUNITY_DB_PASSWORD", None)

        from app.config import Settings
        s = Settings()
        assert s.DB_TARGET == "localdockerdb"
        assert s.ORACLE_COMMUNITY_USER == "test_local_user"
        assert s.COMMUNITY_DB_PASSWORD == "test_local_pw"
        assert s.ORACLE_DSN == "oracle:1521/FREEPDB1"


def test_community_config_db_target_cloud():
    with patch.dict(os.environ, {
        "DB_TARGET": "cloud",
        "ORACLE_COMMUNITY_USER": "GREENLINE_COMMUNITY",
        "COMMUNITY_DB_PASSWORD": "community_cloud_pw",
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
        assert s.ORACLE_COMMUNITY_USER == "GREENLINE_COMMUNITY"
        assert s.COMMUNITY_DB_PASSWORD == "community_cloud_pw"
        assert s.ORACLE_DSN == "(description=...cloud...)"
