from app.integrations.extraction.base import DocumentExtractionResult, ExtractionError

USER_A = "11111111-1111-1111-1111-111111111111"


def _onboard(client, headers, name="Acme BV", country="NL"):
    return client.post("/api/companies", json={"name": name, "country": country}, headers=headers)


def _setup_and_upload(client, headers, fake_extraction_service):
    supplier = client.post(
        "/api/suppliers", json={"name": "Supplier", "email": "s@example.com"}, headers=headers
    ).json()
    product = client.post(
        "/api/products",
        json={"name": "Widget", "supplier_id": supplier["id"]},
        headers=headers,
    ).json()
    client.post(
        f"/api/products/{product['id']}/packaging-components",
        json={"name": "Box", "packaging_type": "box"},
        headers=headers,
    )
    request = client.post(
        "/api/requests",
        json={"supplier_id": supplier["id"], "product_ids": [product["id"]], "language": "es"},
        headers=headers,
    ).json()
    sent = client.post(f"/api/requests/{request['id']}/send", headers=headers).json()
    token = sent["request_url"].rsplit("/", 1)[-1]

    fake_extraction_service.error = ExtractionError("provider unavailable")
    client.post(
        f"/api/public/requests/{token}/documents",
        files={"file": ("spec.pdf", b"%PDF-1.4 fake", "application/pdf")},
    )
    document_id = client.get(f"/api/requests/{request['id']}", headers=headers).json()["documents"][
        0
    ]["id"]
    return request, document_id


def test_failed_extraction_can_be_retried_and_succeed(client, auth_header, fake_extraction_service):
    headers = auth_header(user_id=USER_A)
    _onboard(client, headers)
    request, document_id = _setup_and_upload(client, headers, fake_extraction_service)

    company_view = client.get(f"/api/requests/{request['id']}", headers=headers).json()
    assert company_view["documents"][0]["extraction_status"] == "failed"

    fake_extraction_service.error = None
    fake_extraction_service.result = DocumentExtractionResult(
        document_classification="other",
        fields=[],
        model="fake",
        input_tokens=1,
        output_tokens=1,
        duration_ms=1,
        estimated_cost_usd=0.0,
    )
    retry = client.post(f"/api/documents/{document_id}/retry-extraction", headers=headers)
    assert retry.status_code == 200
    assert retry.json()["extraction_status"] == "completed"


def test_retry_extraction_is_company_scoped(client, auth_header, fake_extraction_service):
    headers_a = auth_header(user_id=USER_A, email="a@example.com")
    headers_b = auth_header(user_id="22222222-2222-2222-2222-222222222222", email="b@example.com")
    _onboard(client, headers_a, name="Company A")
    _onboard(client, headers_b, name="Company B")
    _request, document_id = _setup_and_upload(client, headers_a, fake_extraction_service)

    response = client.post(f"/api/documents/{document_id}/retry-extraction", headers=headers_b)
    assert response.status_code == 404
