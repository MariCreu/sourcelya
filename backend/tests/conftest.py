import os
import uuid
from datetime import datetime, timedelta, timezone

os.environ.setdefault("SUPABASE_JWT_SECRET", "test-secret")
os.environ.setdefault("ENVIRONMENT", "test")

import pytest
from fastapi.testclient import TestClient
from jose import jwt
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.deps import get_db
from app.core.config import get_settings
from app.core.database import Base
from app.main import app

get_settings.cache_clear()
settings = get_settings()

# Import models so they register on Base.metadata before create_all.
from app.models import *  # noqa: E402,F401,F403

engine = create_engine(
    "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
)
TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def _override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


app.dependency_overrides[get_db] = _override_get_db


@pytest.fixture(autouse=True)
def _clean_database():
    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)


@pytest.fixture
def client():
    # Not using `with TestClient(...)` on purpose: that would run the
    # startup/shutdown lifespan (including the APScheduler background
    # scheduler) on every single test.
    return TestClient(app)


def make_supabase_token(
    *,
    user_id: str | None = None,
    email: str | None = "user@example.com",
    expired: bool = False,
    audience: str = "authenticated",
) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id or str(uuid.uuid4()),
        "aud": audience,
        "iat": now,
        "exp": now - timedelta(hours=1) if expired else now + timedelta(hours=1),
    }
    if email is not None:
        payload["email"] = email
    return jwt.encode(payload, settings.supabase_jwt_secret, algorithm=settings.jwt_algorithm)


@pytest.fixture
def auth_header():
    def _make(user_id: str | None = None, email: str = "user@example.com") -> dict[str, str]:
        token = make_supabase_token(user_id=user_id, email=email)
        return {"Authorization": f"Bearer {token}"}

    return _make
