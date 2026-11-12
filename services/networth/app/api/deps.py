from typing import Optional
from fastapi import Depends, HTTPException, status, Header
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from cachetools import TTLCache

try:
    from ..config import settings
    from ..db.database import get_db
    from ..db.models import User
    from ..services.auth0_service import verify_auth0_token
except (ImportError, ValueError):
    from app.config import settings
    from app.db.database import get_db
    from app.db.models import User
    from app.services.auth0_service import verify_auth0_token

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_STR}/auth/token",
    auto_error=False
)

_user_cache: TTLCache = TTLCache(maxsize=1000, ttl=300)


def _clean_token(value: Optional[str]) -> Optional[str]:
    if isinstance(value, str):
        cleaned = value.strip()
        if not cleaned:
            return None
        if cleaned.lower().startswith("bearer "):
            cleaned = cleaned[7:].strip()
        return cleaned if cleaned else None
    return None


async def get_current_user(
    authorization: Optional[str] = Header(None, alias="Authorization"),
    token: Optional[str] = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
) -> User:
    """
    Stateless Auth0 JWT authentication dependency for Networth microservice.
    Resolves user via: SELECT user_id, auth0_sub, email, username FROM users WHERE auth0_sub = :sub.
    """
    candidate_token = _clean_token(token) or _clean_token(authorization)
    if not candidate_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    auth0_payload = await verify_auth0_token(candidate_token)
    if not auth0_payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    sub = auth0_payload.get("sub")
    if not sub or not str(sub).strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    sub_key = str(sub).strip()
    if sub_key in _user_cache:
        return _user_cache[sub_key]

    stmt = select(User).where(User.auth0_sub == sub_key)
    res = await db.execute(stmt)
    user = res.scalars().first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    _user_cache[sub_key] = user
    return user


def get_user_id(current_user: User) -> int:
    """Helper to extract user_id integer from authenticated User model."""
    return current_user.user_id
