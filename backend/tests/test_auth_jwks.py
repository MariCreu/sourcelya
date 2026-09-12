"""Exercises the production JWT verification path end-to-end: a real EC
keypair, a real local JWKS HTTP endpoint, and a real PyJWKClient fetch —
not a mocked signature check. `tests/test_auth.py` covers the HS256
dev/test fallback; this file is what actually proves the JWKS strategy
(the one production runs) works and fails closed.
"""

import json
import threading
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from jwt.algorithms import ECAlgorithm

from app.core.security import InvalidTokenError, JWKSTokenVerifier

KID = "test-key-1"
ISSUER = "https://test-project.supabase.co/auth/v1"
AUDIENCE = "authenticated"
SUBJECT = "11111111-1111-1111-1111-111111111111"


def _build_jwks(public_key) -> dict:
    algo = ECAlgorithm(ECAlgorithm.SHA256)
    jwk = json.loads(algo.to_jwk(public_key))
    jwk.update({"kid": KID, "use": "sig", "alg": "ES256"})
    return {"keys": [jwk]}


def _make_handler(jwks_payload: dict) -> type:
    body = json.dumps(jwks_payload).encode()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format, *args):  # noqa: A002 - silence request logging
            pass

    return Handler


@pytest.fixture(scope="module")
def jwks_server():
    private_key = ec.generate_private_key(ec.SECP256R1())
    server = HTTPServer(("127.0.0.1", 0), _make_handler(_build_jwks(private_key.public_key())))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    port = server.server_address[1]
    try:
        yield {"url": f"http://127.0.0.1:{port}/jwks.json", "private_key": private_key}
    finally:
        server.shutdown()
        thread.join(timeout=2)


def _verifier(jwks_server, **overrides) -> JWKSTokenVerifier:
    kwargs = dict(
        jwks_url=jwks_server["url"], issuer=ISSUER, audience=AUDIENCE, allowed_algorithms=["ES256"]
    )
    kwargs.update(overrides)
    return JWKSTokenVerifier(**kwargs)


def _sign(private_key, *, kid: str | None = KID, alg: str = "ES256", **claim_overrides) -> str:
    now = datetime.now(timezone.utc)
    claims = {
        "sub": SUBJECT,
        "email": "supplier@example.com",
        "aud": AUDIENCE,
        "iss": ISSUER,
        "exp": now + timedelta(hours=1),
        "iat": now,
    }
    claims.update(claim_overrides)
    headers = {"kid": kid} if kid else None
    return jwt.encode(claims, private_key, algorithm=alg, headers=headers)


def test_valid_token_is_verified_against_a_real_jwks_endpoint(jwks_server):
    token = _sign(jwks_server["private_key"])
    identity = _verifier(jwks_server).verify(token)
    assert identity.user_id == SUBJECT
    assert identity.email == "supplier@example.com"


def test_rejects_expired_token(jwks_server):
    now = datetime.now(timezone.utc)
    token = _sign(jwks_server["private_key"], exp=now - timedelta(minutes=1))
    with pytest.raises(InvalidTokenError):
        _verifier(jwks_server).verify(token)


def test_rejects_wrong_issuer(jwks_server):
    token = _sign(jwks_server["private_key"], iss="https://someone-else.supabase.co/auth/v1")
    with pytest.raises(InvalidTokenError):
        _verifier(jwks_server).verify(token)


def test_rejects_wrong_audience(jwks_server):
    token = _sign(jwks_server["private_key"], aud="not-authenticated")
    with pytest.raises(InvalidTokenError):
        _verifier(jwks_server).verify(token)


def test_rejects_token_missing_subject(jwks_server):
    now = datetime.now(timezone.utc)
    token = jwt.encode(
        {"aud": AUDIENCE, "iss": ISSUER, "exp": now + timedelta(hours=1)},
        jwks_server["private_key"],
        algorithm="ES256",
        headers={"kid": KID},
    )
    with pytest.raises(InvalidTokenError):
        _verifier(jwks_server).verify(token)


def test_rejects_token_signed_with_an_unknown_key_id(jwks_server):
    token = _sign(jwks_server["private_key"], kid="some-other-key")
    with pytest.raises(InvalidTokenError):
        _verifier(jwks_server).verify(token)


def test_rejects_a_genuinely_valid_token_if_its_algorithm_is_outside_the_allowlist(jwks_server):
    """The core "no dynamic algorithm" guarantee: this token is legitimately
    signed by the right key with ES256, but the verifier only trusts RS256
    here — it must be rejected outright, not silently accepted because the
    signature itself checks out.
    """
    token = _sign(jwks_server["private_key"])
    verifier = _verifier(jwks_server, allowed_algorithms=["RS256"])
    with pytest.raises(InvalidTokenError):
        verifier.verify(token)


def test_constructor_refuses_the_none_algorithm(jwks_server):
    with pytest.raises(ValueError):
        _verifier(jwks_server, allowed_algorithms=["none"])


def test_constructor_refuses_an_empty_algorithm_list(jwks_server):
    with pytest.raises(ValueError):
        _verifier(jwks_server, allowed_algorithms=[])
