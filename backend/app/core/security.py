"""Verification of Supabase-issued JWTs.

PackProof never issues its own login tokens: the frontend authenticates
directly against Supabase Auth and forwards the resulting access token on
every API call. This module is the single place that trusts (or rejects)
that token, so any bug here is a full tenant-isolation bug.
"""

import hashlib
import secrets
from dataclasses import dataclass

from jose import JWTError, jwt

from app.core.config import get_settings

settings = get_settings()

SUPABASE_EXPECTED_AUDIENCE = "authenticated"


class InvalidTokenError(Exception):
    """Raised when a Supabase access token fails verification."""


@dataclass(frozen=True)
class SupabaseIdentity:
    user_id: str
    email: str | None


def decode_supabase_access_token(token: str) -> SupabaseIdentity:
    try:
        payload = jwt.decode(
            token,
            settings.supabase_jwt_secret,
            algorithms=[settings.jwt_algorithm],
            audience=SUPABASE_EXPECTED_AUDIENCE,
        )
    except JWTError as exc:
        raise InvalidTokenError(str(exc)) from exc

    subject = payload.get("sub")
    if not subject:
        raise InvalidTokenError("Token payload is missing 'sub'")

    return SupabaseIdentity(user_id=subject, email=payload.get("email"))


def generate_secure_token(num_bytes: int | None = None) -> str:
    """Cryptographically-random URL-safe token handed out to suppliers."""
    return secrets.token_urlsafe(num_bytes or settings.supplier_token_bytes)


def hash_token(raw_token: str) -> str:
    """Only the hash is ever persisted, so a DB leak does not leak live links."""
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
