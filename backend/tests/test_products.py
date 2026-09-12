USER_A = "11111111-1111-1111-1111-111111111111"
USER_B = "22222222-2222-2222-2222-222222222222"


def _onboard(client, headers, name="Acme BV", country="NL"):
    return client.post("/api/companies", json={"name": name, "country": country}, headers=headers)


def _create_supplier(client, headers, name="Shenzhen Wonderful Packaging"):
    return client.post(
        "/api/suppliers", json={"name": name, "email": "s@example.com"}, headers=headers
    ).json()


def test_create_product_without_supplier(client, auth_header):
    headers = auth_header(user_id=USER_A)
    _onboard(client, headers)

    response = client.post("/api/products", json={"name": "Bamboo toothbrush"}, headers=headers)
    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Bamboo toothbrush"
    assert body["supplier_id"] is None
    # No packaging components yet -> ORANGE, not GREEN.
    assert body["status"] == "orange"
    assert body["packaging_component_count"] == 0


def test_create_product_with_supplier(client, auth_header):
    headers = auth_header(user_id=USER_A)
    _onboard(client, headers)
    supplier = _create_supplier(client, headers)

    response = client.post(
        "/api/products",
        json={"name": "Bamboo toothbrush", "supplier_id": supplier["id"]},
        headers=headers,
    )
    assert response.status_code == 201
    assert response.json()["supplier_id"] == supplier["id"]


def test_create_product_rejects_supplier_from_another_company(client, auth_header):
    headers_a = auth_header(user_id=USER_A, email="a@example.com")
    headers_b = auth_header(user_id=USER_B, email="b@example.com")
    _onboard(client, headers_a, name="Company A")
    _onboard(client, headers_b, name="Company B")
    supplier_b = _create_supplier(client, headers_b)

    response = client.post(
        "/api/products",
        json={"name": "Sneaky product", "supplier_id": supplier_b["id"]},
        headers=headers_a,
    )
    assert response.status_code == 400


def test_products_are_isolated_between_companies(client, auth_header):
    headers_a = auth_header(user_id=USER_A, email="a@example.com")
    headers_b = auth_header(user_id=USER_B, email="b@example.com")
    _onboard(client, headers_a, name="Company A")
    _onboard(client, headers_b, name="Company B")
    product_a = client.post("/api/products", json={"name": "Widget"}, headers=headers_a).json()

    assert client.get("/api/products", headers=headers_b).json() == []
    assert client.get(f"/api/products/{product_a['id']}", headers=headers_b).status_code == 404


def test_update_product_reassigns_supplier(client, auth_header):
    headers = auth_header(user_id=USER_A)
    _onboard(client, headers)
    supplier = _create_supplier(client, headers)
    product = client.post("/api/products", json={"name": "Widget"}, headers=headers).json()

    response = client.patch(
        f"/api/products/{product['id']}", json={"supplier_id": supplier["id"]}, headers=headers
    )
    assert response.status_code == 200
    assert response.json()["supplier_id"] == supplier["id"]


def test_add_packaging_component_and_see_status_flip_to_green(client, auth_header):
    headers = auth_header(user_id=USER_A)
    _onboard(client, headers)
    product = client.post("/api/products", json={"name": "Widget"}, headers=headers).json()

    incomplete = client.post(
        f"/api/products/{product['id']}/packaging-components",
        json={"name": "Outer box", "packaging_type": "box", "material": "cardboard"},
        headers=headers,
    )
    assert incomplete.status_code == 201
    assert incomplete.json()["status"] == "orange"
    assert "weight_grams" in incomplete.json()["missing_fields"]

    detail_after_incomplete = client.get(f"/api/products/{product['id']}", headers=headers).json()
    assert detail_after_incomplete["status"] == "orange"
    assert len(detail_after_incomplete["packaging_components"]) == 1

    complete = client.patch(
        f"/api/products/{product['id']}/packaging-components/{incomplete.json()['id']}",
        json={"weight_grams": 50.0, "recycled_content_percentage": 30.0},
        headers=headers,
    )
    assert complete.status_code == 200
    assert complete.json()["status"] == "green"
    assert complete.json()["missing_fields"] == []

    detail_after_complete = client.get(f"/api/products/{product['id']}", headers=headers).json()
    assert detail_after_complete["status"] == "green"


def test_packaging_component_rejects_invalid_packaging_type(client, auth_header):
    headers = auth_header(user_id=USER_A)
    _onboard(client, headers)
    product = client.post("/api/products", json={"name": "Widget"}, headers=headers).json()

    response = client.post(
        f"/api/products/{product['id']}/packaging-components",
        json={"name": "Mystery item", "packaging_type": "not-a-real-type"},
        headers=headers,
    )
    assert response.status_code == 422


def test_packaging_components_are_isolated_between_companies(client, auth_header):
    headers_a = auth_header(user_id=USER_A, email="a@example.com")
    headers_b = auth_header(user_id=USER_B, email="b@example.com")
    _onboard(client, headers_a, name="Company A")
    _onboard(client, headers_b, name="Company B")
    product_a = client.post("/api/products", json={"name": "Widget"}, headers=headers_a).json()

    # Company B can't create/list/read components on Company A's product.
    assert (
        client.post(
            f"/api/products/{product_a['id']}/packaging-components",
            json={"name": "Box", "packaging_type": "box"},
            headers=headers_b,
        ).status_code
        == 404
    )
    assert (
        client.get(
            f"/api/products/{product_a['id']}/packaging-components", headers=headers_b
        ).status_code
        == 404
    )
