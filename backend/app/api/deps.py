import hashlib
import datetime
from typing import Optional
from fastapi import Depends, HTTPException, status, Header
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.database import get_db
from app.db.models import User, ApiKey
from app.services.auth_service import decode_access_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)

def hash_api_key(key: str) -> str:
    return hashlib.sha256(key.strip().encode("utf-8")).hexdigest()

async def get_current_user(
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    token: Optional[str] = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    # 1. Check X-API-Key or Bearer starting with gl_mcp_
    candidate_key = x_api_key
    if not candidate_key and token and token.startswith("gl_mcp_"):
        candidate_key = token

    if candidate_key:
        k_hash = hash_api_key(candidate_key)
        stmt = select(ApiKey).where(ApiKey.key_hash == k_hash, ApiKey.is_active == True)
        res = await db.execute(stmt)
        api_key_obj = res.scalar_one_or_none()
        if not api_key_obj:
            raise credentials_exception
        
        api_key_obj.last_used_at = datetime.datetime.utcnow()
        await db.commit()

        user_stmt = select(User).where(User.user_id == api_key_obj.user_id)
        user_res = await db.execute(user_stmt)
        user = user_res.scalar_one_or_none()
        if not user:
            raise credentials_exception
        return user

    # 2. Fall back to standard JWT Bearer token
    if not token:
        raise credentials_exception

    payload = decode_access_token(token)
    if payload is None:
        raise credentials_exception
    username: str = payload.get("sub")
    if username is None:
        raise credentials_exception

    stmt = select(User).where(User.username == username)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    if user is None:
        raise credentials_exception
    return user

