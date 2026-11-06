import datetime
from typing import Optional
import bcrypt
from jose import jwt, JWTError
from app.config import settings

def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        pwd_bytes = plain_password.encode('utf-8')[:72]
        hash_bytes = hashed_password.encode('utf-8')
        return bcrypt.checkpw(pwd_bytes, hash_bytes)
    except Exception:
        return False

def get_password_hash(password: str) -> str:
    pwd_bytes = password.encode('utf-8')[:72]
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(pwd_bytes, salt).decode('utf-8')

def create_access_token(data: dict, expires_delta: Optional[datetime.timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.datetime.utcnow() + expires_delta
    else:
        expire = datetime.datetime.utcnow() + datetime.timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

def decode_access_token(token: str) -> Optional[dict]:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except JWTError:
        return None


async def get_or_sync_auth0_user(
    db: "AsyncSession",
    sub: str,
    email: Optional[str] = None,
    name: Optional[str] = None,
    picture: Optional[str] = None,
) -> "User":
    """Lookup or synchronize an Auth0 user into the local database."""
    from sqlalchemy import select, or_
    from sqlalchemy.ext.asyncio import AsyncSession
    from app.db.models import User

    # 1. Primary lookup by auth0_sub
    stmt = select(User).where(User.auth0_sub == sub)
    res = await db.execute(stmt)
    user = res.scalar_one_or_none()

    # 2. Account linking fallback: lookup unlinked user matching email or username
    if not user and email:
        link_stmt = select(User).where(
            or_(User.email == email, User.username == email)
        )
        link_res = await db.execute(link_stmt)
        candidates = link_res.scalars().all()
        # Find candidate without an auth0_sub already attached
        for candidate in candidates:
            if not candidate.auth0_sub:
                candidate.auth0_sub = sub
                user = candidate
                break

    # 3. Synchronize profile updates if existing user found or linked
    if user:
        changed = False
        if email and user.email != email:
            user.email = email
            changed = True
        if name and user.name != name:
            user.name = name
            changed = True
        if picture and user.picture != picture:
            user.picture = picture
            changed = True
        if changed or user.auth0_sub == sub:
            user.updated_at = datetime.datetime.utcnow()
            await db.commit()
            await db.refresh(user)
        return user

    # 4. Auto-provision new user
    candidate_username = email or sub
    # Ensure candidate username does not conflict with existing local username
    check_u = await db.execute(select(User).where(User.username == candidate_username))
    if check_u.scalar_one_or_none():
        candidate_username = f"{sub}"

    display_name = name or (email.split("@")[0] if email else sub)

    new_user = User(
        auth0_sub=sub,
        username=candidate_username,
        email=email,
        name=display_name,
        picture=picture,
        password_hash=None,
        created_at=datetime.datetime.utcnow(),
        updated_at=datetime.datetime.utcnow(),
    )
    db.add(new_user)
    try:
        await db.commit()
        await db.refresh(new_user)
        return new_user
    except Exception:
        await db.rollback()
        # Handle concurrency race condition if another thread inserted simultaneously
        retry_stmt = select(User).where(User.auth0_sub == sub)
        retry_res = await db.execute(retry_stmt)
        existing = retry_res.scalar_one_or_none()
        if existing:
            return existing
        raise
