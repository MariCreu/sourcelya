from app.integrations.extraction.base import DocumentExtractionResult, ExtractedFieldSuggestion

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


def _create_component(client, headers, product_id, **overrides):
    payload = {"name": "Outer box", "packaging_type": "box"}
    payload.update(overrides)
    return client.post(
        f"/api/products/{product_id}/packaging-components", json=payload, headers=headers
    ).json()


def _send_request(client, headers, supplier, product):
    request = client.post(
        "/api/requests",
        json={"supplier_id": supplier["id"], "product_ids": [product["id"]], "language": "es"},
        headers=headers,
    ).json()
    sent = client.post(f"/api/requests/{request['id']}/send", headers=headers).json()
    token = sent["request_url"].rsplit("/", 1)[-1]
    return request, token


def _field(field_name, value, confidence="high"):
    return ExtractedFieldSuggestion(
        field_name=field_name,
        value=value,
        confidence=confidence,
        source_page=1,
        source_quote=value,
        quote_verified=(confidence == "high"),
    )


def _result(*fields):
    return DocumentExtractionResult(
        document_classification="packaging_specification",
        fields=list(fields),
        model="fake",
        input_tokens=10,
        output_tokens=5,
        duration_ms=10,
        estimated_cost_usd=0.0001,
    )


def _upload(client, token, filename="spec.pdf"):
    return client.post(
        f"/api/public/requests/{token}/documents",
        files={"file": (filename, b"%PDF-1.4 fake spec", "application/pdf")},
    )


def _extracted_fields(client, headers, document_id):
    return client.get(f"/api/documents/{document_id}/extracted-fields", headers=headers).json()


def test_extraction_never_overwrites_the_component_without_approval(
    client, auth_header, fake_extraction_service
):
    headers = auth_header(user_id=USER_A)
    _onboard(client, headers)
    supplier = _create_supplier(client, headers)
    product = _create_product(client, headers, supplier["id"])
    _create_component(client, headers, product["id"], packaging_type="box")
    request, token = _send_request(client, headers, supplier, product)

    fake_extraction_service.result = _result(_field("material", "Corrugated cardboard"))
    upload = _upload(client, token)
    assert upload.status_code == 200
    document_id = client.get(f"/api/requests/{request['id']}", headers=headers).json()["documents"][
        0
    ]["id"]

    fields = _extracted_fields(client, headers, document_id)
    assert len(fields) == 1
    assert fields[0]["review_status"] == "pending"

    # Component itself is untouched — nothing was written automatically.
    product_view = client.get(f"/api/products/{product['id']}", headers=headers).json()
    assert product_view["packaging_components"][0]["material"] is None
    assert "material" in product_view["packaging_components"][0]["missing_fields"]


def test_accept_applies_value_when_no_conflict(client, auth_header, fake_extraction_service):
    headers = auth_header(user_id=USER_A)
    _onboard(client, headers)
    supplier = _create_supplier(client, headers)
    product = _create_product(client, headers, supplier["id"])
    _create_component(client, headers, product["id"], packaging_type="box")
    request, token = _send_request(client, headers, supplier, product)

    fake_extraction_service.result = _result(_field("material", "Corrugated cardboard"))
    _upload(client, token)
    document_id = client.get(f"/api/requests/{request['id']}", headers=headers).json()["documents"][
        0
    ]["id"]
    field_id = _extracted_fields(client, headers, document_id)[0]["id"]

    response = client.post(
        f"/api/documents/{document_id}/extracted-fields/{field_id}/accept", json={}, headers=headers
    )
    assert response.status_code == 200
    assert response.json()["review_status"] == "accepted"

    product_view = client.get(f"/api/products/{product['id']}", headers=headers).json()
    assert product_view["packaging_components"][0]["material"] == "Corrugated cardboard"


