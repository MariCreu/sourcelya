USER_A = "11111111-1111-1111-1111-111111111111"
USER_B = "22222222-2222-2222-2222-222222222222"


def _onboard(client, headers, name="Acme BV", country="NL"):
    return client.post("/api/companies", json={"name": name, "country": country}, headers=headers)


def _create_supplier(client, headers, name="Shenzhen Wonderful Packaging", email="s@example.com"):
    return client.post(
        "/api/suppliers", json={"name": name, "email": email}, headers=headers
    ).json()


def _create_product(client, headers, supplier_id=None, name="Bamboo toothbrush"):
    payload = {"name": name}
    if supplier_id is not None:
        payload["supplier_id"] = supplier_id
    return client.post("/api/products", json=payload, headers=headers).json()


def _setup_supplier_with_product(client, headers):
    supplier = _create_supplier(client, headers)
    product = _create_product(client, headers, supplier_id=supplier["id"])
    return supplier, product


def test_create_request(client, auth_header):
    headers = auth_header(user_id=USER_A)
    _onboard(client, headers)
    supplier, product = _setup_supplier_with_product(client, headers)

    response = client.post(
        "/api/requests",
        json={"supplier_id": supplier["id"], "product_ids": [product["id"]], "language": "es"},
        headers=headers,
    )
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "draft"
    assert body["language"] == "es"
    assert body["supplier_name"] == supplier["name"]
    assert len(body["products"]) == 1
    assert body["products"][0]["product_id"] == product["id"]
    assert body["has_active_link"] is False


def test_create_request_requires_at_least_one_product(client, auth_header):
    headers = auth_header(user_id=USER_A)
    _onboard(client, headers)
    supplier = _create_supplier(client, headers)

    response = client.post(
        "/api/requests",
        json={"supplier_id": supplier["id"], "product_ids": [], "language": "es"},
        headers=headers,
    )
    assert response.status_code == 422


def test_create_request_rejects_supplier_from_another_company(client, auth_header):
    headers_a = auth_header(user_id=USER_A, email="a@example.com")
    headers_b = auth_header(user_id=USER_B, email="b@example.com")
    _onboard(client, headers_a, name="Company A")
    _onboard(client, headers_b, name="Company B")
    supplier_b, product_b = _setup_supplier_with_product(client, headers_b)

    response = client.post(
        "/api/requests",
        json={"supplier_id": supplier_b["id"], "product_ids": [product_b["id"]], "language": "es"},
        headers=headers_a,
    )
    assert response.status_code == 400


def test_create_request_rejects_product_from_another_supplier(client, auth_header):
    headers = auth_header(user_id=USER_A)
    _onboard(client, headers)
    supplier_1 = _create_supplier(client, headers, name="Supplier 1", email="s1@example.com")
    supplier_2 = _create_supplier(client, headers, name="Supplier 2", email="s2@example.com")
    product_of_supplier_2 = _create_product(client, headers, supplier_id=supplier_2["id"])

    response = client.post(
        "/api/requests",
        json={
            "supplier_id": supplier_1["id"],
            "product_ids": [product_of_supplier_2["id"]],
            "language": "es",
        },
        headers=headers,
    )
    assert response.status_code == 400


def test_create_request_rejects_product_from_another_company(client, auth_header):
    headers_a = auth_header(user_id=USER_A, email="a@example.com")
    headers_b = auth_header(user_id=USER_B, email="b@example.com")
    _onboard(client, headers_a, name="Company A")
    _onboard(client, headers_b, name="Company B")
    supplier_a = _create_supplier(client, headers_a)
    _supplier_b, product_b = _setup_supplier_with_product(client, headers_b)

    response = client.post(
        "/api/requests",
        json={"supplier_id": supplier_a["id"], "product_ids": [product_b["id"]], "language": "es"},
        headers=headers_a,
    )
    assert response.status_code == 400


