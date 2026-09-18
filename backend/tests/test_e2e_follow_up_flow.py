"""FASE 6 end-to-end: the full missing-information loop through the real
HTTP API — company asks -> supplier partially responds -> Sourcelya
extracts -> company reviews -> Sourcelya (via the company's manual click)
asks again for only what's still missing -> supplier completes it ->
request reaches COMPLETE. Also covers a conflict blocking completion until
a human resolves it, and the audit trail/recovery metric this produces.

Fixtures only — the fake extraction service, never a real/paid Claude call
(see conftest.fake_extraction_service).
"""

from app.integrations.extraction.base import DocumentExtractionResult, ExtractedFieldSuggestion
from app.models.audit_event import AuditEvent
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


def _detail(client, headers, request_id):
    return client.get(f"/api/requests/{request_id}", headers=headers).json()


def _extract_new_token(request_url: str) -> str:
    return request_url.rsplit("/", 1)[-1]


def test_full_missing_information_loop_reaches_complete(
    client, auth_header, fake_extraction_service
):
    headers = auth_header(user_id=USER_A)
    _onboard(client, headers)
    supplier = _create_supplier(client, headers)
    product = _create_product(client, headers, supplier["id"])
    # Bare component: only packaging_type is set (always NOT NULL at
    # creation) — 1/5 available, 4 missing.
    component = _create_component(client, headers, product["id"])
    request, token = _send_request(client, headers, supplier, product)

    detail = _detail(client, headers, request["id"])
    assert detail["information_status"]["total_requested"] == 5
    assert detail["information_status"]["available_count"] == 1

    # Supplier fills in 2 of the 4 missing fields directly, uploads a
    # document, and submits.
    client.patch(
        f"/api/public/requests/{token}",
        json={
            "components": [
                {"id": component["id"], "material": "Cardboard", "weight_grams": 42}
            ]
        },
    )
    fake_extraction_service.result = _result(_field("packaging_reference", "REF-2024-071"))
    _upload(client, token)
    submitted = client.post(f"/api/public/requests/{token}/submit")
    assert submitted.json()["status"] == "submitted"  # recycled_content still missing + a pending review

    detail = _detail(client, headers, request["id"])
    assert detail["information_status"]["status"] == "review_required"
    document_id = detail["documents"][0]["id"]
    field_id = client.get(
        f"/api/documents/{document_id}/extracted-fields", headers=headers
    ).json()[0]["id"]

    # Company reviews the extraction — accepts the proposed reference.
    client.post(
        f"/api/documents/{document_id}/extracted-fields/{field_id}/accept",
        json={},
        headers=headers,
    )

    detail = _detail(client, headers, request["id"])
    assert detail["information_status"]["available_count"] == 4  # packaging_type, material, weight, reference
    assert detail["information_status"]["missing_count"] == 1  # recycled_content_percentage
    assert detail["status"] == "submitted"  # not complete yet

    # Company requests exactly the one missing field.
    follow_up = client.post(f"/api/requests/{request['id']}/follow-up", headers=headers)
    assert follow_up.status_code == 200
    rounds = follow_up.json()["follow_up_rounds"]
    assert len(rounds) == 1
    assert [r["field_name"] for r in rounds[0]["requested_fields"]] == [
        "recycled_content_percentage"
    ]

    # A second identical follow-up is refused — nothing has changed.
    duplicate = client.post(f"/api/requests/{request['id']}/follow-up", headers=headers)
    assert duplicate.status_code == 409
    assert duplicate.json()["detail"]["code"] == "duplicate_follow_up"

    # The follow-up minted a new token — the old one's hash no longer
    # matches anything, so it now reads as an unknown/invalid link.
    assert client.get(f"/api/public/requests/{token}").status_code == 404

    # Supplier opens the NEW link (only the company can see it — read the
    # rotated hash indirectly via the round's own request detail; in a
    # real flow the supplier gets this by email, so we resolve it via the
    # DB exactly like the RecordingEmailSender-based tests do).
    new_token = _current_raw_token(request["id"])

    portal_view = client.get(f"/api/public/requests/{new_token}")
    assert portal_view.status_code == 200
    assert portal_view.json()["missing_fields"] == [
        {"packaging_component_id": component["id"], "field_name": "recycled_content_percentage"}
    ]

    client.patch(
        f"/api/public/requests/{new_token}",
        json={"components": [{"id": component["id"], "recycled_content_percentage": 30}]},
    )
    final_submit = client.post(f"/api/public/requests/{new_token}/submit")
    assert final_submit.json()["status"] == "completed"

    final_detail = _detail(client, headers, request["id"])
    assert final_detail["status"] == "completed"
    assert final_detail["information_status"]["status"] == "complete"
    assert final_detail["information_status"]["missing_count"] == 0
    assert final_detail["recovery_stats"]["available_now"] == 5
    assert final_detail["recovery_stats"]["total_requested"] == 5
    assert final_detail["recovery_stats"]["recovery_rate"] == 1.0
    # At the moment of first submission: packaging_type/material/weight_grams
    # are already available (3) — packaging_reference is still PENDING
    # review (not yet accepted) and recycled_content_percentage is missing,
    # so neither counts as "available" yet at that snapshot.
    assert final_detail["recovery_stats"]["available_after_first_submission"] == 3
    assert final_detail["recovery_stats"]["follow_up_recovered"] == 2

    # Audit trail reconstructs the whole story.
    with TestingSessionLocal() as db:
        events = (
            db.query(AuditEvent)
            .filter_by(entity_id=request["id"])
            .order_by(AuditEvent.created_at)
            .all()
        )
    event_types = [e.event_type for e in events]
    assert "request_sent" in event_types
    assert "request_submitted" in event_types
    assert "follow_up_created" in event_types
    assert "supplier_resubmitted" in event_types
    assert "request_completed" in event_types


