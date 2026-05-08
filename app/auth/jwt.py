"""
JWT verification for Supabase-issued tokens.

Newer Supabase projects use ES256 (ECDSA P-256) and publish multiple keys
via JWKS at /auth/v1/.well-known/jwks.json, each with a `kid`.  We look up
the matching key by `kid` from the token header.  Older projects used HS256.
"""
import time
from typing import Any

import httpx
from jose import ExpiredSignatureError, JWTError, jwk, jwt

from app.config import settings

_AUDIENCE = "authenticated"
_JWKS_URL = f"{settings.supabase_url}/auth/v1/.well-known/jwks.json"
_JWKS_TTL = 3600  # 1 hour

_jwks_cache: dict[str, Any] = {}
_jwks_fetched_at: float = 0.0


def _jwks_keys(force_refresh: bool = False) -> dict[str, Any]:
    """Fetch and cache ES256 public keys indexed by kid. Refreshes every hour."""
    global _jwks_cache, _jwks_fetched_at
    now = time.monotonic()
    if not force_refresh and _jwks_cache and (now - _jwks_fetched_at) < _JWKS_TTL:
        return _jwks_cache
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
        _jwks_cache = result
        _jwks_fetched_at = now
        return result
    except Exception:
        return _jwks_cache  # return stale on failure rather than empty


_hs256_secret_cache: bytes | None = None


def _hs256_secret() -> bytes:
    global _hs256_secret_cache
    if _hs256_secret_cache is None:
        _hs256_secret_cache = settings.supabase_jwt_secret.encode()
    return _hs256_secret_cache


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
            kid = header.get("kid")
            kids = _jwks_keys()
            key = kids.get(kid) if kid else None
            # If kid not found, refresh cache once (handles key rotation)
            if key is None and kid:
                kids = _jwks_keys(force_refresh=True)
                key = kids.get(kid)
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
