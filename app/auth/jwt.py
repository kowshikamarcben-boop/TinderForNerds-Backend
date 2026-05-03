"""
JWT verification for Supabase-issued tokens.

Newer Supabase projects use ES256 (ECDSA P-256) and publish multiple keys
via JWKS at /auth/v1/.well-known/jwks.json, each with a `kid`.  We look up
the matching key by `kid` from the token header.  Older projects used HS256.
"""
from functools import lru_cache
from typing import Any

import httpx
from jose import ExpiredSignatureError, JWTError, jwk, jwt

from app.config import settings

_AUDIENCE = "authenticated"
_JWKS_URL = f"{settings.supabase_url}/auth/v1/.well-known/jwks.json"


@lru_cache(maxsize=1)
def _jwks_keys() -> dict[str, Any]:
    """Fetch and cache all ES256 public keys indexed by kid."""
    try:
        resp = httpx.get(_JWKS_URL, timeout=10)
        resp.raise_for_status()
        result: dict[str, Any] = {}
        for k in resp.json().get("keys", []):
            if k.get("alg") == "ES256":
                try:
                    result[k["kid"]] = jwk.construct(k, algorithm="ES256")
                except Exception:
                    pass
        return result
    except Exception:
        return {}


@lru_cache(maxsize=1)
def _hs256_secret() -> bytes:
    """Raw JWT secret bytes for HS256 verification."""
    return settings.supabase_jwt_secret.encode()


def verify_jwt(token: str) -> dict[str, Any]:
    """
    Decode and verify a Supabase JWT (ES256 or HS256).
    Raises ValueError on any failure.
    Returns full claims dict on success.
    """
    try:
        header = jwt.get_unverified_header(token)
        alg = header.get("alg", "HS256")
    except JWTError:
        raise ValueError("token_invalid: malformed header")

    try:
        if alg == "ES256":
            kids = _jwks_keys()
            kid = header.get("kid")
            # Pick key by kid; fall back to first available
            key = kids.get(kid) if kid else None
            if key is None:
                key = next(iter(kids.values()), None)
            if key is None:
                raise ValueError("token_invalid: no JWKS key available")
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
                _hs256_secret(),
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
