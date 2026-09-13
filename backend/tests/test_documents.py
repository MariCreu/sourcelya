from app.models.audit_event import AuditEvent
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


def _send_full_request(client, headers, language="es"):
    supplier = _create_supplier(client, headers)
    product = _create_product(client, headers, supplier["id"])
    request = client.post(
        "/api/requests",
        json={"supplier_id": supplier["id"], "product_ids": [product["id"]], "language": language},
        headers=headers,
    ).json()
    sent = client.post(f"/api/requests/{request['id']}/send", headers=headers).json()
    token = sent["request_url"].rsplit("/", 1)[-1]
    return request, token


def _upload(client, token, filename="spec.pdf", content=b"%PDF-1.4 fake content", content_type="application/pdf"):
    return client.post(
        f"/api/public/requests/{token}/documents",
        files={"file": (filename, content, content_type)},
    )


def test_upload_document_appears_for_supplier_and_company(client, auth_header):
    headers = auth_header(user_id=USER_A)
    _onboard(client, headers)
    request, token = _send_full_request(client, headers)

    response = _upload(client, token)
    assert response.status_code == 200
    body = response.json()
    assert len(body["documents"]) == 1
    assert body["documents"][0]["filename"] == "spec.pdf"
    assert body["documents"][0]["content_type"] == "application/pdf"

    company_view = client.get(f"/api/requests/{request['id']}", headers=headers).json()
    assert len(company_view["documents"]) == 1
    assert company_view["documents"][0]["filename"] == "spec.pdf"


def test_upload_rejects_disallowed_extension(client, auth_header):
    headers = auth_header(user_id=USER_A)
    _onboard(client, headers)
    _request, token = _send_full_request(client, headers)

    response = _upload(client, token, filename="virus.exe", content_type="application/octet-stream")
    assert response.status_code == 400


def test_upload_rejects_invalid_token(client):
    response = _upload(client, "not-a-real-token")
    assert response.status_code == 404


def test_delete_document_before_submit(client, auth_header):
    headers = auth_header(user_id=USER_A)
    _onboard(client, headers)
    request, token = _send_full_request(client, headers)
    uploaded = _upload(client, token).json()
    document_id = uploaded["documents"][0]["id"]

    response = client.delete(f"/api/public/requests/{token}/documents/{document_id}")
    assert response.status_code == 200
    assert response.json()["documents"] == []

    company_view = client.get(f"/api/requests/{request['id']}", headers=headers).json()
    assert company_view["documents"] == []


def test_upload_rejected_after_submit(client, auth_header):
    headers = auth_header(user_id=USER_A)
    _onboard(client, headers)
    _request, token = _send_full_request(client, headers)
    client.post(f"/api/public/requests/{token}/submit")

    response = _upload(client, token)
    assert response.status_code == 409


def test_delete_rejected_after_submit(client, auth_header):
    headers = auth_header(user_id=USER_A)
    _onboard(client, headers)
    _request, token = _send_full_request(client, headers)
    uploaded = _upload(client, token).json()
    document_id = uploaded["documents"][0]["id"]

    client.post(f"/api/public/requests/{token}/submit")

    response = client.delete(f"/api/public/requests/{token}/documents/{document_id}")
    assert response.status_code == 409


def test_cannot_delete_document_from_another_request(client, auth_header):
    headers = auth_header(user_id=USER_A)
    _onboard(client, headers)
    _request_1, token_1 = _send_full_request(client, headers)
    _request_2, token_2 = _send_full_request(client, headers, language="en")

    uploaded_on_2 = _upload(client, token_2).json()
    document_id = uploaded_on_2["documents"][0]["id"]

    response = client.delete(f"/api/public/requests/{token_1}/documents/{document_id}")
    assert response.status_code == 404

    # Still there via its real request's token.
    still_there = client.get(f"/api/public/requests/{token_2}").json()
    assert len(still_there["documents"]) == 1


def test_company_can_download_its_own_document(client, auth_header):
    headers = auth_header(user_id=USER_A)
    _onboard(client, headers)
    request, token = _send_full_request(client, headers)
    original_content = b"%PDF-1.4 hello world"
    _upload(client, token, content=original_content)
    document_id = client.get(f"/api/requests/{request['id']}", headers=headers).json()["documents"][0]["id"]

    response = client.get(f"/api/documents/{document_id}/download", headers=headers)
    assert response.status_code == 200
    assert response.content == original_content
    assert response.headers["content-type"] == "application/pdf"
    assert "spec.pdf" in response.headers["content-disposition"]


def test_another_company_cannot_download_the_document(client, auth_header):
    headers_a = auth_header(user_id=USER_A, email="a@example.com")
    headers_b = auth_header(user_id=USER_B, email="b@example.com")
    _onboard(client, headers_a, name="Company A")
    _onboard(client, headers_b, name="Company B")
    request, token = _send_full_request(client, headers_a)
    _upload(client, token)
    document_id = client.get(f"/api/requests/{request['id']}", headers=headers_a).json()["documents"][0]["id"]

    response = client.get(f"/api/documents/{document_id}/download", headers=headers_b)
    assert response.status_code == 404


def test_upload_and_delete_record_audit_events(client, auth_header):
    headers = auth_header(user_id=USER_A)
    _onboard(client, headers)
    request, token = _send_full_request(client, headers)
    uploaded = _upload(client, token).json()
    document_id = uploaded["documents"][0]["id"]
    client.delete(f"/api/public/requests/{token}/documents/{document_id}")

    with TestingSessionLocal() as db:
        event_types = [
            event.event_type
            for event in db.query(AuditEvent).filter(AuditEvent.entity_id == document_id).all()
        ]
    assert "document_uploaded" in event_types
    assert "document_deleted" in event_types
