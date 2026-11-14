import os
from typing import Optional, List
from pydantic_settings import BaseSettings
from pydantic import ConfigDict


class Settings(BaseSettings):
    model_config = ConfigDict(case_sensitive=True, extra="ignore")

    PROJECT_NAME: str = "Greenline Community Microservice"
    API_V1_STR: str = "/api/v1/community"
    PORT: int = int(os.getenv("PORT", "8002"))

    # Database connection URL
    DATABASE_URL: str = (
        os.getenv("DATABASE_URL_COMMUNITY")
        or os.getenv("DATABASE_URL")
        or "oracle+oracledb://@"
    )

    # Dedicated Community Database user credentials
    ORACLE_COMMUNITY_USER: Optional[str] = (
        os.getenv("ORACLE_COMMUNITY_USER")
        or os.getenv("ORACLE_USER")
        or "GREENLINE_COMMUNITY"
    )
    COMMUNITY_DB_PASSWORD: Optional[str] = (
        os.getenv("COMMUNITY_DB_PASSWORD")
        or os.getenv("ORACLE_PASSWORD")
        or "SecureCommunity2026#DbPass"
    )
    ORACLE_DSN: Optional[str] = os.getenv("ORACLE_DSN", "localhost:1521/FREEPDB1")
    ORACLE_SCHEMA: Optional[str] = os.getenv("ORACLE_SCHEMA", "ADMIN")

    # Auth0 Configuration
    AUTH0_DOMAIN: Optional[str] = os.getenv("AUTH0_DOMAIN", "jayam04.eu.auth0.com")
    AUTH0_CLIENT_ID: Optional[str] = os.getenv("AUTH0_CLIENT_ID", os.getenv("NEXT_PUBLIC_AUTH0_CLIENT_ID", "wTsdPwbGO91s4SjnzhA4pC9ik4MFEjby"))
    AUTH0_AUDIENCE: Optional[str] = os.getenv("AUTH0_AUDIENCE", "http://localhost:8000")
    AUTH0_ISSUER: Optional[str] = os.getenv("AUTH0_ISSUER")
    AUTH0_ALGORITHMS: List[str] = ["RS256"]
    AUTH0_TEST_MODE: bool = os.getenv("AUTH0_TEST_MODE", "false").lower() in ("true", "1", "yes")


settings = Settings()
