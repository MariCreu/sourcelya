"""End-to-end happy path for FASE 3's one critical flow: a company sends a
request, a supplier who never creates an account fills it in from the
emailed link, and the company sees it come back as SUBMITTED.

Everything here goes through the real HTTP API (FastAPI TestClient) and a
real SQLAlchemy/SQLite database — the only thing faked is the outbound
email transport (RecordingEmailSender), exactly as production would use a
real provider behind the same EmailSender interface.
"""

USER_A = "11111111-1111-1111-1111-111111111111"


def test_full_supplier_request_lifecycle(client, auth_header, recording_email_sender):
    headers = auth_header(user_id=USER_A)

    # 1. Company signs up / onboards.
    onboarding = client.post(
        "/api/companies", json={"name": "Acme BV", "country": "NL"}, headers=headers
    )
    assert onboarding.status_code == 201

    # 2. Company creates a supplier and one of that supplier's products,
    #    with an incomplete packaging component (that's the whole point:
    #    the supplier is the one who should fill in the missing data).
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
    component = client.post(
        f"/api/products/{product['id']}/packaging-components",
        json={"name": "Outer box", "packaging_type": "box"},
        headers=headers,
    ).json()

    # 3. Company creates a ComplianceRequest for that product, in Spanish.
    created = client.post(
        "/api/requests",
        json={"supplier_id": supplier["id"], "product_ids": [product["id"]], "language": "es"},
        headers=headers,
    )
    assert created.status_code == 201
    request = created.json()
    assert request["status"] == "draft"

    # 4. Company sends it — a secure token is minted, the fake email
    #    provider "delivers" the templated ES email, and the response
    #    hands back the one-time request URL.
    sent = client.post(f"/api/requests/{request['id']}/send", headers=headers)
    assert sent.status_code == 200
    send_body = sent.json()
    assert send_body["request"]["status"] == "sent"
    request_url = send_body["request_url"]

    assert len(recording_email_sender.sent_messages) == 1
    email = recording_email_sender.sent_messages[0]
    assert email.to == supplier["email"]
    assert email.subject == "Solicitud de información de productos"
    assert request_url in email.html_body  # exactly what a real supplier would click

    # 5. Supplier opens the secure link — no login, ever.
    token = request_url.rsplit("/", 1)[-1]
    opened = client.get(f"/api/public/requests/{token}")
    assert opened.status_code == 200
    public_view = opened.json()
    assert public_view["status"] == "opened"
    assert public_view["company_name"] == "Acme BV"
    assert public_view["supplier_name"] == supplier["name"]
    assert "company_id" not in public_view and "supplier_id" not in public_view
    assert public_view["products"][0]["packaging_components"][0]["id"] == component["id"]

    # Company sees the status flip too, without touching the request itself.
    assert (
        client.get(f"/api/requests/{request['id']}", headers=headers).json()["status"] == "opened"
    )

    # 6. Supplier fills in the missing packaging data and saves progress
    #    (can be partial — no PPWR validation blocking this yet).
    saved = client.patch(
        f"/api/public/requests/{token}",
        json={
            "components": [
                {
                    "id": component["id"],
                    "material": "cardboard",
                    "weight_grams": 45.0,
                    "recycled_content_percentage": 60,
                    "packaging_reference": "BOX-001",
                    "notes": "FSC certified",
                }
            ]
        },
    )
    assert saved.status_code == 200
    assert saved.json()["status"] == "in_progress"
    assert (
        client.get(f"/api/requests/{request['id']}", headers=headers).json()["status"]
        == "in_progress"
    )

    # 7. Supplier submits. FASE 6: the supplier provided every requested
    #    field above, so submitting now takes the request all the way to
    #    COMPLETED — not just SUBMITTED — since MissingInformationService
    #    finds nothing left missing/pending/conflicting. See
    #    FollowUpService.reevaluate, called right after submit().
    submitted = client.post(f"/api/public/requests/{token}/submit")
    assert submitted.status_code == 200
    assert submitted.json()["status"] == "completed"

    # 8. Company sees COMPLETED, with the supplier-provided data attached.
    final = client.get(f"/api/requests/{request['id']}", headers=headers)
    assert final.status_code == 200
    assert final.json()["status"] == "completed"
    assert final.json()["submitted_at"] is not None
    assert final.json()["completed_at"] is not None

    final_product = client.get(f"/api/products/{product['id']}", headers=headers).json()
    saved_component = final_product["packaging_components"][0]
    assert saved_component["material"] == "cardboard"
    assert saved_component["weight_grams"] == 45.0
    assert saved_component["packaging_reference"] == "BOX-001"
