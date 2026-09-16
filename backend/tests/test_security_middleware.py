from tests.test_documents import _onboard, _send_full_request, _upload

USER = "33333333-3333-3333-3333-333333333333"


def test_security_headers_present_on_every_response(client):
    response = client.get("/api/health")
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
    assert "Strict-Transport-Security" in response.headers


def test_public_upload_is_rate_limited_per_ip(client, auth_header, fake_extraction_service):
    headers = auth_header(user_id=USER)
    _onboard(client, headers)
    _, token = _send_full_request(client, headers)

    # The limit is 10/minute (see app/core/rate_limit.py and the
    # @limiter.limit decorator on upload_public_document) — a compromised
    # or leaked supplier link shouldn't be able to spam uploads, each of
    # which can trigger a paid extraction call.
    for _ in range(10):
        assert _upload(client, token).status_code == 200

    limited = _upload(client, token)
    assert limited.status_code == 429
