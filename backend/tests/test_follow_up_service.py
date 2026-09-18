import uuid

import pytest

from app.integrations.extraction.base import DocumentExtractionResult, ExtractedFieldSuggestion
from app.models.supplier_document import SupplierDocument
from app.repositories.company_repository import CompanyRepository
from app.repositories.compliance_request_repository import ComplianceRequestRepository
from app.repositories.follow_up_round_repository import FollowUpRoundRepository
from app.services.email_service import EmailService
from app.services.follow_up_service import (
    DuplicateFollowUpError,
    ExtractionStillProcessingError,
    FollowUpService,
    MaxAutomaticRoundsReachedError,
    NothingMissingError,
    RequestNotEligibleForFollowUpError,
)
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


def _load(company_id_str, request_id_str):
    db = TestingSessionLocal()
    company_id = uuid.UUID(company_id_str)
    request_id = uuid.UUID(request_id_str)
    company = CompanyRepository(db).get_by_id(company_id)
    request = ComplianceRequestRepository(db).get(company_id, request_id)
    return db, company, request


def test_create_round_lists_only_missing_fields_and_sends_email(
    client, auth_header, recording_email_sender
):
    headers = auth_header(user_id=USER_A)
    _onboard(client, headers)
    supplier = _create_supplier(client, headers)
    product = _create_product(client, headers, supplier["id"])
    _create_component(client, headers, product["id"], material="Cardboard")
    request, token = _send_request(client, headers, supplier, product)
    client.post(f"/api/public/requests/{token}/submit")

    db, company, req = _load(_company_id(client, headers), request["id"])
    try:
        follow_up_round = FollowUpService(db, EmailService(recording_email_sender)).create_round(
            company, uuid.UUID(USER_A), req, trigger="manual"
        )
        field_names = {ref["field_name"] for ref in follow_up_round.requested_fields}
        db.commit()
    finally:
        db.close()

    assert "material" not in field_names  # already available — never re-asked
    assert field_names == {"weight_grams", "recycled_content_percentage", "packaging_reference"}

    # The initial-request email was already sent by _send_request(); this
    # is the follow-up email on top of that one.
    assert len(recording_email_sender.sent_messages) == 2
    sent = recording_email_sender.sent_messages[-1]
    assert "Material" not in sent.html_body  # only missing fields are listed
    assert "Weight" in sent.html_body or "Peso" in sent.html_body


def _company_id(client, headers) -> str:
    return client.get("/api/companies/me", headers=headers).json()["id"]


def test_duplicate_follow_up_is_blocked(client, auth_header, recording_email_sender):
    headers = auth_header(user_id=USER_A)
    _onboard(client, headers)
    supplier = _create_supplier(client, headers)
    product = _create_product(client, headers, supplier["id"])
    _create_component(client, headers, product["id"])
    request, token = _send_request(client, headers, supplier, product)
    client.post(f"/api/public/requests/{token}/submit")

    db, company, req = _load(_company_id(client, headers), request["id"])
    try:
        service = FollowUpService(db, EmailService(recording_email_sender))
        service.create_round(company, uuid.UUID(USER_A), req, trigger="manual")
        db.commit()
    finally:
        db.close()

    db, company, req = _load(_company_id(client, headers), request["id"])
    try:
        service = FollowUpService(db, EmailService(recording_email_sender))
        with pytest.raises(DuplicateFollowUpError):
            service.create_round(company, uuid.UUID(USER_A), req, trigger="manual")
    finally:
        db.close()


def test_nothing_missing_blocks_follow_up(client, auth_header, recording_email_sender):
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
    request, token = _send_request(client, headers, supplier, product)
    submitted = client.post(f"/api/public/requests/{token}/submit")
    assert submitted.json()["status"] == "completed"

    db, company, req = _load(_company_id(client, headers), request["id"])
    try:
        with pytest.raises(NothingMissingError):
            FollowUpService(db, EmailService(recording_email_sender)).create_round(
                company, uuid.UUID(USER_A), req, trigger="manual"
            )
    finally:
        db.close()


def test_revoked_request_cannot_follow_up(client, auth_header, recording_email_sender):
    headers = auth_header(user_id=USER_A)
    _onboard(client, headers)
    supplier = _create_supplier(client, headers)
    product = _create_product(client, headers, supplier["id"])
    _create_component(client, headers, product["id"])
    request, token = _send_request(client, headers, supplier, product)
    client.post(f"/api/public/requests/{token}/submit")
    client.post(f"/api/requests/{request['id']}/revoke", headers=headers)

    db, company, req = _load(_company_id(client, headers), request["id"])
    try:
        with pytest.raises(RequestNotEligibleForFollowUpError):
            FollowUpService(db, EmailService(recording_email_sender)).create_round(
                company, uuid.UUID(USER_A), req, trigger="manual"
            )
    finally:
        db.close()


