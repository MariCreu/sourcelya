USER_A = "11111111-1111-1111-1111-111111111111"
USER_B = "22222222-2222-2222-2222-222222222222"


def _onboard(client, headers, name="Acme BV", country="NL"):
    return client.post("/api/companies", json={"name": name, "country": country}, headers=headers)


def test_create_supplier_requires_a_company(client, auth_header):
    headers = auth_header(user_id=USER_A)
    response = client.post(
        "/api/suppliers",
        json={"name": "Shenzhen Wonderful Packaging", "email": "s@example.com"},
        headers=headers,
    )
    assert response.status_code == 404


def test_create_and_list_suppliers(client, auth_header):
    headers = auth_header(user_id=USER_A)
    _onboard(client, headers)

    create = client.post(
        "/api/suppliers",
        json={"name": "Shenzhen Wonderful Packaging", "email": "s@example.com", "country": "cn"},
        headers=headers,
    )
    assert create.status_code == 201
    body = create.json()
    assert body["name"] == "Shenzhen Wonderful Packaging"
    assert body["country"] == "CN"  # normalized to uppercase

    listing = client.get("/api/suppliers", headers=headers).json()
    assert len(listing) == 1
    assert listing[0]["id"] == body["id"]


def test_get_supplier_by_id(client, auth_header):
    headers = auth_header(user_id=USER_A)
    _onboard(client, headers)
    created = client.post(
        "/api/suppliers", json={"name": "Dongguan ABC", "email": "abc@example.com"}, headers=headers
    ).json()

    response = client.get(f"/api/suppliers/{created['id']}", headers=headers)
    assert response.status_code == 200
    assert response.json()["name"] == "Dongguan ABC"


def test_get_unknown_supplier_is_404(client, auth_header):
    headers = auth_header(user_id=USER_A)
    _onboard(client, headers)
    response = client.get(
        "/api/suppliers/11111111-1111-1111-1111-111111111111", headers=headers
    )
    assert response.status_code == 404


def test_update_supplier(client, auth_header):
    headers = auth_header(user_id=USER_A)
    _onboard(client, headers)
    created = client.post(
        "/api/suppliers", json={"name": "Dongguan ABC", "email": "abc@example.com"}, headers=headers
    ).json()

    response = client.patch(
        f"/api/suppliers/{created['id']}", json={"name": "Dongguan ABC Ltd"}, headers=headers
    )
    assert response.status_code == 200
    assert response.json()["name"] == "Dongguan ABC Ltd"
    assert response.json()["email"] == "abc@example.com"  # untouched


def test_supplier_rejects_invalid_email(client, auth_header):
    headers = auth_header(user_id=USER_A)
    _onboard(client, headers)
    response = client.post(
        "/api/suppliers", json={"name": "Bad Supplier", "email": "not-an-email"}, headers=headers
    )
    assert response.status_code == 422


def test_suppliers_are_isolated_between_companies(client, auth_header):
    headers_a = auth_header(user_id=USER_A, email="a@example.com")
    headers_b = auth_header(user_id=USER_B, email="b@example.com")
    _onboard(client, headers_a, name="Company A")
    _onboard(client, headers_b, name="Company B")

    supplier_a = client.post(
        "/api/suppliers", json={"name": "Supplier A", "email": "sa@example.com"}, headers=headers_a
    ).json()

    # Company B can't see, read, or edit Company A's supplier.
    assert client.get("/api/suppliers", headers=headers_b).json() == []
    assert client.get(f"/api/suppliers/{supplier_a['id']}", headers=headers_b).status_code == 404
    assert (
        client.patch(
            f"/api/suppliers/{supplier_a['id']}", json={"name": "Hijacked"}, headers=headers_b
        ).status_code
        == 404
    )
