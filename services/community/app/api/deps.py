from typing import Optional
from fastapi import Depends, HTTPException, status, Header
from fastapi.security import OAuth2PasswordBearer

try:
    from ..config import settings
    from ..services.auth0_service import verify_auth0_token
except (ImportError, ValueError):
    from app.config import settings
    from app.services.auth0_service import verify_auth0_token

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_STR}/auth/token",
    auto_error=False
)


def _clean_token(value: Optional[str]) -> Optional[str]:
    """Strip bearer prefix and surrounding whitespace."""
    if isinstance(value, str):
        cleaned = value.strip()
        if not cleaned:
            return None
        if cleaned.lower().startswith("bearer "):
            cleaned = cleaned[7:].strip()
        return cleaned if cleaned else None
    return None


async def get_current_author_sub(
    authorization: Optional[str] = Header(None, alias="Authorization"),
    token: Optional[str] = Depends(oauth2_scheme),
) -> str:
    """
    Stateless Auth0 RS256 JWT authentication dependency for Community microservice.
    Extracts author_sub from the verified 'sub' claim.
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

    return str(sub).strip()


async def get_optional_author_sub(
    authorization: Optional[str] = Header(None, alias="Authorization"),
    token: Optional[str] = Depends(oauth2_scheme),
) -> Optional[str]:
    """Optional Auth0 dependency returning author_sub if valid token present, or None."""
    candidate_token = _clean_token(token) or _clean_token(authorization)
    if not candidate_token:
        return None

    auth0_payload = await verify_auth0_token(candidate_token)
    if not auth0_payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    sub = auth0_payload.get("sub")
    return str(sub).strip() if sub else None
