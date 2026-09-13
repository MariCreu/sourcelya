import uuid

from app.domain.enums import FieldInformationState, InformationStatus
from app.integrations.extraction.base import DocumentExtractionResult, ExtractedFieldSuggestion
from app.repositories.compliance_request_repository import ComplianceRequestRepository
from app.services.missing_information_service import MissingInformationService
from tests.conftest import TestingSessionLocal

USER_A = "11111111-1111-1111-1111-111111111111"


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
        quote_verified=True,
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


def _summarize(company_id: str):
    db = TestingSessionLocal()
    try:
        repo = ComplianceRequestRepository(db)
        request = repo.list(uuid.UUID(company_id))[0]
        return MissingInformationService(db).summarize(uuid.UUID(company_id), request)
    finally:
        db.close()


def _company_id(client, headers) -> str:
    return client.get("/api/companies/me", headers=headers).json()["id"]


def test_all_fields_missing_on_a_bare_component(client, auth_header):
    headers = auth_header(user_id=USER_A)
    _onboard(client, headers)
    supplier = _create_supplier(client, headers)
    product = _create_product(client, headers, supplier["id"])
    _create_component(client, headers, product["id"])
    _send_request(client, headers, supplier, product)

    summary = _summarize(_company_id(client, headers))
    assert summary.status == InformationStatus.MISSING_INFORMATION
    assert summary.available_count == 1  # packaging_type is NOT NULL, set at creation
    assert summary.missing_count == 4
    assert summary.total_requested == 5


def test_available_fields_are_not_counted_as_missing(client, auth_header):
    headers = auth_header(user_id=USER_A)
    _onboard(client, headers)
    supplier = _create_supplier(client, headers)
    product = _create_product(client, headers, supplier["id"])
    _create_component(
        client,
        headers,
        product["id"],
        material="Cardboard",
        weight_grams=42,
        recycled_content_percentage=10,
        packaging_reference="REF-1",
    )
    _send_request(client, headers, supplier, product)

    summary = _summarize(_company_id(client, headers))
    assert summary.status == InformationStatus.COMPLETE
    assert summary.available_count == 5
    assert summary.missing_count == 0


def test_pending_extraction_on_empty_field_is_review_required_not_missing(
    client, auth_header, fake_extraction_service
):
    headers = auth_header(user_id=USER_A)
    _onboard(client, headers)
    supplier = _create_supplier(client, headers)
    product = _create_product(client, headers, supplier["id"])
    # material left unset — a pending proposal for it should be
    # REVIEW_REQUIRED, not a CONFLICT (nothing to conflict with) and not
    # MISSING (there is a candidate value, just unreviewed).
    _create_component(
        client,
        headers,
        product["id"],
        weight_grams=42,
        recycled_content_percentage=10,
        packaging_reference="REF-1",
    )
    _, token = _send_request(client, headers, supplier, product)

    fake_extraction_service.result = _result(_field("material", "Corrugated cardboard"))
    _upload(client, token)

    summary = _summarize(_company_id(client, headers))
    material_field = next(f for f in summary.components[0].fields if f.field_name == "material")
    assert material_field.state == FieldInformationState.REVIEW_REQUIRED
    assert summary.status == InformationStatus.REVIEW_REQUIRED


def test_conflict_when_pending_extraction_differs_from_current_value(
    client, auth_header, fake_extraction_service
):
    headers = auth_header(user_id=USER_A)
    _onboard(client, headers)
    supplier = _create_supplier(client, headers)
    product = _create_product(client, headers, supplier["id"])
    _create_component(client, headers, product["id"], weight_grams=42)
    _, token = _send_request(client, headers, supplier, product)

    fake_extraction_service.result = _result(_field("weight_grams", "47"))
    _upload(client, token)

    summary = _summarize(_company_id(client, headers))
    weight_field = next(f for f in summary.components[0].fields if f.field_name == "weight_grams")
    assert weight_field.state == FieldInformationState.CONFLICT
    assert summary.status == InformationStatus.CONFLICT


def test_rejected_extraction_field_remains_missing(client, auth_header, fake_extraction_service):
    headers = auth_header(user_id=USER_A)
    _onboard(client, headers)
    supplier = _create_supplier(client, headers)
    product = _create_product(client, headers, supplier["id"])
    _create_component(client, headers, product["id"])
    request, token = _send_request(client, headers, supplier, product)

    fake_extraction_service.result = _result(_field("material", "Corrugated cardboard"))
    _upload(client, token)
    document_id = client.get(f"/api/requests/{request['id']}", headers=headers).json()["documents"][
        0
    ]["id"]
    field_id = client.get(
        f"/api/documents/{document_id}/extracted-fields", headers=headers
    ).json()[0]["id"]
    client.post(
        f"/api/documents/{document_id}/extracted-fields/{field_id}/reject", json={}, headers=headers
    )

    summary = _summarize(_company_id(client, headers))
    material_field = next(f for f in summary.components[0].fields if f.field_name == "material")
    assert material_field.state == FieldInformationState.MISSING
    assert summary.status == InformationStatus.MISSING_INFORMATION


def test_accepted_extraction_field_becomes_available(client, auth_header, fake_extraction_service):
    headers = auth_header(user_id=USER_A)
    _onboard(client, headers)
    supplier = _create_supplier(client, headers)
    product = _create_product(client, headers, supplier["id"])
    _create_component(
        client,
        headers,
        product["id"],
        weight_grams=42,
        recycled_content_percentage=10,
        packaging_reference="REF-1",
    )
    request, token = _send_request(client, headers, supplier, product)

    fake_extraction_service.result = _result(_field("material", "Corrugated cardboard"))
    _upload(client, token)
    document_id = client.get(f"/api/requests/{request['id']}", headers=headers).json()["documents"][
        0
    ]["id"]
    field_id = client.get(
        f"/api/documents/{document_id}/extracted-fields", headers=headers
    ).json()[0]["id"]
    client.post(
        f"/api/documents/{document_id}/extracted-fields/{field_id}/accept", json={}, headers=headers
    )

    summary = _summarize(_company_id(client, headers))
    assert summary.status == InformationStatus.COMPLETE
    material_field = next(f for f in summary.components[0].fields if f.field_name == "material")
    assert material_field.state == FieldInformationState.AVAILABLE
