import os
from typing import Optional, List
from pydantic_settings import BaseSettings
from pydantic import ConfigDict


class Settings(BaseSettings):
    model_config = ConfigDict(case_sensitive=True, extra="ignore")

    PROJECT_NAME: str = "Networth & Analytics Microservice"
    API_V1_STR: str = "/api/v1"
    PORT: int = int(os.getenv("PORT", "8001"))

    # Database connection URL
    DATABASE_URL: str = (
        os.getenv("DATABASE_URL_NETWORTH")
        or os.getenv("DATABASE_URL")
        or "oracle+oracledb://@"
    )

    # Oracle Database credentials
    ORACLE_USER: Optional[str] = os.getenv("ORACLE_NETWORTH_USER") or os.getenv("ORACLE_USER")
    ORACLE_PASSWORD: Optional[str] = os.getenv("ORACLE_NETWORTH_PASSWORD") or os.getenv("ORACLE_PASSWORD")
    ORACLE_DSN: Optional[str] = os.getenv("ORACLE_DSN")
    ORACLE_SCHEMA: Optional[str] = os.getenv("ORACLE_SCHEMA", "ADMIN")

    # Auth0 Configuration
    AUTH0_DOMAIN: Optional[str] = os.getenv("AUTH0_DOMAIN", "jayam04.eu.auth0.com")
    AUTH0_CLIENT_ID: Optional[str] = os.getenv("AUTH0_CLIENT_ID", os.getenv("NEXT_PUBLIC_AUTH0_CLIENT_ID", "wTsdPwbGO91s4SjnzhA4pC9ik4MFEjby"))
    AUTH0_AUDIENCE: Optional[str] = os.getenv("AUTH0_AUDIENCE", "http://localhost:8000")
    AUTH0_ISSUER: Optional[str] = os.getenv("AUTH0_ISSUER")
    AUTH0_ALGORITHMS: List[str] = ["RS256"]
    AUTH0_TEST_MODE: bool = os.getenv("AUTH0_TEST_MODE", "false").lower() in ("true", "1", "yes")


settings = Settings()
