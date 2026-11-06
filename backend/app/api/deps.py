import hashlib
import datetime
from typing import Optional, Any
from fastapi import Depends, HTTPException, status, Header
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, inspect
from app.db.database import get_db
from app.db.models import User, ApiKey
from app.services.auth_service import decode_access_token, get_or_sync_auth0_user
from app.services.auth0_service import verify_auth0_token

def get_user_id(user: Any) -> int:
    if user is None:
        return 0
    if isinstance(user, int):
        return user
    if hasattr(user, "__dict__") and "user_id" in user.__dict__:
        return user.__dict__["user_id"]
    insp = inspect(user, raiseerr=False)
    if insp is not None:
        if insp.key is not None and len(insp.key) > 1 and insp.key[1]:
            return insp.key[1][0]
        if insp.identity is not None and len(insp.identity) > 0:
            return insp.identity[0]
    try:
        return getattr(user, "user_id", 0)
    except Exception:
        return 0

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

_user_token_cache: dict = {}

async def get_current_user(
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    authorization: Optional[str] = Header(None, alias="Authorization"),
    token: Optional[str] = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
) -> User:
    # 0. Quick rejection for unauthenticated requests
    if not authorization and not x_api_key and not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Reject non-Bearer schemes in Authorization header (e.g. Basic) while permitting raw gl_mcp_ API keys
    if authorization:
        auth_stripped = authorization.strip()
        auth_lower = auth_stripped.lower()
        if auth_lower.startswith("basic ") or (
            not (auth_lower.startswith("bearer ") or auth_lower.startswith("token ") or auth_stripped.startswith("gl_mcp_"))
        ):
            raise HTTPException(
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

    if not cleaned_candidates:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

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
    for candidate in cleaned_candidates:
        auth0_payload = await verify_auth0_token(candidate)
        if auth0_payload is not None:
            sub = auth0_payload.get("sub")
            if sub:
                email = auth0_payload.get("email")
                name = auth0_payload.get("name")
                picture = auth0_payload.get("picture")

                # If this exact token was already processed and user exists in DB,
                # return existing user so explicit /auth/sync profile updates are preserved.
                if _user_token_cache.get(sub) == candidate:
                    stmt = select(User).where(User.auth0_sub == sub)
                    existing_user = (await db.execute(stmt)).scalar_one_or_none()
                    if existing_user:
                        return existing_user

                user = await get_or_sync_auth0_user(
                    db,
                    sub=sub,
                    email=email,
                    name=name,
                    picture=picture
                )
                if user:
                    _user_token_cache[sub] = candidate
                    return user

    # 3. Fallback: Try decoding candidates as local HS256 JWT tokens
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

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": 'Bearer error="invalid_token"'},
    )


