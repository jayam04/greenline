import os
from typing import Optional, List
from pydantic_settings import BaseSettings
from pydantic import ConfigDict


class Settings(BaseSettings):
    model_config = ConfigDict(case_sensitive=True, extra="ignore")

    PROJECT_NAME: str = "Greenline Community Microservice"
    API_V1_STR: str = "/api/v1/community"
    PORT: int = int(os.getenv("PORT", "8002"))

    # Deployment environment & database target mode
    ENV: str = os.getenv("ENV", "dev").lower()
    DB_TARGET: str = os.getenv("DB_TARGET", "localdockerdb").lower()

    # Database connection URL
    DATABASE_URL: str = ""

    # Dedicated Community Database user credentials
    ORACLE_COMMUNITY_USER: Optional[str] = None
    COMMUNITY_DB_PASSWORD: Optional[str] = None
    ORACLE_DSN: Optional[str] = None
    ORACLE_SCHEMA: Optional[str] = None

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        target = self.DB_TARGET.lower()
        if target == "cloud":
            self.ORACLE_COMMUNITY_USER = (
                os.getenv("ORACLE_COMMUNITY_USER")
                or os.getenv("ORACLE_USER")
                or "GREENLINE_COMMUNITY"
            )
            self.COMMUNITY_DB_PASSWORD = (
                os.getenv("COMMUNITY_DB_PASSWORD")
                or os.getenv("ORACLE_PASSWORD")
                or "SecureCommunity2026#DbPass"
            )
            self.ORACLE_DSN = os.getenv("ORACLE_CLOUD_DSN") or os.getenv("ORACLE_DSN")
            self.ORACLE_SCHEMA = os.getenv("ORACLE_SCHEMA", "ADMIN")
            self.DATABASE_URL = (
                os.getenv("DATABASE_URL_COMMUNITY")
                or os.getenv("DATABASE_URL_CLOUD")
                or os.getenv("DATABASE_URL")
                or "oracle+oracledb://@"
            )
        else:
            # localdockerdb mode
            default_host = "oracle" if os.getenv("IS_DOCKER") else "localhost"
            self.ORACLE_COMMUNITY_USER = (
                os.getenv("ORACLE_LOCAL_COMMUNITY_USER")
                or os.getenv("ORACLE_LOCAL_USER")
                or os.getenv("ORACLE_COMMUNITY_USER")
                or os.getenv("ORACLE_USER")
                or "GREENLINE_COMMUNITY"
            )
            self.COMMUNITY_DB_PASSWORD = (
                os.getenv("COMMUNITY_LOCAL_DB_PASSWORD")
                or os.getenv("ORACLE_LOCAL_PASSWORD")
                or os.getenv("COMMUNITY_DB_PASSWORD")
                or os.getenv("ORACLE_PASSWORD")
                or "SecureCommunity2026#DbPass"
            )
            self.ORACLE_DSN = (
                os.getenv("ORACLE_LOCAL_DSN")
                or os.getenv("ORACLE_DSN")
                or f"{default_host}:1521/FREEPDB1"
            )
            self.ORACLE_SCHEMA = os.getenv("ORACLE_SCHEMA", "ADMIN")
            self.DATABASE_URL = (
                os.getenv("DATABASE_URL_COMMUNITY")
                or os.getenv("DATABASE_URL_LOCAL")
                or os.getenv("DATABASE_URL")
                or "oracle+oracledb://@"
            )

    # Auth0 Configuration
    AUTH0_DOMAIN: Optional[str] = os.getenv("AUTH0_DOMAIN", "jayam04.eu.auth0.com")
    AUTH0_CLIENT_ID: Optional[str] = os.getenv("AUTH0_CLIENT_ID", os.getenv("NEXT_PUBLIC_AUTH0_CLIENT_ID", "wTsdPwbGO91s4SjnzhA4pC9ik4MFEjby"))
    AUTH0_AUDIENCE: Optional[str] = os.getenv("AUTH0_AUDIENCE", "http://localhost:8000")
    AUTH0_ISSUER: Optional[str] = os.getenv("AUTH0_ISSUER")
    AUTH0_ALGORITHMS: List[str] = ["RS256"]
    AUTH0_TEST_MODE: bool = os.getenv("AUTH0_TEST_MODE", "false").lower() in ("true", "1", "yes")


settings = Settings()
