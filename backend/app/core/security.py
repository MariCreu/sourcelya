"""Verification of Supabase-issued JWTs.

Sourcelya never issues its own login tokens: the frontend authenticates
directly against Supabase Auth and forwards the resulting access token on
every API call. This module is the single place that trusts (or rejects)
that token, so any bug here is a full tenant-isolation bug.

Two verifiers exist:

- `JWKSTokenVerifier` (production default, `SUPABASE_JWT_STRATEGY=jwks`):
  Supabase's current recommended approach — asymmetric signing keys,
  verified against the project's JWKS endpoint
  (`https://<project>.supabase.co/auth/v1/.well-known/jwks.json`). Checks
  signature, `exp`, `iss`, `aud`, requires `sub`, and only ever accepts the
  configured algorithm allowlist.
- `HS256TokenVerifier` (`SUPABASE_JWT_STRATEGY=hs256`): a shared secret, for
  local/offline dev or tests that can't reach a real Supabase project. Never
  the default — see `Settings.supabase_jwt_strategy` — so production stays
  on the strong path even if that variable is simply forgotten.

Both pass `algorithms=[...]` explicitly to `jwt.decode`. PyJWT then refuses
to verify a token whose header claims a different algorithm, which is what
stops the classic "alg confusion" attack (e.g. an RS256/ES256 token being
resubmitted with `alg: HS256`, using the public key as an HMAC secret) —
the algorithm is never taken dynamically from the token itself.
"""

import hashlib
import secrets
from dataclasses import dataclass
from functools import lru_cache
from typing import Protocol

import jwt
from jwt import PyJWKClient

from app.core.config import Settings, get_settings

SUPABASE_EXPECTED_AUDIENCE = "authenticated"


class InvalidTokenError(Exception):
    """Raised when a Supabase access token fails verification for any reason."""


@dataclass(frozen=True)
class SupabaseIdentity:
    user_id: str
    email: str | None


def _identity_from_payload(payload: dict) -> SupabaseIdentity:
    subject = payload.get("sub")
    if not subject:
        raise InvalidTokenError("Token payload is missing 'sub'")
    return SupabaseIdentity(user_id=subject, email=payload.get("email"))


class TokenVerifier(Protocol):
    def verify(self, token: str) -> SupabaseIdentity: ...


class JWKSTokenVerifier:
    def __init__(self, jwks_url: str, issuer: str, audience: str, allowed_algorithms: list[str]):
        if not allowed_algorithms:
            raise ValueError("allowed_algorithms must not be empty")
        if any(alg.lower() == "none" for alg in allowed_algorithms):
            raise ValueError("The 'none' algorithm is never allowed")
        self._jwks_client = PyJWKClient(jwks_url)
        self._issuer = issuer
        self._audience = audience
        self._allowed_algorithms = allowed_algorithms

    def verify(self, token: str) -> SupabaseIdentity:
        try:
            signing_key = self._jwks_client.get_signing_key_from_jwt(token)
            payload = jwt.decode(
                token,
                signing_key.key,
                algorithms=self._allowed_algorithms,
                audience=self._audience,
                issuer=self._issuer,
                options={"require": ["exp", "sub", "iss"]},
            )
        except jwt.PyJWTError as exc:
            raise InvalidTokenError(str(exc)) from exc
        return _identity_from_payload(payload)


class HS256TokenVerifier:
    """Local/offline-dev/test verifier using a shared secret."""

    def __init__(self, secret: str, audience: str, issuer: str | None = None):
        self._secret = secret
        self._audience = audience
        self._issuer = issuer

    def verify(self, token: str) -> SupabaseIdentity:
        try:
            payload = jwt.decode(
                token,
                self._secret,
                algorithms=["HS256"],
                audience=self._audience,
                issuer=self._issuer,
                options={"require": ["exp", "sub"]},
            )
        except jwt.PyJWTError as exc:
            raise InvalidTokenError(str(exc)) from exc
        return _identity_from_payload(payload)


def build_token_verifier(settings: Settings) -> TokenVerifier:
    if settings.supabase_jwt_strategy == "jwks":
        return JWKSTokenVerifier(
            jwks_url=settings.resolved_supabase_jwks_url,
            issuer=settings.resolved_supabase_issuer,
            audience=SUPABASE_EXPECTED_AUDIENCE,
            allowed_algorithms=settings.supabase_jwt_allowed_algorithms,
        )
    return HS256TokenVerifier(
        secret=settings.supabase_jwt_secret,
        audience=SUPABASE_EXPECTED_AUDIENCE,
        issuer=settings.supabase_issuer or None,
    )


@lru_cache
def get_token_verifier() -> TokenVerifier:
    return build_token_verifier(get_settings())


def decode_supabase_access_token(token: str) -> SupabaseIdentity:
    return get_token_verifier().verify(token)


def generate_secure_token(num_bytes: int | None = None) -> str:
    """Cryptographically-random URL-safe token handed out to suppliers."""
    return secrets.token_urlsafe(num_bytes or get_settings().supplier_token_bytes)


def hash_token(raw_token: str) -> str:
    """Only the hash is ever persisted, so a DB leak does not leak live links."""
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
