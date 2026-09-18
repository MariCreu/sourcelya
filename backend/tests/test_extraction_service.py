import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.domain.enums import ExtractionStatus, RequestStatus
from app.integrations.extraction.base import (
    DocumentExtractionResult,
    ExtractedFieldSuggestion,
    ExtractionError,
)
from app.integrations.storage.memory_storage import InMemoryStorageService
from app.models import *  # noqa: F401,F403 register models on Base.metadata
from app.models.company import Company
from app.models.compliance_request import ComplianceRequest, ComplianceRequestProduct
from app.models.extracted_field import ExtractedField
from app.models.packaging_component import PackagingComponent
from app.models.product import Product
from app.models.supplier_document import SupplierDocument
from app.services.extraction_service import ExtractionService
from tests.fakes import FakeDocumentExtractionService


@pytest.fixture
def db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def _make_request_with_document(db, *, component_count=1):
    company = Company(name="Acme", country="NL", owner_user_id=uuid.uuid4())
    db.add(company)
    db.flush()

    supplier_id = uuid.uuid4()
    request = ComplianceRequest(
        company_id=company.id, supplier_id=supplier_id, status=RequestStatus.SENT.value, language="en"
    )
    db.add(request)
    db.flush()

    for _ in range(component_count):
        product = Product(company_id=company.id, supplier_id=supplier_id, name="Widget")
        db.add(product)
        db.flush()
        component = PackagingComponent(product_id=product.id, name="Box", packaging_type="box")
        db.add(component)
        db.flush()
        db.add(ComplianceRequestProduct(request_id=request.id, product_id=product.id))
    db.flush()

    storage = InMemoryStorageService()
    document_id = uuid.uuid4()
    storage_path = f"companies/{company.id}/requests/{request.id}/{document_id}.pdf"
    storage.upload(path=storage_path, content=b"%PDF-1.4 fake", content_type="application/pdf")
    document = SupplierDocument(
        id=document_id,
        company_id=company.id,
        supplier_id=supplier_id,
        request_id=request.id,
        filename="spec.pdf",
        storage_path=storage_path,
        content_type="application/pdf",
        size_bytes=13,
    )
    db.add(document)
    db.flush()
    return document, storage


def test_successful_extraction_creates_extracted_fields(db):
    document, storage = _make_request_with_document(db)
    fake = FakeDocumentExtractionService(
        result=DocumentExtractionResult(
            document_classification="packaging_specification",
            fields=[
                ExtractedFieldSuggestion(
                    field_name="material",
                    value="Corrugated cardboard",
                    confidence="high",
                    source_page=1,
                    source_quote="Corrugated cardboard",
                    quote_verified=True,
                )
            ],
            model="fake-model",
            input_tokens=100,
            output_tokens=20,
            duration_ms=250,
            estimated_cost_usd=0.001,
        )
    )

    result = ExtractionService(db, fake, storage).process(document)

    assert result.extraction_status == ExtractionStatus.COMPLETED.value
    assert result.document_type == "packaging_specification"
    assert result.extraction_model == "fake-model"
    assert result.extraction_input_tokens == 100
    assert result.extraction_cost_usd == 0.001

    fields = db.query(ExtractedField).filter(ExtractedField.document_id == document.id).all()
    assert len(fields) == 1
    assert fields[0].field_name == "material"
    assert fields[0].review_status == "pending"
    # Only one packaging component exists for this request -> auto-linked.
    assert fields[0].packaging_component_id is not None


def test_not_found_fields_never_produce_a_row(db):
    """The extractor only ever returns suggestions for FOUND fields — a
    NOT_FOUND/UNKNOWN field is absence, not a low-value row (that absence
    is exactly what StatusCalculationService.missing_fields already means).
    """
    document, storage = _make_request_with_document(db)
    fake = FakeDocumentExtractionService(
        result=DocumentExtractionResult(
            document_classification="other", fields=[], model="fake", input_tokens=1,
            output_tokens=1, duration_ms=1, estimated_cost_usd=0.0,
        )
    )
    ExtractionService(db, fake, storage).process(document)
    assert db.query(ExtractedField).count() == 0


def test_low_confidence_field_marks_review_required(db):
    document, storage = _make_request_with_document(db)
    fake = FakeDocumentExtractionService(
        result=DocumentExtractionResult(
            document_classification="other",
            fields=[
                ExtractedFieldSuggestion(
                    field_name="material", value="plastic?", confidence="low",
                    source_page=1, source_quote="nope", quote_verified=False,
                )
            ],
            model="fake", input_tokens=1, output_tokens=1, duration_ms=1, estimated_cost_usd=0.0,
        )
    )
    result = ExtractionService(db, fake, storage).process(document)
    assert result.extraction_status == ExtractionStatus.REVIEW_REQUIRED.value


def test_extraction_failure_marks_failed_and_keeps_the_document(db):
    document, storage = _make_request_with_document(db)
    fake = FakeDocumentExtractionService(error=ExtractionError("provider timed out"))

    result = ExtractionService(db, fake, storage).process(document)

    assert result.extraction_status == ExtractionStatus.FAILED.value
    assert "provider timed out" in result.processing_error
    assert result.extraction_attempts == 1
    # The original file is untouched — still downloadable.
    assert storage.download(path=document.storage_path) == b"%PDF-1.4 fake"


def test_retry_after_failure_can_succeed(db):
    document, storage = _make_request_with_document(db)
    failing = FakeDocumentExtractionService(error=ExtractionError("temporary outage"))
    ExtractionService(db, failing, storage).process(document)
    assert document.extraction_status == ExtractionStatus.FAILED.value
    assert document.extraction_attempts == 1

    succeeding = FakeDocumentExtractionService(
        result=DocumentExtractionResult(
            document_classification="other", fields=[], model="fake", input_tokens=1,
            output_tokens=1, duration_ms=1, estimated_cost_usd=0.0,
        )
    )
    ExtractionService(db, succeeding, storage).process(document)
    assert document.extraction_status == ExtractionStatus.COMPLETED.value
    assert document.extraction_attempts == 2
    assert document.processing_error is None


def test_does_not_auto_link_component_when_request_has_several(db):
    document, storage = _make_request_with_document(db, component_count=2)
    fake = FakeDocumentExtractionService(
        result=DocumentExtractionResult(
            document_classification="other",
            fields=[
                ExtractedFieldSuggestion(
                    field_name="material", value="cardboard", confidence="high",
                    source_page=1, source_quote="cardboard", quote_verified=True,
                )
            ],
            model="fake", input_tokens=1, output_tokens=1, duration_ms=1, estimated_cost_usd=0.0,
        )
    )
    ExtractionService(db, fake, storage).process(document)
    field = db.query(ExtractedField).filter(ExtractedField.document_id == document.id).first()
    assert field.packaging_component_id is None
