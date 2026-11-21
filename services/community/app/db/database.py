from typing import Optional
from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import event

try:
    from ..config import settings
except (ImportError, ValueError):
    from app.config import settings

db_url = settings.DATABASE_URL


def _clean_credential(value: Optional[str]) -> Optional[str]:
    if isinstance(value, str):
        return value.strip("\"' \t\r\n")
    return value


def create_database_engine(database_url: str, connect_args=None, **kwargs) -> AsyncEngine:
    """Build an async SQLAlchemy engine for Oracle Database scoped to GREENLINE_COMMUNITY."""
    driver_args = dict(connect_args or {})
    engine_kwargs = {"echo": False}
    engine_kwargs.update(kwargs)

    if database_url.startswith("oracle+oracledb://"):
        user = settings.ORACLE_COMMUNITY_USER
        password = settings.COMMUNITY_DB_PASSWORD
        dsn = settings.ORACLE_DSN

        if user:
            driver_args.setdefault("user", _clean_credential(user))
        if password:
            driver_args.setdefault("password", _clean_credential(password))
        if dsn:
            driver_args.setdefault("dsn", _clean_credential(dsn))

        driver_args.setdefault("stmtcachesize", 50)
        for key in ("user", "password", "dsn"):
            if key in driver_args and isinstance(driver_args[key], str):
                driver_args[key] = _clean_credential(driver_args[key])

        poolclass = engine_kwargs.get("poolclass")
        is_null_pool = poolclass is not None and (
            getattr(poolclass, "__name__", "") == "NullPool"
            or str(poolclass) == "<class 'sqlalchemy.pool.impl.NullPool'>"
        )
        if not is_null_pool:
            engine_kwargs.setdefault("pool_size", 10)
            engine_kwargs.setdefault("max_overflow", 20)
        else:
            engine_kwargs.pop("pool_size", None)
            engine_kwargs.pop("max_overflow", None)

        engine_kwargs.setdefault("pool_recycle", 1800)
        engine_kwargs.setdefault("pool_pre_ping", True)

    return create_async_engine(
        database_url,
        connect_args=driver_args,
        **engine_kwargs
    )


engine = create_database_engine(db_url)

if db_url.startswith("oracle+oracledb://") and getattr(settings, "ORACLE_SCHEMA", None):
    target_schema = _clean_credential(settings.ORACLE_SCHEMA)

    @event.listens_for(engine.sync_engine, "connect")
    def set_oracle_current_schema(dbapi_connection, connection_record):
        try:
            cursor = dbapi_connection.cursor()
            cursor.execute(f"ALTER SESSION SET CURRENT_SCHEMA = {target_schema}")
            cursor.close()
        except Exception:
            pass

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False
)


class Base(DeclarativeBase):
    pass


async def get_db():
    """Async session dependency for FastAPI routes."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
