"""FASE 5's own E2E slice on top of FASE 3/4's request+document flow:

company creates request -> supplier uploads document -> submits ->
extraction runs -> company opens request -> sees proposed fields with
evidence -> accepts -> status/completeness updates.
"""

from app.integrations.extraction.base import DocumentExtractionResult, ExtractedFieldSuggestion

USER_A = "11111111-1111-1111-1111-111111111111"


def test_full_extraction_review_lifecycle(client, auth_header, fake_extraction_service):
    headers = auth_header(user_id=USER_A)
    client.post("/api/companies", json={"name": "Acme BV", "country": "NL"}, headers=headers)

    supplier = client.post(
        "/api/suppliers",
        json={"name": "Shenzhen Wonderful Packaging", "email": "supplier@example.com"},
        headers=headers,
    ).json()
    product = client.post(
        "/api/products",
        json={"name": "Bamboo toothbrush", "supplier_id": supplier["id"]},
        headers=headers,
    ).json()
    client.post(
        f"/api/products/{product['id']}/packaging-components",
        json={"name": "Outer box", "packaging_type": "box"},
        headers=headers,
    )

    request = client.post(
        "/api/requests",
        json={"supplier_id": supplier["id"], "product_ids": [product["id"]], "language": "es"},
        headers=headers,
    ).json()
    sent = client.post(f"/api/requests/{request['id']}/send", headers=headers).json()
    token = sent["request_url"].rsplit("/", 1)[-1]

    # Supplier uploads a document; the (fake, deterministic) extractor
    # finds material and weight, with page-level evidence.
    fake_extraction_service.result = DocumentExtractionResult(
        document_classification="packaging_specification",
        fields=[
            ExtractedFieldSuggestion(
                field_name="material",
                value="Corrugated cardboard",
                confidence="high",
                source_page=3,
                source_quote="Corrugated cardboard",
                quote_verified=True,
            ),
            ExtractedFieldSuggestion(
                field_name="weight_grams",
                value="47",
                confidence="high",
                source_page=7,
                source_quote="47",
                quote_verified=True,
            ),
        ],
        model="fake-claude",
        input_tokens=1200,
        output_tokens=150,
        duration_ms=900,
        estimated_cost_usd=0.01,
    )
    upload = client.post(
        f"/api/public/requests/{token}/documents",
        files={"file": ("PackagingSpecification.pdf", b"%PDF-1.4 fake spec", "application/pdf")},
    )
    assert upload.status_code == 200

    submitted = client.post(f"/api/public/requests/{token}/submit")
    assert submitted.status_code == 200
    assert submitted.json()["status"] == "submitted"

    # Company opens the request and sees the document with proposed fields.
    company_view = client.get(f"/api/requests/{request['id']}", headers=headers).json()
    document = company_view["documents"][0]
    assert document["extraction_status"] == "completed"
    assert document["extracted_field_count"] == 2
    assert document["pending_review_count"] == 2

    fields = client.get(
        f"/api/documents/{document['id']}/extracted-fields", headers=headers
    ).json()
    assert len(fields) == 2
    material_field = next(f for f in fields if f["field_name"] == "material")
    assert material_field["extracted_value"] == "Corrugated cardboard"
    assert material_field["confidence"] == "high"
    assert material_field["source_page"] == 3
    assert material_field["quote_verified"] is True

    # Before review, nothing was written automatically — and the pending
    # proposals themselves flip status to RED ("needs a human decision"),
    # regardless of how confident the extraction was.
    before = client.get(f"/api/products/{product['id']}", headers=headers).json()
    assert before["status"] == "red"
    assert before["packaging_components"][0]["material"] is None

    # Company reviews and accepts both proposals.
    for field in fields:
        response = client.post(
            f"/api/documents/{document['id']}/extracted-fields/{field['id']}/accept",
            json={},
            headers=headers,
        )
        assert response.status_code == 200

    after = client.get(f"/api/products/{product['id']}", headers=headers).json()
    component = after["packaging_components"][0]
    assert component["material"] == "Corrugated cardboard"
    assert component["weight_grams"] == 47.0
    # recycled_content_percentage was never proposed -> still missing.
    assert component["missing_fields"] == ["recycled_content_percentage"]
    assert after["status"] == "orange"

    company_view_after = client.get(f"/api/requests/{request['id']}", headers=headers).json()
    assert company_view_after["documents"][0]["pending_review_count"] == 0
