"""
Auth0 RS256 Token Verification & Public JWKS Management Service for Networth Microservice.

Handles:
- Fetching and caching public JWKS with 24h TTL.
- Key rotation and cache-busting on unknown kid.
- RS256 JWT decoding, signature verification, expiry, and claim validation.
"""

import os
import time
import inspect
import logging
from typing import Optional, Dict, Any

import httpx
from jose import jwt, JWTError, ExpiredSignatureError
from jose.exceptions import JWTClaimsError

try:
    from ..config import settings
except (ImportError, ValueError):
    from app.config import settings

logger = logging.getLogger(__name__)

_jwks_cache: Optional[Dict[str, Any]] = None
_jwks_cache_timestamp: float = 0.0
JWKS_CACHE_TTL_SECONDS: float = 86400.0  # 24 hours


def clear_jwks_cache() -> None:
    """Clear in-memory JWKS cache (useful for testing and manual cache-busting)."""
    global _jwks_cache, _jwks_cache_timestamp
    _jwks_cache = None
    _jwks_cache_timestamp = 0.0


async def fetch_jwks(domain: Optional[str] = None) -> Dict[str, Any]:
    """Fetch public JWKS keys from Auth0 tenant endpoint."""
    dom = domain or settings.AUTH0_DOMAIN or "jayam04.eu.auth0.com"
    jwks_url = f"https://{dom}/.well-known/jwks.json"
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(jwks_url)
        resp.raise_for_status()
        return resp.json()


async def get_jwks(force_refresh: bool = False, domain: Optional[str] = None) -> Dict[str, Any]:
    """
    Retrieve cached JWKS keys, refreshing from network if cache is empty, expired,
    or force_refresh is True.
    """
    global _jwks_cache, _jwks_cache_timestamp
    now = time.time()
    if not force_refresh and _jwks_cache is not None and (now - _jwks_cache_timestamp) < JWKS_CACHE_TTL_SECONDS:
        return _jwks_cache

    jwks_res = fetch_jwks(domain=domain)
    if inspect.isawaitable(jwks_res):
        data = await jwks_res
    else:
        data = jwks_res

    _jwks_cache = data
    _jwks_cache_timestamp = now
    return _jwks_cache


async def verify_auth0_token(token: str) -> Optional[Dict[str, Any]]:
    """
    Verify RS256 Auth0 JWT token against public JWKS.
    Returns decoded token payload if valid, or None if invalid/expired/untrusted.
    """
    if not token or not isinstance(token, str):
        return None

    cleaned_token = token.strip()
    if not cleaned_token:
        return None

    try:
        header = jwt.get_unverified_header(cleaned_token)
    except Exception:
        return None

    alg = header.get("alg")
    allowed_algorithms = getattr(settings, "AUTH0_ALGORITHMS", ["RS256"]) or ["RS256"]
    if not alg or alg not in allowed_algorithms or alg != "RS256":
        return None

    kid = header.get("kid")
    if not kid:
        return None

    # Retrieve JWKS
    try:
        jwks_res = get_jwks()
        if inspect.isawaitable(jwks_res):
            jwks = await jwks_res
        else:
            jwks = jwks_res
    except Exception as e:
        logger.warning(f"Failed to retrieve JWKS: {e}")
        return None

    keys = jwks.get("keys", []) if isinstance(jwks, dict) else []
    matching_key = next((k for k in keys if isinstance(k, dict) and k.get("kid") == kid), None)

    # Key rotation / cache-busting retry
    if matching_key is None:
        try:
            jwks_res = get_jwks(force_refresh=True)
            if inspect.isawaitable(jwks_res):
                jwks = await jwks_res
            else:
                jwks = jwks_res
            keys = jwks.get("keys", []) if isinstance(jwks, dict) else []
            matching_key = next((k for k in keys if isinstance(k, dict) and k.get("kid") == kid), None)
        except Exception as e:
            logger.warning(f"Failed to refresh JWKS for kid {kid}: {e}")
            return None

    if matching_key is None:
        logger.warning(f"Auth0 token kid '{kid}' not found in JWKS keys")
        return None

    # Determine audience and issuer
    configured_aud = getattr(settings, "AUTH0_AUDIENCE", "http://localhost:8000") or "http://localhost:8000"
    client_id = getattr(settings, "AUTH0_CLIENT_ID", None) or os.getenv("AUTH0_CLIENT_ID") or os.getenv("NEXT_PUBLIC_AUTH0_CLIENT_ID") or "wTsdPwbGO91s4SjnzhA4pC9ik4MFEjby"
    allowed_audiences = [a for a in [configured_aud, client_id] if a]

    domain = getattr(settings, "AUTH0_DOMAIN", "jayam04.eu.auth0.com") or "jayam04.eu.auth0.com"
    clean_domain = domain.replace("https://", "").replace("http://", "").strip("/")

    raw_issuer = getattr(settings, "AUTH0_ISSUER", None) or f"https://{clean_domain}/"
    if not raw_issuer.startswith("http://") and not raw_issuer.startswith("https://"):
        raw_issuer = f"https://{raw_issuer}"
    if not raw_issuer.endswith("/"):
        raw_issuer = f"{raw_issuer}/"
    default_issuer = raw_issuer

    valid_issuers = {
        default_issuer,
        default_issuer.rstrip("/"),
        f"https://{clean_domain}/",
        f"https://{clean_domain}",
        f"http://{clean_domain}/",
        f"http://{clean_domain}",
    }

    expected_iss = default_issuer
    expected_aud = configured_aud
    try:
        unverified_claims = jwt.get_unverified_claims(cleaned_token)
        token_iss = unverified_claims.get("iss")
        if token_iss and token_iss in valid_issuers:
            expected_iss = token_iss

        token_aud = unverified_claims.get("aud")
        if token_aud:
            if isinstance(token_aud, str) and token_aud in allowed_audiences:
                expected_aud = token_aud
            elif isinstance(token_aud, list):
                matching_aud = next((a for a in token_aud if a in allowed_audiences), None)
                if matching_aud:
                    expected_aud = matching_aud
    except Exception as e:
        logger.warning(f"Failed to read unverified claims from Auth0 token: {e}")
        return None

    try:
        payload = jwt.decode(
            cleaned_token,
            matching_key,
            algorithms=["RS256"],
            audience=expected_aud,
            issuer=expected_iss,
            options={
                "verify_signature": True,
                "verify_aud": bool(expected_aud),
                "verify_iss": bool(expected_iss),
                "verify_exp": True,
                "verify_nbf": True,
                "verify_iat": True,
            }
        )

        # Check future iat with 2-minute clock drift margin
        iat = payload.get("iat")
        if iat is not None and iat > (time.time() + 120):
            logger.warning(f"Auth0 token iat {iat} is in future (> 2 min drift)")
            return None

        # Verify subject is present and non-empty
        sub = payload.get("sub")
        if not sub or not str(sub).strip():
            logger.warning("Auth0 token missing valid sub claim")
            return None

        return payload
    except (ExpiredSignatureError, JWTClaimsError, JWTError) as e:
        logger.warning(f"Auth0 token validation failed: {e}")
        return None
    except Exception as e:
        logger.warning(f"Unexpected error validating Auth0 token: {e}")
        return None