def test_accept_returns_conflict_when_current_value_differs(
    client, auth_header, fake_extraction_service
):
    headers = auth_header(user_id=USER_A)
    _onboard(client, headers)
    supplier = _create_supplier(client, headers)
    product = _create_product(client, headers, supplier["id"])
    _create_component(client, headers, product["id"], packaging_type="box", weight_grams=42)
    request, token = _send_request(client, headers, supplier, product)

    fake_extraction_service.result = _result(_field("weight_grams", "47"))
    _upload(client, token)
    document_id = client.get(f"/api/requests/{request['id']}", headers=headers).json()["documents"][
        0
    ]["id"]
    field_id = _extracted_fields(client, headers, document_id)[0]["id"]

    response = client.post(
        f"/api/documents/{document_id}/extracted-fields/{field_id}/accept", json={}, headers=headers
    )
    assert response.status_code == 409
    body = response.json()["detail"]
    assert body["current_value"] == "42.0"
    assert body["extracted_value"] == "47"

    # Still untouched and still pending after the rejected attempt.
    product_view = client.get(f"/api/products/{product['id']}", headers=headers).json()
    assert product_view["packaging_components"][0]["weight_grams"] == 42
    assert _extracted_fields(client, headers, document_id)[0]["review_status"] == "pending"


def test_accept_with_use_extracted_resolves_the_conflict(
    client, auth_header, fake_extraction_service
):
    headers = auth_header(user_id=USER_A)
    _onboard(client, headers)
    supplier = _create_supplier(client, headers)
    product = _create_product(client, headers, supplier["id"])
    _create_component(client, headers, product["id"], packaging_type="box", weight_grams=42)
    request, token = _send_request(client, headers, supplier, product)

    fake_extraction_service.result = _result(_field("weight_grams", "47"))
    _upload(client, token)
    document_id = client.get(f"/api/requests/{request['id']}", headers=headers).json()["documents"][
        0
    ]["id"]
    field_id = _extracted_fields(client, headers, document_id)[0]["id"]

    response = client.post(
        f"/api/documents/{document_id}/extracted-fields/{field_id}/accept",
        json={"conflict_resolution": "use_extracted"},
        headers=headers,
    )
    assert response.status_code == 200
    product_view = client.get(f"/api/products/{product['id']}", headers=headers).json()
    assert product_view["packaging_components"][0]["weight_grams"] == 47


