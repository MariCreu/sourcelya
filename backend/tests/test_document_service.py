import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import Settings
from app.core.database import Base
from app.domain.enums import RequestStatus
from app.integrations.storage.memory_storage import InMemoryStorageService
from app.models import *  # noqa: F401,F403 register models on Base.metadata
from app.models.company import Company
from app.models.compliance_request import ComplianceRequest
from app.services.document_service import (
    DocumentService,
    FileTooLargeError,
    RequestNotEditableError,
    UnsupportedFileTypeError,
    UploadedFilePayload,
)

TEST_SETTINGS = Settings(
    supabase_jwt_strategy="hs256",
    supabase_jwt_secret="x",
    max_upload_size_mb=1,
    allowed_upload_extensions=["pdf", "png"],
)


@pytest.fixture
def db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def draft_request(db):
    company = Company(name="Acme", country="NL", owner_user_id=uuid.uuid4())
    db.add(company)
    db.flush()
    request = ComplianceRequest(
        company_id=company.id,
        supplier_id=uuid.uuid4(),
        status=RequestStatus.SENT.value,
        language="en",
    )
    db.add(request)
    db.flush()
    return request


def _service(db):
    return DocumentService(db, InMemoryStorageService(), settings=TEST_SETTINGS)


def test_upload_accepts_allowed_extension(db, draft_request):
    upload = UploadedFilePayload(filename="spec.pdf", content_type="application/pdf", content=b"%PDF-1.4")
    document = _service(db).upload_for_request(draft_request, upload)
    assert document.filename == "spec.pdf"
    assert document.content_type == "application/pdf"
    assert document.extraction_status == "pending"
    assert document.document_type == "other"


def test_upload_rejects_disallowed_extension(db, draft_request):
    upload = UploadedFilePayload(filename="malware.exe", content_type="application/x-msdownload", content=b"x")
    with pytest.raises(UnsupportedFileTypeError):
        _service(db).upload_for_request(draft_request, upload)


def test_upload_rejects_mismatched_mime_for_extension(db, draft_request):
    upload = UploadedFilePayload(filename="fake.pdf", content_type="image/png", content=b"x")
    with pytest.raises(UnsupportedFileTypeError):
        _service(db).upload_for_request(draft_request, upload)


def test_upload_tolerates_generic_octet_stream_content_type(db, draft_request):
    upload = UploadedFilePayload(filename="spec.pdf", content_type="application/octet-stream", content=b"x")
    document = _service(db).upload_for_request(draft_request, upload)
    # Canonical content type is stored, never the client's generic one.
    assert document.content_type == "application/pdf"


def test_upload_rejects_file_over_size_limit(db, draft_request):
    too_big = b"x" * (2 * 1024 * 1024)  # 2MB > 1MB limit in TEST_SETTINGS
    upload = UploadedFilePayload(filename="big.pdf", content_type="application/pdf", content=too_big)
    with pytest.raises(FileTooLargeError):
        _service(db).upload_for_request(draft_request, upload)


def test_upload_rejected_once_request_is_submitted(db, draft_request):
    draft_request.status = RequestStatus.SUBMITTED.value
    upload = UploadedFilePayload(filename="spec.pdf", content_type="application/pdf", content=b"x")
    with pytest.raises(RequestNotEditableError):
        _service(db).upload_for_request(draft_request, upload)


def test_delete_rejected_once_request_is_submitted(db, draft_request):
    upload = UploadedFilePayload(filename="spec.pdf", content_type="application/pdf", content=b"x")
    document = _service(db).upload_for_request(draft_request, upload)
    draft_request.status = RequestStatus.SUBMITTED.value
    with pytest.raises(RequestNotEditableError):
        _service(db).delete_for_request(draft_request, document.id)
