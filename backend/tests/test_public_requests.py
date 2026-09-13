from datetime import datetime, timedelta, timezone

from app.models.compliance_request import ComplianceRequest
from tests.conftest import TestingSessionLocal

USER_A = "11111111-1111-1111-1111-111111111111"
USER_B = "22222222-2222-2222-2222-222222222222"


def _onboard(client, headers, name="Acme BV", country="NL"):
    return client.post("/api/companies", json={"name": name, "country": country}, headers=headers)


def _create_supplier(client, headers, name="Shenzhen Wonderful Packaging", email="s@example.com"):
    return client.post(
        "/api/suppliers", json={"name": name, "email": email}, headers=headers
    ).json()


def _create_product(client, headers, supplier_id, name="Bamboo toothbrush"):
    return client.post(
        "/api/products", json={"name": name, "supplier_id": supplier_id}, headers=headers
    ).json()


def _create_component(client, headers, product_id, name="Outer box"):
    return client.post(
        f"/api/products/{product_id}/packaging-components",
        json={"name": name, "packaging_type": "box"},
        headers=headers,
    ).json()


def _send_full_request(client, headers, language="es"):
    supplier = _create_supplier(client, headers)
    product = _create_product(client, headers, supplier["id"])
    component = _create_component(client, headers, product["id"])
    request = client.post(
        "/api/requests",
        json={"supplier_id": supplier["id"], "product_ids": [product["id"]], "language": language},
        headers=headers,
    ).json()
    sent = client.post(f"/api/requests/{request['id']}/send", headers=headers).json()
    token = sent["request_url"].rsplit("/", 1)[-1]
    return request, token, component


def _expire_token(request_id: str):
    with TestingSessionLocal() as db:
        record = db.get(ComplianceRequest, request_id)
        record.token_expires_at = datetime.now(timezone.utc) - timedelta(days=1)
        db.commit()


def test_invalid_token_returns_404(client):
    response = client.get("/api/public/requests/not-a-real-token")
    assert response.status_code == 404


def test_expired_token_returns_410(client, auth_header):
    headers = auth_header(user_id=USER_A)
    _onboard(client, headers)
    request, token, _component = _send_full_request(client, headers)
    _expire_token(request["id"])

    response = client.get(f"/api/public/requests/{token}")
    assert response.status_code == 410


def test_revoked_token_returns_403(client, auth_header):
    headers = auth_header(user_id=USER_A)
    _onboard(client, headers)
    request, token, _component = _send_full_request(client, headers)

    client.post(f"/api/requests/{request['id']}/revoke", headers=headers)

    response = client.get(f"/api/public/requests/{token}")
    assert response.status_code == 403


def test_token_never_exposes_company_or_supplier_id(client, auth_header):
    headers = auth_header(user_id=USER_A)
    _onboard(client, headers)
    _request, token, _component = _send_full_request(client, headers)

    body = client.get(f"/api/public/requests/{token}").json()
    assert "company_id" not in body
    assert "supplier_id" not in body
    assert body["company_name"] == "Acme BV"


def test_first_access_flips_status_to_opened(client, auth_header):
    headers = auth_header(user_id=USER_A)
    _onboard(client, headers)
    request, token, _component = _send_full_request(client, headers)

    public_view = client.get(f"/api/public/requests/{token}").json()
    assert public_view["status"] == "opened"

    company_view = client.get(f"/api/requests/{request['id']}", headers=headers).json()
    assert company_view["status"] == "opened"
    assert company_view["opened_at"] is not None


def test_save_progress_updates_component_and_sets_in_progress(client, auth_header):
    headers = auth_header(user_id=USER_A)
    _onboard(client, headers)
    request, token, component = _send_full_request(client, headers)
    client.get(f"/api/public/requests/{token}")

    response = client.patch(
        f"/api/public/requests/{token}",
        json={
            "components": [
                {
                    "id": component["id"],
                    "material": "cardboard",
                    "weight_grams": 42.5,
                    "recycled_content_percentage": 30,
                    "packaging_reference": "REF-1",
                    "notes": "recyclable",
                }
            ]
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "in_progress"
    saved_component = body["products"][0]["packaging_components"][0]
    assert saved_component["material"] == "cardboard"
    assert saved_component["weight_grams"] == 42.5

    company_view = client.get(f"/api/requests/{request['id']}", headers=headers).json()
    assert company_view["status"] == "in_progress"


def test_save_progress_rejects_component_from_another_request(client, auth_header):
    headers = auth_header(user_id=USER_A)
    _onboard(client, headers)
    _request_1, token_1, _component_1 = _send_full_request(client, headers)
    _request_2, _token_2, component_2 = _send_full_request(client, headers, language="en")

    response = client.patch(
        f"/api/public/requests/{token_1}",
        json={"components": [{"id": component_2["id"], "material": "plastic"}]},
    )
    assert response.status_code == 400


def test_save_progress_rejects_component_from_another_companys_product(client, auth_header):
    headers_a = auth_header(user_id=USER_A, email="a@example.com")
    headers_b = auth_header(user_id=USER_B, email="b@example.com")
    _onboard(client, headers_a, name="Company A")
    _onboard(client, headers_b, name="Company B")
    _request_a, token_a, _component_a = _send_full_request(client, headers_a)
    _request_b, _token_b, component_b = _send_full_request(client, headers_b)

    response = client.patch(
        f"/api/public/requests/{token_a}",
        json={"components": [{"id": component_b["id"], "material": "plastic"}]},
    )
    assert response.status_code == 400


def test_submit_sets_status_and_is_idempotent(client, auth_header):
    headers = auth_header(user_id=USER_A)
    _onboard(client, headers)
    request, token, _component = _send_full_request(client, headers)
    client.get(f"/api/public/requests/{token}")

    first_submit = client.post(f"/api/public/requests/{token}/submit")
    assert first_submit.status_code == 200
    assert first_submit.json()["status"] == "submitted"

    second_submit = client.post(f"/api/public/requests/{token}/submit")
    assert second_submit.status_code == 200
    assert second_submit.json()["status"] == "submitted"

    company_view = client.get(f"/api/requests/{request['id']}", headers=headers).json()
    assert company_view["status"] == "submitted"
    assert company_view["submitted_at"] is not None


def test_cannot_save_progress_after_submit(client, auth_header):
    headers = auth_header(user_id=USER_A)
    _onboard(client, headers)
    request, token, component = _send_full_request(client, headers)
    client.post(f"/api/public/requests/{token}/submit")

    response = client.patch(
        f"/api/public/requests/{token}",
        json={"components": [{"id": component["id"], "material": "plastic"}]},
    )
    assert response.status_code == 409
