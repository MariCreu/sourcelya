"""Fixtures for the `-m integration` suite: real PostgreSQL, not SQLite.

Why this exists at all: our fast suite (`tests/conftest.py`) runs against
SQLite for speed, but SQLite silently diverges from Postgres in ways that
matter here — it doesn't enforce foreign keys unless a pragma is set (ours
isn't), and it doesn't enforce VARCHAR(n) length limits at all. A schema bug
in either of those would pass the fast suite and only show up in
production/Supabase. This package is the small, deliberately narrow set of
tests that catches that class of bug — see tests/integration/README.md.

Reuses the same Postgres docker-compose already provides for local dev
(`docker compose up -d postgres`) rather than standing up separate
infrastructure. Truncates the app's tables before every test for isolation,
so don't point this at a database with data you care about.
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

BACKEND_DIR = Path(__file__).resolve().parents[2]

INTEGRATION_DATABASE_URL = os.environ.get(
    "INTEGRATION_DATABASE_URL",
    "postgresql+psycopg://sourcelya:sourcelya@localhost:5432/sourcelya",
)

APP_TABLES = ("packaging_components", "products", "suppliers", "companies", "users")


def pytest_collection_modifyitems(config, items):
    # A conftest.py hook applies to the whole session, not just its own
    # directory, so this must explicitly scope itself to files under here —
    # otherwise every test in the suite gets marked "integration".
    integration_dir = str(Path(__file__).resolve().parent)
    for item in items:
        if str(item.path).startswith(integration_dir):
            item.add_marker(pytest.mark.integration)


@pytest.fixture(scope="session")
def pg_engine():
    engine = create_engine(INTEGRATION_DATABASE_URL)
    try:
        with engine.connect():
            pass
    except Exception as exc:  # noqa: BLE001 - reporting, not handling
        pytest.skip(
            f"PostgreSQL not reachable at {INTEGRATION_DATABASE_URL} ({exc}). "
            "Start it with `docker compose up -d postgres` and retry."
        )

    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=BACKEND_DIR,
        env={**os.environ, "DATABASE_URL": INTEGRATION_DATABASE_URL},
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        pytest.fail(f"alembic upgrade head failed:\n{result.stdout}\n{result.stderr}")

    yield engine
    engine.dispose()


@pytest.fixture
def pg_session(pg_engine):
    with pg_engine.begin() as conn:
        conn.execute(text(f"TRUNCATE TABLE {', '.join(APP_TABLES)} RESTART IDENTITY CASCADE"))

    Session = sessionmaker(bind=pg_engine)
    session = Session()
    try:
        yield session
    finally:
        session.rollback()
        session.close()
