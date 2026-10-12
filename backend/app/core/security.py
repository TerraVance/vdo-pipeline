"""
JWT verification using Supabase's public JWKS endpoint.

Strategy:
  - On first auth check, fetch the public key from Supabase's JWKS endpoint.
  - Cache it in memory for the lifetime of the process.
  - Verify all subsequent JWTs locally using PyJWT — no network call per request.

This eliminates the timeout issue caused by calling db.auth.get_user(token) on every request.
"""
import jwt
import httpx
from typing import Optional
from functools import lru_cache
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.core.config import get_settings
from app.core.logging import logger

# auto_error=False allows optional auth endpoints to handle missing tokens
security = HTTPBearer(auto_error=False)


@lru_cache(maxsize=1)
def _get_public_key() -> jwt.PyJWK:
    """
    Fetch Supabase's EC public signing key from the JWKS endpoint.
    Result is cached for the lifetime of the process (lru_cache).
    Only called once on the first authenticated request.
    """
    settings = get_settings()
    supabase_url = settings.supabase_url.rstrip("/")
    jwks_url = f"{supabase_url}/auth/v1/.well-known/jwks.json"

    try:
        response = httpx.get(jwks_url, timeout=10.0)
        response.raise_for_status()
        jwks = response.json()
        # Supabase projects typically have one key
        return jwt.PyJWK(jwks["keys"][0])
    except Exception as e:
        logger.error(f"Failed to fetch Supabase public key from JWKS ({jwks_url}): {e}")
        raise RuntimeError(f"Failed to fetch Supabase public key from JWKS: {e}")


def _verify_token(token: str) -> Optional[str]:
    """
    Verify a Supabase JWT locally using the cached public key.
    Returns the user UUID (sub claim) or None if invalid.
    No network call is made after the first request.
    """
    try:
        signing_key = _get_public_key()
        payload = jwt.decode(
            token,
            signing_key,
            algorithms=["ES256"],
            audience="authenticated",
            options={"verify_exp": True},
        )
        return payload.get("sub")  # sub = user UUID in Supabase JWTs
    except jwt.ExpiredSignatureError:
        logger.debug("Supabase JWT has expired")
        return None
    except jwt.InvalidTokenError as e:
        logger.warning(f"Invalid Supabase JWT token: {e}")
        return None
    except Exception as e:
        logger.error(f"JWT verification error: {e}")
        return None


def get_current_user_optional(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> Optional[str]:
    """
    Validates the Supabase JWT token locally.
    Returns the user_id (UUID string) if valid, or None if no/invalid token.
    Allows anonymous access — ownership is handled per-endpoint.
    """
    if not credentials:
        return None
    return _verify_token(credentials.credentials)


def get_current_user_required(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> str:
    """
    Strict validation — requires a valid Supabase JWT token.
    Raises 401 Unauthorized if missing or invalid.
    """
    user_id = get_current_user_optional(credentials)
    if not user_id:
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing authentication token"
        )
    return user_id
