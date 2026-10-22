import time
import logging
from typing import Optional, Dict, Any
import httpx
from jose import jwt, JWTError
from app.config import settings

logger = logging.getLogger(__name__)

# In-memory JWKS cache: { "keys": [...], "fetched_at": float }
_jwks_cache: Dict[str, Any] = {}
JWKS_CACHE_TTL_SECONDS = 86400 # 24 hours

def clear_jwks_cache():
    """Clear the in-memory JWKS cache (useful for tests)."""
    global _jwks_cache
    _jwks_cache.clear()

async def fetch_jwks(domain: str) -> Dict[str, Any]:
    """Fetch JSON Web Key Set from the Auth0 well-known endpoint."""
    url = f"https://{domain}/.well-known/jwks.json"
    async with httpx.AsyncClient(timeout=10.0) as client:
        res = await client.get(url)
        res.raise_for_status()
        return res.json()

async def get_jwks(domain: str, force_refresh: bool = False) -> Dict[str, Any]:
    """Retrieve JWKS with in-memory caching."""
    global _jwks_cache
    now = time.time()
    if (
        not force_refresh
        and _jwks_cache.get("domain") == domain
        and (now - _jwks_cache.get("fetched_at", 0)) < JWKS_CACHE_TTL_SECONDS
        and "keys" in _jwks_cache
    ):
        return _jwks_cache["keys"]

    try:
        jwks_data = await fetch_jwks(domain)
        _jwks_cache = {
            "domain": domain,
            "keys": jwks_data,
            "fetched_at": now,
        }
        return jwks_data
    except Exception as exc:
        logger.error(f"Failed to fetch Auth0 JWKS from domain {domain}: {exc}")
        if "keys" in _jwks_cache and _jwks_cache.get("domain") == domain:
            return _jwks_cache["keys"]
        return {"keys": []}

async def verify_auth0_token(token: str) -> Optional[Dict[str, Any]]:
    """
    Verify an RS256 JWT issued by Auth0 against the tenant's JWKS.
    Returns decoded token payload claims if valid, or None if invalid.
    """
    domain = settings.AUTH0_DOMAIN
    audience = settings.AUTH0_AUDIENCE
    if not domain:
        return None

    try:
        header = jwt.get_unverified_header(token)
    except JWTError:
        return None

    if header.get("alg") != "RS256":
        return None

    kid = header.get("kid")
    if not kid:
        return None

    jwks = await get_jwks(domain)
    matching_key = next((k for k in jwks.get("keys", []) if k.get("kid") == kid), None)

    # If key ID is unknown, attempt one cache-busting refresh
    if not matching_key:
        jwks = await get_jwks(domain, force_refresh=True)
        matching_key = next((k for k in jwks.get("keys", []) if k.get("kid") == kid), None)

    if not matching_key:
        logger.warning(f"Auth0 token signed with unrecognized key id: {kid}")
        return None

    issuer = settings.AUTH0_ISSUER or f"https://{domain}/"
    if not issuer.endswith("/"):
        issuer = f"{issuer}/"

    try:
        payload = jwt.decode(
            token,
            matching_key,
            algorithms=settings.AUTH0_ALGORITHMS,
            audience=audience,
            issuer=issuer,
        )
        return payload
    except JWTError as exc:
        logger.debug(f"Auth0 token validation failed: {exc}")
        return None
    except Exception as exc:
        logger.error(f"Unexpected error validating Auth0 token: {exc}")
        return None