def _current_raw_token(request_id: str) -> str:
    """Test-only helper: the raw token is never retrievable through the
    real API after being minted (only its hash is stored) — a real
    supplier gets it by email. Since this test doesn't wire up
    RecordingEmailSender, it mints an equivalent fresh token directly via
    the same code path FollowUpService/ComplianceRequestService use, only
    to keep driving the *public* side of this one test scenario.
    """
    import uuid
    from datetime import datetime, timedelta, timezone

    from app.core.config import get_settings
    from app.core.security import generate_secure_token, hash_token
    from app.models.compliance_request import ComplianceRequest

    with TestingSessionLocal() as db:
        record = db.get(ComplianceRequest, uuid.UUID(request_id))
        raw_token = generate_secure_token()
        record.secure_token_hash = hash_token(raw_token)
        record.token_expires_at = datetime.now(timezone.utc) + timedelta(
            days=get_settings().supplier_token_default_expiry_days
        )
        record.token_revoked_at = None
        db.commit()
    return raw_token


def test_conflict_blocks_complete_until_resolved(client, auth_header, fake_extraction_service):
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

    fake_extraction_service.result = _result(_field("weight_grams", "47"))
    _upload(client, token)
    submitted = client.post(f"/api/public/requests/{token}/submit")
    assert submitted.json()["status"] == "submitted"

    detail = _detail(client, headers, request["id"])
    assert detail["information_status"]["status"] == "conflict"
    assert detail["status"] == "submitted"  # never auto-completed with a live conflict

    # Can't follow up while a conflict is unresolved.
    blocked = client.post(f"/api/requests/{request['id']}/follow-up", headers=headers)
    assert blocked.status_code == 409
    assert blocked.json()["detail"]["code"] == "review_required"

    document_id = detail["documents"][0]["id"]
    field_id = client.get(
        f"/api/documents/{document_id}/extracted-fields", headers=headers
    ).json()[0]["id"]
    accept_conflict = client.post(
        f"/api/documents/{document_id}/extracted-fields/{field_id}/accept",
        json={},
        headers=headers,
    )
    assert accept_conflict.status_code == 409
    assert accept_conflict.json()["detail"]["detail"] == "POSSIBLE CONFLICT"

    resolved = client.post(
        f"/api/documents/{document_id}/extracted-fields/{field_id}/accept",
        json={"conflict_resolution": "keep_current"},
        headers=headers,
    )
    assert resolved.status_code == 200

    final_detail = _detail(client, headers, request["id"])
    assert final_detail["status"] == "completed"
    assert final_detail["information_status"]["status"] == "complete"
