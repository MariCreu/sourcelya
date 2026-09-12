"""High-signal checks that only mean anything against a real Postgres.

Deliberately not a mirror of the fast suite — these exist only for the
specific SQLite-vs-Postgres divergences that would otherwise go unnoticed
until production. See tests/integration/README.md.

Not included here: a `secure_token_hash` check. That column lives on
`ComplianceRequest`, which doesn't exist until FASE 3 — adding a test for a
table we haven't built would just be decoration. `hash_token`/
`generate_secure_token` themselves are pure functions with no DB dependency
and are already covered in the fast suite (test_security_tokens.py); there
is nothing Postgres-specific to add for them today.
"""

import uuid

import pytest
from sqlalchemy import inspect
from sqlalchemy.exc import DataError, IntegrityError

from app.models.company import Company
from app.models.supplier import Supplier
from app.models.user import User
from app.repositories.base import CompanyScopedRepository


class SupplierRepository(CompanyScopedRepository[Supplier]):
    model = Supplier


def test_migrations_create_the_expected_tables(pg_engine):
    tables = set(inspect(pg_engine).get_table_names())
    assert {"users", "companies", "suppliers", "products", "packaging_components"} <= tables


def test_company_and_user_round_trip_through_the_real_driver(pg_session):
    """Also exercises the custom GUID type against psycopg (not SQLite's
    generic CHAR fallback) — the id must come back as a real uuid.UUID.
    """
    user = User(id=uuid.uuid4(), email="owner@example.com")
    pg_session.add(user)
    pg_session.flush()

    company = Company(name="Acme BV", country="NL", owner_user_id=user.id)
    pg_session.add(company)
    pg_session.flush()
    user.company_id = company.id
    pg_session.commit()

    fetched = pg_session.get(Company, company.id)
    assert fetched is not None
    assert fetched.name == "Acme BV"
    assert isinstance(fetched.id, uuid.UUID)


def test_foreign_key_is_enforced_for_supplier_company_id(pg_session):
    """SQLite doesn't enforce foreign keys unless `PRAGMA foreign_keys=ON`
    is set — our fast-suite engine doesn't set it — so a missing/broken FK
    here would sail through the fast suite undetected.
    """
    orphan = Supplier(company_id=uuid.uuid4(), name="Ghost Co", email="ghost@example.com")
    pg_session.add(orphan)
    with pytest.raises(IntegrityError):
        pg_session.flush()


def test_country_column_enforces_its_varchar_length(pg_session):
    """Postgres enforces VARCHAR(n) at the column level; SQLite has no such
    concept and would silently accept a too-long value.
    """
    user = User(id=uuid.uuid4(), email="owner2@example.com")
    pg_session.add(user)
    pg_session.flush()

    too_long = Company(name="Bad Co", country="NLD", owner_user_id=user.id)  # column is VARCHAR(2)
    pg_session.add(too_long)
    with pytest.raises(DataError):
        pg_session.flush()


def test_user_email_uniqueness_is_enforced(pg_session):
    pg_session.add(User(id=uuid.uuid4(), email="dupe@example.com"))
    pg_session.flush()

    pg_session.add(User(id=uuid.uuid4(), email="dupe@example.com"))
    with pytest.raises(IntegrityError):
        pg_session.flush()


def test_company_scoped_repository_isolation_against_the_real_database(pg_session):
    """Mirrors tests/test_company_isolation.py, but end to end against the
    real database/driver rather than SQLite.
    """
    user = User(id=uuid.uuid4(), email="a@example.com")
    pg_session.add(user)
    pg_session.flush()

    company = Company(name="Company A", country="NL", owner_user_id=user.id)
    pg_session.add(company)
    pg_session.flush()

    supplier = Supplier(company_id=company.id, name="Supplier A", email="s@example.com")
    pg_session.add(supplier)
    pg_session.flush()

    repo = SupplierRepository(pg_session)
    other_company_id = uuid.uuid4()

    assert repo.get(company.id, supplier.id) is not None
    assert repo.get(other_company_id, supplier.id) is None
    assert repo.list(other_company_id) == []
