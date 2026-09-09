import os
from pydantic_settings import BaseSettings
from pydantic import ConfigDict

def _get_default_data_dir() -> str:
    env_dir = os.getenv("DATA_DIR")
    if env_dir:
        return env_dir
    if os.path.exists("/data") and os.access("/data", os.W_OK):
        return "/data"
    os.makedirs("./data", exist_ok=True)
    return "./data"

def _get_default_database_file() -> str:
    env_file = os.getenv("DATABASE_FILE")
    if env_file:
        return env_file
    env_url = os.getenv("DATABASE_URL")
    if env_url and "sqlite" in env_url:
        import re
        raw_path = re.sub(r"^sqlite(?:\+[a-zA-Z0-9_]+)?:///", "", env_url)
        base = os.path.basename(raw_path)
        if base:
            return base
    return "investments.db"

def _get_default_database_url(data_dir: str, db_file: str) -> str:
    env_url = os.getenv("DATABASE_URL")
    if env_url:
        return env_url
    clean_dir = data_dir.rstrip("/")
    return f"sqlite+aiosqlite:///{clean_dir}/{db_file}"

class Settings(BaseSettings):
    model_config = ConfigDict(case_sensitive=True)

    PROJECT_NAME: str = "Investment Tracker API"
    API_V1_STR: str = "/api/v1"
    SECRET_KEY: str = os.getenv("SECRET_KEY", "super-secret-investment-tracker-key-change-in-prod-2026")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7 # 7 days
    
    DATA_DIR: str = _get_default_data_dir()
    DATABASE_FILE: str = _get_default_database_file()
    BACKUP_DIR: str = os.getenv("BACKUP_DIR", os.path.join(_get_default_data_dir(), "backups"))
    
    DATABASE_URL: str = _get_default_database_url(_get_default_data_dir(), _get_default_database_file())
    
    DEFAULT_ADMIN_USER: str = os.getenv("DEFAULT_ADMIN_USER", "admin")
    DEFAULT_ADMIN_PASSWORD: str = os.getenv("DEFAULT_ADMIN_PASSWORD", "admin123")

settings = Settings()
