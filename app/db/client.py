"""
Supabase client factories.

- get_admin_client()  → service-role client for cross-user/system ops
- get_user_client(token) → user-scoped client; RLS enforced
"""
import re as _re
from functools import lru_cache
from typing import Any

from fastapi import Request
from supabase import Client, create_client

from app.config import settings


def _create_client_allow_sb_secret(url: str, key: str) -> Client:
    """
    supabase-py 2.7+ rejects keys without dots (JWT format check).
    New Supabase projects issue sb_secret_* keys that have no dots.
    We patch the re module reference inside supabase._sync.client for the
    duration of the create_client() call so that sb_secret_* passes through.
    """
    if _re.match(r"^[A-Za-z0-9-_=]+\.[A-Za-z0-9-_=]+\.?", key):
        return create_client(url, key)

    import supabase._sync.client as _sc

    _orig_re = _sc.re

    class _ReProxy:
        def match(self, pattern: str, string: Any, *args: Any, **kwargs: Any) -> Any:
            # Allow sb_secret_* through the JWT-format check
            if (
                isinstance(string, str)
                and string.startswith("sb_secret_")
                and "A-Za-z0-9" in pattern
            ):
                return True
            return _orig_re.match(pattern, string, *args, **kwargs)

        def __getattr__(self, name: str) -> Any:
            return getattr(_orig_re, name)

    _sc.re = _ReProxy()
    try:
        client = create_client(url, key)
    finally:
        _sc.re = _orig_re

    return client


@lru_cache(maxsize=1)
def get_admin_client() -> Client:
    """Service-role client. Use only for system/cross-user operations."""
    return _create_client_allow_sb_secret(
        settings.supabase_url, settings.supabase_service_role_key
    )


def get_user_client(request: Request) -> Client:
    """
    Per-request client initialised with the caller's JWT.
    RLS policies enforce row-level access automatically.
    Falls back to anon role when no Authorization header present.
    """
    auth_header = request.headers.get("Authorization", "")
    token = auth_header.removeprefix("Bearer ").strip()
    client = create_client(settings.supabase_url, settings.supabase_anon_key)
    if token:
        client.postgrest.auth(token)
    return client
