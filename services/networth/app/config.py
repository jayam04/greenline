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
    model_config = ConfigDict(case_sensitive=True, extra="ignore")

    PROJECT_NAME: str = "Networth & Analytics Service"
    API_V1_STR: str = "/api/v1"
    PORT: int = int(os.getenv("PORT", "8000"))

    # Security & Local HS256 JWT
    SECRET_KEY: str = os.getenv("SECRET_KEY", "super-secret-investment-tracker-key-change-in-prod-2026")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days

    # Storage paths
    DATA_DIR: str = _get_default_data_dir()
    BACKUP_DIR: str = os.getenv("BACKUP_DIR", os.path.join(_get_default_data_dir(), "backups"))

    # Deployment environment & database target mode
    ENV: str = os.getenv("ENV", "dev").lower()
    DB_TARGET: str = os.getenv("DB_TARGET", "localdockerdb").lower()

    # Redis Cache Configuration
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    NETWORTH_HISTORY_URL: str = os.getenv("NETWORTH_HISTORY_URL", "http://localhost:8003")
    NETWORTH_HISTORY_SERVICE_TOKEN: str = os.getenv("NETWORTH_HISTORY_SERVICE_TOKEN", "")

    # Database connection URL
    DATABASE_URL: str = ""

    # Oracle Database credentials
    ORACLE_USER: Optional[str] = None
    ORACLE_PASSWORD: Optional[str] = None
    ORACLE_DSN: Optional[str] = None
    ORACLE_SCHEMA: Optional[str] = None

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        target = self.DB_TARGET.lower()
        history_mode = os.getenv("NETWORTH_HISTORY_MODE", "false").lower() in ("true", "1", "yes")
        history_database_url = os.getenv("DATABASE_URL_NETWORTH_HISTORY")
        if target == "cloud":
            self.ORACLE_USER = (
                (os.getenv("ORACLE_NETWORTH_HISTORY_USER") if history_mode else None)
                or os.getenv("ORACLE_CLOUD_USER")
                or os.getenv("ORACLE_NETWORTH_USER")
                or os.getenv("ORACLE_USER")
            )
            self.ORACLE_PASSWORD = (
                (os.getenv("ORACLE_NETWORTH_HISTORY_PASSWORD") if history_mode else None)
                or os.getenv("ORACLE_CLOUD_PASSWORD")
                or os.getenv("ORACLE_NETWORTH_PASSWORD")
                or os.getenv("ORACLE_PASSWORD")
            )
            self.ORACLE_DSN = os.getenv("ORACLE_CLOUD_DSN") or os.getenv("ORACLE_DSN")
            self.ORACLE_SCHEMA = os.getenv("ORACLE_SCHEMA", "ADMIN")
            self.DATABASE_URL = (
                (history_database_url if history_mode else None)
                or os.getenv("DATABASE_URL_NETWORTH")
                or os.getenv("DATABASE_URL_CLOUD")
                or os.getenv("DATABASE_URL")
                or "oracle+oracledb://@"
            )
        else:
            # localdockerdb mode
            default_host = "oracle" if os.getenv("IS_DOCKER") else "localhost"
            self.ORACLE_USER = (
                (os.getenv("ORACLE_NETWORTH_HISTORY_USER") if history_mode else None)
                or os.getenv("ORACLE_LOCAL_USER")
                or os.getenv("ORACLE_NETWORTH_USER")
                or os.getenv("ORACLE_USER")
                or "greenline_test"
            )
            self.ORACLE_PASSWORD = (
                (os.getenv("ORACLE_NETWORTH_HISTORY_PASSWORD") if history_mode else None)
                or os.getenv("ORACLE_LOCAL_PASSWORD")
                or os.getenv("ORACLE_NETWORTH_PASSWORD")
                or os.getenv("ORACLE_PASSWORD")
                or "test_password"
            )
            self.ORACLE_DSN = (
                os.getenv("ORACLE_LOCAL_DSN")
                or os.getenv("ORACLE_DSN")
                or f"{default_host}:1521/FREEPDB1"
            )
            self.ORACLE_SCHEMA = os.getenv("ORACLE_SCHEMA", "ADMIN")
            self.DATABASE_URL = (
                (history_database_url if history_mode else None)
                or os.getenv("DATABASE_URL_NETWORTH")
                or os.getenv("DATABASE_URL_LOCAL")
                or os.getenv("DATABASE_URL")
                or f"oracle+oracledb://{self.ORACLE_USER}:{self.ORACLE_PASSWORD}@{self.ORACLE_DSN}"
            )

    # Default admin credentials
    DEFAULT_ADMIN_USER: str = os.getenv("DEFAULT_ADMIN_USER", "admin")
    DEFAULT_ADMIN_PASSWORD: str = os.getenv("DEFAULT_ADMIN_PASSWORD", "admin123")

    # Auth0 Configuration
    AUTH0_DOMAIN: Optional[str] = os.getenv("AUTH0_DOMAIN", "jayam04.eu.auth0.com")
    AUTH0_CLIENT_ID: Optional[str] = os.getenv("AUTH0_CLIENT_ID", os.getenv("NEXT_PUBLIC_AUTH0_CLIENT_ID", "wTsdPwbGO91s4SjnzhA4pC9ik4MFEjby"))
    AUTH0_AUDIENCE: Optional[str] = os.getenv("AUTH0_AUDIENCE", "http://localhost:8000")
    AUTH0_ISSUER: Optional[str] = os.getenv("AUTH0_ISSUER", "https://jayam04.eu.auth0.com/")
    AUTH0_ALGORITHMS: List[str] = ["RS256"]
    AUTH0_TEST_MODE: bool = os.getenv("AUTH0_TEST_MODE", "false").lower() in ("true", "1", "yes")


settings = Settings()
