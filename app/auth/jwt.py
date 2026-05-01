"""
JWT verification for Supabase-issued tokens.

Newer Supabase projects use ES256 (ECDSA P-256) and publish their public key
via JWKS at /auth/v1/.well-known/jwks.json.  Older projects used HS256 with
a shared secret.  We support both:

  1. Try ES256 via cached JWKS public key.
  2. Fall back to HS256 with base64-decoded secret.
"""
import base64
from functools import lru_cache
from typing import Any

import httpx
from jose import ExpiredSignatureError, JWTError, jwt
from jose.backends import ECKey

from app.config import settings

_AUDIENCE = "authenticated"
_JWKS_URL = f"{settings.supabase_url}/auth/v1/.well-known/jwks.json"


@lru_cache(maxsize=1)
def _jwks_public_key() -> ECKey | None:
    """Fetch and cache the ES256 public key from Supabase JWKS endpoint."""
    try:
        resp = httpx.get(_JWKS_URL, timeout=10)
        resp.raise_for_status()
        keys = resp.json().get("keys", [])
        ec_keys = [k for k in keys if k.get("alg") == "ES256"]
        if ec_keys:
            return ECKey(ec_keys[0], algorithm="ES256")
        return None
    except Exception:
        return None


@lru_cache(maxsize=1)
def _hs256_secret_bytes() -> bytes:
    """HS256 secret: base64-decode the dashboard value to raw bytes."""
    secret = settings.supabase_jwt_secret
    try:
        return base64.b64decode(secret)
    except Exception:
        return secret.encode()


def verify_jwt(token: str) -> dict[str, Any]:
    """
    Decode and verify a Supabase JWT (ES256 or HS256).
    Raises ValueError on any failure.
    Returns full claims dict on success.
    """
    # Detect algorithm from header without full verification
    try:
        header = jwt.get_unverified_header(token)
        alg = header.get("alg", "HS256")
    except JWTError:
        raise ValueError("token_invalid: malformed header")

    try:
        if alg == "ES256":
            key = _jwks_public_key()
            if key is None:
                raise ValueError("token_invalid: JWKS key unavailable")
            claims = jwt.decode(
                token,
                key,
                algorithms=["ES256"],
                audience=_AUDIENCE,
                options={"verify_exp": True},
            )
        else:
            claims = jwt.decode(
                token,
                _hs256_secret_bytes(),
                algorithms=["HS256"],
                audience=_AUDIENCE,
                options={"verify_exp": True},
            )
        return claims  # type: ignore[return-value]
    except ExpiredSignatureError:
        raise ValueError("token_expired")
    except JWTError as exc:
        raise ValueError(f"token_invalid: {exc}") from exc


def extract_user_id(token: str) -> str:
    claims = verify_jwt(token)
    uid = claims.get("sub")
    if not uid:
        raise ValueError("token_missing_sub")
    return str(uid)


def extract_role(token: str) -> str:
    claims = verify_jwt(token)
    app_meta = claims.get("app_metadata", {})
    return str(app_meta.get("role", "user"))


def is_admin_token(token: str) -> bool:
    return extract_role(token) == "admin"
