import uuid

USER_A = "11111111-1111-1111-1111-111111111111"
USER_B = "22222222-2222-2222-2222-222222222222"


def test_companies_me_is_not_found_before_onboarding(client, auth_header):
    response = client.get("/api/companies/me", headers=auth_header(user_id=USER_A))
    assert response.status_code == 404


def test_user_can_create_and_then_read_their_own_company(client, auth_header):
    headers = auth_header(user_id=USER_A)
    create = client.post(
        "/api/companies", json={"name": "Acme BV", "country": "NL"}, headers=headers
    )
    assert create.status_code == 201
    company_id = create.json()["id"]

    read = client.get("/api/companies/me", headers=headers)
    assert read.status_code == 200
    assert read.json()["id"] == company_id


def test_user_cannot_onboard_twice(client, auth_header):
    headers = auth_header(user_id=USER_A)
    client.post("/api/companies", json={"name": "Acme BV", "country": "NL"}, headers=headers)

    second = client.post(
        "/api/companies", json={"name": "Another Co", "country": "DE"}, headers=headers
    )
    assert second.status_code == 409


def test_a_user_never_sees_another_companys_data(client, auth_header):
    headers_a = auth_header(user_id=USER_A, email="a@example.com")
    headers_b = auth_header(user_id=USER_B, email="b@example.com")

    company_a = client.post(
        "/api/companies", json={"name": "Company A", "country": "NL"}, headers=headers_a
    ).json()
    company_b = client.post(
        "/api/companies", json={"name": "Company B", "country": "ES"}, headers=headers_b
    ).json()

    assert company_a["id"] != company_b["id"]

    my_company_a = client.get("/api/companies/me", headers=headers_a).json()
    my_company_b = client.get("/api/companies/me", headers=headers_b).json()

    assert my_company_a["id"] == company_a["id"]
    assert my_company_b["id"] == company_b["id"]
    assert my_company_a["id"] != my_company_b["id"]


def test_repository_scoping_never_leaks_across_companies(client, auth_header):
    """Exercises CompanyScopedRepository directly: even if an endpoint forgot
    to filter, the repository layer must refuse to return another tenant's row.
    """
    from app.api.deps import get_db
    from app.main import app
    from app.models.supplier import Supplier
    from app.repositories.base import CompanyScopedRepository

    class SupplierRepository(CompanyScopedRepository[Supplier]):
        model = Supplier

    db_gen = app.dependency_overrides[get_db]()
    db = next(db_gen)
    try:
        company_a_id = uuid.uuid4()
        company_b_id = uuid.uuid4()
        supplier = Supplier(
            company_id=company_a_id, name="Shenzhen Wonderful Packaging", email="s@example.com"
        )
        db.add(supplier)
        db.flush()

        repo = SupplierRepository(db)
        assert repo.get(company_a_id, supplier.id) is not None
        assert repo.get(company_b_id, supplier.id) is None
        assert repo.list(company_b_id) == []
    finally:
        db.rollback()
