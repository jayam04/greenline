import os
from pydantic_settings import BaseSettings
from pydantic import ConfigDict
from typing import Optional, List

def _get_default_data_dir() -> str:
    env_dir = os.getenv("DATA_DIR")
    if env_dir:
        return env_dir
    if os.path.exists("/data") and os.access("/data", os.W_OK):
        return "/data"
    os.makedirs("./data", exist_ok=True)
    return "./data"

class Settings(BaseSettings):
    model_config = ConfigDict(case_sensitive=True)

    PROJECT_NAME: str = "Investment Tracker API"
    API_V1_STR: str = "/api/v1"
    SECRET_KEY: str = os.getenv("SECRET_KEY", "super-secret-investment-tracker-key-change-in-prod-2026")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7 # 7 days
    
    DATA_DIR: str = _get_default_data_dir()
    BACKUP_DIR: str = os.getenv("BACKUP_DIR", os.path.join(_get_default_data_dir(), "backups"))
    
    DATABASE_URL: str = os.getenv("DATABASE_URL", "oracle+oracledb://@")

    # Oracle Database credentials (Autonomous Database or local container)
    ORACLE_USER: Optional[str] = None
    ORACLE_PASSWORD: Optional[str] = None
    ORACLE_DSN: Optional[str] = None
    ORACLE_SCHEMA: Optional[str] = os.getenv("ORACLE_SCHEMA", None)
    
    DEFAULT_ADMIN_USER: str = os.getenv("DEFAULT_ADMIN_USER", "admin")
    DEFAULT_ADMIN_PASSWORD: str = os.getenv("DEFAULT_ADMIN_PASSWORD", "admin123")

    # Auth0 Configuration
    AUTH0_DOMAIN: Optional[str] = os.getenv("AUTH0_DOMAIN", None)
    AUTH0_CLIENT_ID: Optional[str] = os.getenv("AUTH0_CLIENT_ID", os.getenv("NEXT_PUBLIC_AUTH0_CLIENT_ID", "wTsdPwbGO91s4SjnzhA4pC9ik4MFEjby"))
    AUTH0_AUDIENCE: Optional[str] = os.getenv("AUTH0_AUDIENCE", None)
    AUTH0_ISSUER: Optional[str] = os.getenv("AUTH0_ISSUER", None)
    AUTH0_ALGORITHMS: List[str] = ["RS256"]
    AUTH0_TEST_MODE: bool = os.getenv("AUTH0_TEST_MODE", "false").lower() in ("true", "1", "yes")

settings = Settings()
