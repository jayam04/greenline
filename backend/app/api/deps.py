import hashlib
import datetime
from typing import Optional
from fastapi import Depends, HTTPException, status, Header
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.config import settings
from app.db.database import get_db
from app.db.models import User, ApiKey
from app.services.auth_service import decode_access_token, get_password_hash
from app.services.auth0_service import verify_auth0_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)

def hash_api_key(key: str) -> str:
    return hashlib.sha256(key.strip().encode("utf-8")).hexdigest()

def _clean_auth_value(val: Optional[str]) -> Optional[str]:
    if not val:
        return None
    cleaned = val.strip().strip('"').strip("'")
    # Repeatedly strip leading 'bearer ' or 'token ' in case of 'Bearer Bearer ...'
    while True:
        lower = cleaned.lower()
        if lower.startswith("bearer "):
            cleaned = cleaned[7:].strip().strip('"').strip("'")
        elif lower.startswith("token "):
            cleaned = cleaned[6:].strip().strip('"').strip("'")
        else:
            break
    return cleaned or None

async def get_current_user(
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    authorization: Optional[str] = Header(None, alias="Authorization"),
    token: Optional[str] = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    # Gather potential key/token candidates from all possible auth headers
    raw_candidates = [x_api_key, token, authorization]
    cleaned_candidates = []
    for c in raw_candidates:
        cleaned = _clean_auth_value(c)
        if cleaned and cleaned not in cleaned_candidates:
            cleaned_candidates.append(cleaned)

    # 1. Try matching candidates against database API keys
    for candidate in cleaned_candidates:
        k_hash = hash_api_key(candidate)
        stmt = select(ApiKey).where(ApiKey.key_hash == k_hash, ApiKey.is_active == True)
        res = await db.execute(stmt)
        api_key_obj = res.scalar_one_or_none()
        if api_key_obj:
            api_key_obj.last_used_at = datetime.datetime.utcnow()
            await db.commit()

            user_stmt = select(User).where(User.user_id == api_key_obj.user_id)
            user_res = await db.execute(user_stmt)
            user = user_res.scalar_one_or_none()
            if user:
                return user

    # 2. Try validating candidates as Auth0 RS256 Bearer tokens
    if settings.AUTH0_DOMAIN:
        for candidate in cleaned_candidates:
            auth0_payload = await verify_auth0_token(candidate)
            if auth0_payload is not None:
                # In single-tenant phase, map to the existing primary user record
                user_stmt = select(User).order_by(User.user_id.asc())
                user_res = await db.execute(user_stmt)
                primary_user = user_res.scalars().first()
                if primary_user:
                    return primary_user

                # If no user exists yet in the database, automatically initialize one
                new_user = User(
                    username=settings.DEFAULT_ADMIN_USER,
                    password_hash=get_password_hash(settings.DEFAULT_ADMIN_PASSWORD),
                )
                db.add(new_user)
                await db.commit()
                await db.refresh(new_user)
                return new_user

    # 3. Try decoding candidates as local JWT Bearer tokens (HS256)
    for candidate in cleaned_candidates:
        payload = decode_access_token(candidate)
        if payload is not None:
            username: str = payload.get("sub")
            if username:
                stmt = select(User).where(User.username == username)
                result = await db.execute(stmt)
                user = result.scalar_one_or_none()
                if user:
                    return user

    print(f"[AUTH ERROR] Failed auth attempt. Raw headers: x_api_key={x_api_key!r}, auth={authorization!r}, token={token!r}. Cleaned candidates={cleaned_candidates!r}")
    raise credentials_exception