def test_follow_up_blocked_while_extraction_is_processing(
    client, auth_header, recording_email_sender
):
    headers = auth_header(user_id=USER_A)
    _onboard(client, headers)
    supplier = _create_supplier(client, headers)
    product = _create_product(client, headers, supplier["id"])
    _create_component(client, headers, product["id"])
    request, token = _send_request(client, headers, supplier, product)
    _upload(client, token)
    client.post(f"/api/public/requests/{token}/submit")

    db, company, req = _load(_company_id(client, headers), request["id"])
    try:
        document = db.query(SupplierDocument).filter_by(request_id=req.id).first()
        document.extraction_status = "processing"
        db.commit()
    finally:
        db.close()

    db, company, req = _load(_company_id(client, headers), request["id"])
    try:
        with pytest.raises(ExtractionStillProcessingError):
            FollowUpService(db, EmailService(recording_email_sender)).create_round(
                company, uuid.UUID(USER_A), req, trigger="manual"
            )
    finally:
        db.close()


def test_automatic_follow_up_disabled_by_default(client, auth_header, recording_email_sender):
    headers = auth_header(user_id=USER_A)
    _onboard(client, headers)
    supplier = _create_supplier(client, headers)
    product = _create_product(client, headers, supplier["id"])
    _create_component(client, headers, product["id"])
    _request, token = _send_request(client, headers, supplier, product)

    client.post(f"/api/public/requests/{token}/submit")

    # Only the initial-request email was sent — no automatic follow-up,
    # since automatic_follow_up defaults to False.
    assert len(recording_email_sender.sent_messages) == 1


def test_automatic_follow_up_caps_at_max_rounds(client, auth_header, recording_email_sender):
    """Drives `create_round(trigger="automatic")` directly rather than
    through repeated HTTP submits: toggling one field's value between two
    states keeps each round's missing-set different from the *immediately
    preceding* one (dodging the duplicate-follow-up guard, which only
    compares against the latest round) without ever actually completing
    the request — isolating the round-cap behavior from the separate
    duplicate-detection behavior already covered above.
    """
    from app.core.config import get_settings

    headers = auth_header(user_id=USER_A)
    _onboard(client, headers)
    supplier = _create_supplier(client, headers)
    product = _create_product(client, headers, supplier["id"])
    _create_component(client, headers, product["id"])
    request, token = _send_request(client, headers, supplier, product)
    client.post(f"/api/public/requests/{token}/submit")

    max_rounds = get_settings().max_automatic_follow_up_rounds
    for i in range(max_rounds + 2):
        db, company, req = _load(_company_id(client, headers), request["id"])
        try:
            component = req.products[0].product.packaging_components[0]
            component.recycled_content_percentage = 5 if i % 2 == 0 else None
            db.commit()
            db, company, req = _load(_company_id(client, headers), request["id"])
            service = FollowUpService(db, EmailService(recording_email_sender))
            try:
                service.create_round(company, None, req, trigger="automatic")
            except (MaxAutomaticRoundsReachedError, DuplicateFollowUpError):
                # Once the cap is hit, later iterations may see either
                # exception depending on which toggle state they land on —
                # both are "correctly blocked," only the round count matters.
                pass
            db.commit()
        finally:
            db.close()

    db, company, req = _load(_company_id(client, headers), request["id"])
    try:
        rounds = FollowUpRoundRepository(db).list_for_request(company.id, req.id)
    finally:
        db.close()

    automatic_rounds = [r for r in rounds if r.trigger == "automatic"]
    assert len(automatic_rounds) == max_rounds


def test_follow_up_endpoint_returns_structured_error_code(client, auth_header):
    """The manual /follow-up endpoint reports *why* it's blocked as a
    machine-readable `code`, not just a message string — same pattern as
    the FASE 5 accept-conflict body — so the frontend can show the exact
    right guidance."""
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
    request, token = _send_request(client, headers, supplier, product)
    submitted = client.post(f"/api/public/requests/{token}/submit")
    assert submitted.json()["status"] == "completed"

    response = client.post(f"/api/requests/{request['id']}/follow-up", headers=headers)
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "nothing_missing"
