"""FASE 4's own E2E slice on top of FASE 3's request flow: a supplier opens
a request, attaches a document, submits, and the company downloads it —
byte for byte, through the real HTTP API.
"""

USER_A = "11111111-1111-1111-1111-111111111111"


def test_supplier_uploads_document_and_company_downloads_it(client, auth_header, recording_email_sender):
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
    request = client.post(
        "/api/requests",
        json={"supplier_id": supplier["id"], "product_ids": [product["id"]], "language": "es"},
        headers=headers,
    ).json()
    sent = client.post(f"/api/requests/{request['id']}/send", headers=headers).json()
    token = sent["request_url"].rsplit("/", 1)[-1]

    # Supplier opens the request (no login).
    opened = client.get(f"/api/public/requests/{token}")
    assert opened.status_code == 200
    assert opened.json()["documents"] == []

    # Supplier attaches a document.
    file_content = b"%PDF-1.4\n%Fake technical datasheet content for QA\n"
    upload = client.post(
        f"/api/public/requests/{token}/documents",
        files={"file": ("technical-datasheet.pdf", file_content, "application/pdf")},
    )
    assert upload.status_code == 200
    assert len(upload.json()["documents"]) == 1

    # Supplier submits.
    submitted = client.post(f"/api/public/requests/{token}/submit")
    assert submitted.status_code == 200
    assert submitted.json()["status"] == "submitted"
    # Document survives submission and is still listed.
    assert len(submitted.json()["documents"]) == 1

    # Company sees the document on the request and downloads it.
    company_view = client.get(f"/api/requests/{request['id']}", headers=headers).json()
    assert company_view["status"] == "submitted"
    assert len(company_view["documents"]) == 1
    document = company_view["documents"][0]
    assert document["filename"] == "technical-datasheet.pdf"
    assert document["extraction_status"] == "pending"  # no OCR/extraction in FASE 4

    download = client.get(f"/api/documents/{document['id']}/download", headers=headers)
    assert download.status_code == 200
    assert download.content == file_content
    assert download.headers["content-type"] == "application/pdf"