def test_accept_with_keep_current_rejects_the_field_and_leaves_component_untouched(
    client, auth_header, fake_extraction_service
):
    headers = auth_header(user_id=USER_A)
    _onboard(client, headers)
    supplier = _create_supplier(client, headers)
    product = _create_product(client, headers, supplier["id"])
    _create_component(client, headers, product["id"], packaging_type="box", weight_grams=42)
    request, token = _send_request(client, headers, supplier, product)

    fake_extraction_service.result = _result(_field("weight_grams", "47"))
    _upload(client, token)
    document_id = client.get(f"/api/requests/{request['id']}", headers=headers).json()["documents"][
        0
    ]["id"]
    field_id = _extracted_fields(client, headers, document_id)[0]["id"]

    response = client.post(
        f"/api/documents/{document_id}/extracted-fields/{field_id}/accept",
        json={"conflict_resolution": "keep_current"},
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json()["review_status"] == "rejected"

    product_view = client.get(f"/api/products/{product['id']}", headers=headers).json()
    assert product_view["packaging_components"][0]["weight_grams"] == 42


def test_reject_extracted_field(client, auth_header, fake_extraction_service):
    headers = auth_header(user_id=USER_A)
    _onboard(client, headers)
    supplier = _create_supplier(client, headers)
    product = _create_product(client, headers, supplier["id"])
    _create_component(client, headers, product["id"], packaging_type="box")
    request, token = _send_request(client, headers, supplier, product)

    fake_extraction_service.result = _result(_field("material", "Corrugated cardboard"))
    _upload(client, token)
    document_id = client.get(f"/api/requests/{request['id']}", headers=headers).json()["documents"][
        0
    ]["id"]
    field_id = _extracted_fields(client, headers, document_id)[0]["id"]

    response = client.post(
        f"/api/documents/{document_id}/extracted-fields/{field_id}/reject", headers=headers
    )
    assert response.status_code == 200
    assert response.json()["review_status"] == "rejected"

    product_view = client.get(f"/api/products/{product['id']}", headers=headers).json()
    assert product_view["packaging_components"][0]["material"] is None


def test_cannot_review_a_field_twice(client, auth_header, fake_extraction_service):
    headers = auth_header(user_id=USER_A)
    _onboard(client, headers)
    supplier = _create_supplier(client, headers)
    product = _create_product(client, headers, supplier["id"])
    _create_component(client, headers, product["id"], packaging_type="box")
    request, token = _send_request(client, headers, supplier, product)

    fake_extraction_service.result = _result(_field("material", "Corrugated cardboard"))
    _upload(client, token)
    document_id = client.get(f"/api/requests/{request['id']}", headers=headers).json()["documents"][
        0
    ]["id"]
    field_id = _extracted_fields(client, headers, document_id)[0]["id"]

    client.post(f"/api/documents/{document_id}/extracted-fields/{field_id}/reject", headers=headers)
    second = client.post(
        f"/api/documents/{document_id}/extracted-fields/{field_id}/reject", headers=headers
    )
    assert second.status_code == 409


def test_extracted_fields_are_isolated_between_companies(
    client, auth_header, fake_extraction_service
):
    headers_a = auth_header(user_id=USER_A, email="a@example.com")
    headers_b = auth_header(user_id=USER_B, email="b@example.com")
    _onboard(client, headers_a, name="Company A")
    _onboard(client, headers_b, name="Company B")
    supplier = _create_supplier(client, headers_a)
    product = _create_product(client, headers_a, supplier["id"])
    _create_component(client, headers_a, product["id"], packaging_type="box")
    request, token = _send_request(client, headers_a, supplier, product)

    fake_extraction_service.result = _result(_field("material", "Corrugated cardboard"))
    _upload(client, token)
    document_id = client.get(f"/api/requests/{request['id']}", headers=headers_a).json()[
        "documents"
    ][0]["id"]

    assert client.get(f"/api/documents/{document_id}/extracted-fields", headers=headers_b).status_code == 404

    field_id = _extracted_fields(client, headers_a, document_id)[0]["id"]
    assert (
        client.post(
            f"/api/documents/{document_id}/extracted-fields/{field_id}/accept",
            json={},
            headers=headers_b,
        ).status_code
        == 404
    )
    assert (
        client.post(
            f"/api/documents/{document_id}/extracted-fields/{field_id}/reject", headers=headers_b
        ).status_code
        == 404
    )


def test_status_calculation_service_reflects_accepted_fields(
    client, auth_header, fake_extraction_service
):
    headers = auth_header(user_id=USER_A)
    _onboard(client, headers)
    supplier = _create_supplier(client, headers)
    product = _create_product(client, headers, supplier["id"])
    _create_component(client, headers, product["id"], packaging_type="box", material="cardboard")
    request, token = _send_request(client, headers, supplier, product)

    before = client.get(f"/api/products/{product['id']}", headers=headers).json()
    assert before["status"] == "orange"
    assert "weight_grams" in before["packaging_components"][0]["missing_fields"]

    fake_extraction_service.result = _result(
        _field("weight_grams", "47"), _field("recycled_content_percentage", "80")
    )
    _upload(client, token)
    document_id = client.get(f"/api/requests/{request['id']}", headers=headers).json()["documents"][
        0
    ]["id"]
    for field in _extracted_fields(client, headers, document_id):
        client.post(
            f"/api/documents/{document_id}/extracted-fields/{field['id']}/accept",
            json={},
            headers=headers,
        )

    after = client.get(f"/api/products/{product['id']}", headers=headers).json()
    assert after["status"] == "green"
    assert after["packaging_components"][0]["missing_fields"] == []


def test_pending_review_shows_red_status_on_the_product(
    client, auth_header, fake_extraction_service
):
    headers = auth_header(user_id=USER_A)
    _onboard(client, headers)
    supplier = _create_supplier(client, headers)
    product = _create_product(client, headers, supplier["id"])
    _create_component(
        client, headers, product["id"], packaging_type="box", material="cardboard",
        weight_grams=42, recycled_content_percentage=50,
    )
    request, token = _send_request(client, headers, supplier, product)

    before = client.get(f"/api/products/{product['id']}", headers=headers).json()
    assert before["status"] == "green"

    fake_extraction_service.result = _result(_field("packaging_reference", "REF-1", confidence="low"))
    _upload(client, token)

    after = client.get(f"/api/products/{product['id']}", headers=headers).json()
    assert after["status"] == "red"
