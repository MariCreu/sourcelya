from datetime import datetime, timedelta, timezone

import jwt

from app.core.config import get_settings
from tests.conftest import make_supabase_token

settings = get_settings()


def test_me_requires_a_token(client):
    response = client.get("/api/auth/me")
    assert response.status_code == 403  # no Authorization header at all


def test_me_rejects_garbage_token(client):
    response = client.get("/api/auth/me", headers={"Authorization": "Bearer not-a-jwt"})
    assert response.status_code == 401


def test_me_rejects_expired_token(client):
    token = make_supabase_token(expired=True)
    response = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401


def test_me_rejects_wrong_signing_secret(client):
    now = datetime.now(timezone.utc)
    token = jwt.encode(
        {
            "sub": "abc",
            "email": "x@example.com",
            "aud": "authenticated",
            "exp": now + timedelta(hours=1),
        },
        "some-other-secret",
        algorithm="HS256",
    )
    response = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401


def test_me_rejects_wrong_audience(client):
    token = make_supabase_token(audience="not-authenticated")
    response = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401


def test_me_rejects_token_missing_subject(client):
    now = datetime.now(timezone.utc)
    token = jwt.encode(
        {"aud": "authenticated", "exp": now + timedelta(hours=1)},
        settings.supabase_jwt_secret,
        algorithm="HS256",
    )
    response = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401


def test_me_creates_local_user_on_first_call(client, auth_header):
    headers = auth_header(email="new-user@example.com")
    response = client.get("/api/auth/me", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["user"]["email"] == "new-user@example.com"
    assert body["company"] is None


def test_me_is_idempotent_for_the_same_user(client, auth_header):
    headers = auth_header(user_id="11111111-1111-1111-1111-111111111111")
    first = client.get("/api/auth/me", headers=headers).json()
    second = client.get("/api/auth/me", headers=headers).json()
    assert first["user"]["id"] == second["user"]["id"]
