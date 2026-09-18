import os
import uuid
from datetime import datetime, timedelta, timezone

os.environ.setdefault("SUPABASE_JWT_STRATEGY", "hs256")
os.environ.setdefault("SUPABASE_JWT_SECRET", "test-secret-at-least-32-bytes-long")
os.environ.setdefault("INTERNAL_JOBS_SECRET", "test-internal-secret")
os.environ.setdefault("ENVIRONMENT", "test")

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.deps import get_db, get_email_service, get_extraction_service, get_malware_scanner
from app.core.config import get_settings
from app.core.database import Base
from app.core.rate_limit import limiter
from app.core.security import get_token_verifier
from app.main import app
from app.services.email_service import EmailService
from tests.fakes import FakeDocumentExtractionService, FakeMalwareScanner, RecordingEmailSender

get_settings.cache_clear()
get_token_verifier.cache_clear()
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


@pytest.fixture(autouse=True)
def _reset_rate_limits():
    """Every test shares one TestClient "remote address", so without a
    reset, request counts would accumulate across the whole test session
    and eventually trip the real rate limits (see app/core/rate_limit.py)
    on tests that have nothing to do with rate limiting.
    """
    limiter.reset()
    yield


@pytest.fixture
def client():
    # Not using `with TestClient(...)` on purpose: that would run FastAPI's
    # startup/shutdown lifespan on every single test, which we don't need.
    return TestClient(app)


def make_supabase_token(
    *,
    user_id: str | None = None,
    email: str | None = "user@example.com",
    expired: bool = False,
    audience: str = "authenticated",
) -> str:
    """Mints a token for the test (hs256) verifier strategy — see
    test_auth_jwks.py for tokens exercising the real asymmetric/JWKS path.
    """
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id or str(uuid.uuid4()),
        "aud": audience,
        "iat": now,
        "exp": now - timedelta(hours=1) if expired else now + timedelta(hours=1),
    }
    if email is not None:
        payload["email"] = email
    return jwt.encode(payload, settings.supabase_jwt_secret, algorithm="HS256")


@pytest.fixture
def auth_header():
    def _make(user_id: str | None = None, email: str = "user@example.com") -> dict[str, str]:
        token = make_supabase_token(user_id=user_id, email=email)
        return {"Authorization": f"Bearer {token}"}

    return _make


@pytest.fixture
def internal_jobs_header():
    return {"X-Internal-Jobs-Secret": settings.internal_jobs_secret}


@pytest.fixture
def recording_email_sender():
    """Overrides the email dependency for the duration of one test so the
    request/reminder flow never depends on (or tries to reach) a real
    provider — see EmailSender/ConsoleEmailSender/ResendEmailSender.
    """
    sender = RecordingEmailSender()
    app.dependency_overrides[get_email_service] = lambda: EmailService(sender)
    try:
        yield sender
    finally:
        del app.dependency_overrides[get_email_service]


@pytest.fixture
def fake_extraction_service():
    """Overrides the extraction dependency so uploads never call a real,
    paid LLM in the fast suite — set `.result`/`.error` on the returned
    fake before each upload to control what that call returns (see
    tests/fakes.py).
    """
    service = FakeDocumentExtractionService()
    app.dependency_overrides[get_extraction_service] = lambda: service
    try:
        yield service
    finally:
        del app.dependency_overrides[get_extraction_service]


@pytest.fixture
def fake_malware_scanner():
    """Overrides the malware-scan dependency — clean by default; set
    `.error` on the returned fake (see tests/fakes.py's
    infected_file_error()/scanner_unavailable_error()) to exercise the
    rejected-upload paths without a real ClamAV daemon.
    """
    scanner = FakeMalwareScanner()
    app.dependency_overrides[get_malware_scanner] = lambda: scanner
    try:
        yield scanner
    finally:
        del app.dependency_overrides[get_malware_scanner]