def test_send_request_generates_link_and_emails_supplier(client, auth_header, recording_email_sender):
    headers = auth_header(user_id=USER_A)
    _onboard(client, headers)
    supplier, product = _setup_supplier_with_product(client, headers)
    request = client.post(
        "/api/requests",
        json={"supplier_id": supplier["id"], "product_ids": [product["id"]], "language": "es"},
        headers=headers,
    ).json()

    response = client.post(f"/api/requests/{request['id']}/send", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["request"]["status"] == "sent"
    assert body["request"]["has_active_link"] is True
    assert body["request_url"].startswith("http")
    assert "/request/" in body["request_url"]

    assert len(recording_email_sender.sent_messages) == 1
    sent = recording_email_sender.sent_messages[0]
    assert sent.to == supplier["email"]
    assert sent.subject == "Solicitud de información de productos"
    assert body["request_url"] in sent.html_body


def test_send_request_in_english_uses_english_template(
    client, auth_header, recording_email_sender
):
    headers = auth_header(user_id=USER_A)
    _onboard(client, headers)
    supplier, product = _setup_supplier_with_product(client, headers)
    request = client.post(
        "/api/requests",
        json={"supplier_id": supplier["id"], "product_ids": [product["id"]], "language": "en"},
        headers=headers,
    ).json()

    client.post(f"/api/requests/{request['id']}/send", headers=headers)

    sent = recording_email_sender.sent_messages[0]
    assert sent.subject == "Product information request"
    assert "No account is required" in sent.html_body


def test_sending_a_request_twice_is_rejected(client, auth_header, recording_email_sender):
    headers = auth_header(user_id=USER_A)
    _onboard(client, headers)
    supplier, product = _setup_supplier_with_product(client, headers)
    request = client.post(
        "/api/requests",
        json={"supplier_id": supplier["id"], "product_ids": [product["id"]], "language": "es"},
        headers=headers,
    ).json()

    first = client.post(f"/api/requests/{request['id']}/send", headers=headers)
    assert first.status_code == 200

    second = client.post(f"/api/requests/{request['id']}/send", headers=headers)
    assert second.status_code == 409
    # No second email was sent for the rejected attempt.
    assert len(recording_email_sender.sent_messages) == 1


def test_revoke_request_link(client, auth_header, recording_email_sender):
    headers = auth_header(user_id=USER_A)
    _onboard(client, headers)
    supplier, product = _setup_supplier_with_product(client, headers)
    request = client.post(
        "/api/requests",
        json={"supplier_id": supplier["id"], "product_ids": [product["id"]], "language": "es"},
        headers=headers,
    ).json()
    client.post(f"/api/requests/{request['id']}/send", headers=headers)

    response = client.post(f"/api/requests/{request['id']}/revoke", headers=headers)
    assert response.status_code == 200
    assert response.json()["has_active_link"] is False


def test_revoke_without_active_link_is_rejected(client, auth_header):
    headers = auth_header(user_id=USER_A)
    _onboard(client, headers)
    supplier, product = _setup_supplier_with_product(client, headers)
    request = client.post(
        "/api/requests",
        json={"supplier_id": supplier["id"], "product_ids": [product["id"]], "language": "es"},
        headers=headers,
    ).json()

    response = client.post(f"/api/requests/{request['id']}/revoke", headers=headers)
    assert response.status_code == 409


def test_resend_issues_a_new_link_and_invalidates_the_old_one(
    client, auth_header, recording_email_sender
):
    headers = auth_header(user_id=USER_A)
    _onboard(client, headers)
    supplier, product = _setup_supplier_with_product(client, headers)
    request = client.post(
        "/api/requests",
        json={"supplier_id": supplier["id"], "product_ids": [product["id"]], "language": "es"},
        headers=headers,
    ).json()
    first_send = client.post(f"/api/requests/{request['id']}/send", headers=headers).json()
    first_token = first_send["request_url"].rsplit("/", 1)[-1]

    resend = client.post(f"/api/requests/{request['id']}/resend", headers=headers)
    assert resend.status_code == 200
    second_token = resend.json()["request_url"].rsplit("/", 1)[-1]
    assert second_token != first_token
    assert len(recording_email_sender.sent_messages) == 2

    # Old token no longer resolves; new one does.
    assert client.get(f"/api/public/requests/{first_token}").status_code == 404
    assert client.get(f"/api/public/requests/{second_token}").status_code == 200


def test_requests_are_isolated_between_companies(client, auth_header):
    headers_a = auth_header(user_id=USER_A, email="a@example.com")
    headers_b = auth_header(user_id=USER_B, email="b@example.com")
    _onboard(client, headers_a, name="Company A")
    _onboard(client, headers_b, name="Company B")
    supplier_a, product_a = _setup_supplier_with_product(client, headers_a)
    request_a = client.post(
        "/api/requests",
        json={"supplier_id": supplier_a["id"], "product_ids": [product_a["id"]], "language": "es"},
        headers=headers_a,
    ).json()

    assert client.get("/api/requests", headers=headers_b).json() == []
    assert client.get(f"/api/requests/{request_a['id']}", headers=headers_b).status_code == 404
    assert (
        client.post(f"/api/requests/{request_a['id']}/send", headers=headers_b).status_code == 404
    )
