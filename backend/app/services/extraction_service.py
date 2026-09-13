"""Turns one `SupplierDocument` into `ExtractedField` proposals.

This service NEVER writes to `PackagingComponent` — see
`ExtractedFieldService` for the only code path allowed to do that, gated
on an explicit human ACCEPT. Its whole job stops at "here is what the
document appears to say, with evidence"; whether that's actually applied
is a separate, later decision.

Run synchronously, inline with the upload request (see
`app/api/v1/public_requests.py`) — there is no job queue in this codebase
(see the root README's "Why not an in-process scheduler" for why: no
Celery/Redis, `POST /internal/jobs/process-reminders` is the one
background-work shape that exists, and it's for cron-style periodic work,
not per-upload processing). Running extraction inline keeps this
consistent — one document, one request, one LLM call — at the cost of the
supplier's upload request taking as long as that call. Documented as
technical debt: production volume would want this moved off the request
path.
"""

import uuid

from sqlalchemy.orm import Session

from app.domain.enums import AuditEventType, ConfidenceLevel, ExtractionStatus
from app.integrations.extraction.base import DocumentExtractionService, ExtractionError
from app.integrations.storage.base import StorageService
from app.models.extracted_field import ExtractedField
from app.models.supplier_document import SupplierDocument
from app.repositories.compliance_request_repository import ComplianceRequestRepository
from app.services.audit_service import AuditService


class ExtractionService:
    def __init__(
        self,
        db: Session,
        extractor: DocumentExtractionService,
        storage: StorageService,
    ):
        self.db = db
        self.extractor = extractor
        self.storage = storage
        self.audit_service = AuditService(db)
        self.request_repository = ComplianceRequestRepository(db)

    def process(self, document: SupplierDocument) -> SupplierDocument:
        document.extraction_status = ExtractionStatus.PROCESSING.value
        document.extraction_attempts += 1
        self.db.flush()

        try:
            file_bytes = self.storage.download(path=document.storage_path)
            result = self.extractor.extract(
                file_bytes=file_bytes,
                filename=document.filename,
                content_type=document.content_type,
            )
        except ExtractionError as exc:
            return self._mark_failed(document, str(exc))
        except Exception as exc:  # pragma: no cover — defense in depth
            return self._mark_failed(document, f"Unexpected error: {exc}")

        document.document_type = result.document_classification
        document.extraction_model = result.model
        document.extraction_input_tokens = result.input_tokens
        document.extraction_output_tokens = result.output_tokens
        document.extraction_duration_ms = result.duration_ms
        document.extraction_cost_usd = result.estimated_cost_usd
        document.processing_error = None

        component_id = self._unambiguous_component_id(document.company_id, document.request_id)

        has_low_confidence = False
        for suggestion in result.fields:
            if suggestion.confidence == ConfidenceLevel.LOW.value:
                has_low_confidence = True
            self.db.add(
                ExtractedField(
                    company_id=document.company_id,
                    document_id=document.id,
                    request_id=document.request_id,
                    packaging_component_id=component_id,
                    field_name=suggestion.field_name,
                    extracted_value=suggestion.value,
                    confidence=suggestion.confidence,
                    source_page=suggestion.source_page,
                    source_quote=suggestion.source_quote,
                    quote_verified=suggestion.quote_verified,
                )
            )

        document.extraction_status = (
            ExtractionStatus.REVIEW_REQUIRED.value
            if has_low_confidence
            else ExtractionStatus.COMPLETED.value
        )
        self.db.flush()
        self.audit_service.record(
            company_id=document.company_id,
            event_type=AuditEventType.EXTRACTION_COMPLETED,
            entity_type="supplier_document",
            entity_id=document.id,
            metadata={
                "fields_found": len(result.fields),
                "classification": result.document_classification,
                "model": result.model,
            },
        )
        return document

    def _mark_failed(self, document: SupplierDocument, error: str) -> SupplierDocument:
        document.extraction_status = ExtractionStatus.FAILED.value
        document.processing_error = error[:2000]
        self.db.flush()
        self.audit_service.record(
            company_id=document.company_id,
            event_type=AuditEventType.EXTRACTION_FAILED,
            entity_type="supplier_document",
            entity_id=document.id,
            metadata={"error": error[:500], "attempt": document.extraction_attempts},
        )
        return document

    def _unambiguous_component_id(
        self, company_id: uuid.UUID, request_id: uuid.UUID | None
    ) -> uuid.UUID | None:
        """Auto-link a proposal to the one PackagingComponent it can only be
        about — when a request covers several, the reviewer picks at accept
        time instead of a heuristic guessing for them."""
        if request_id is None:
            return None
        request = self.request_repository.get(company_id, request_id)
        if request is None:
            return None
        components = [
            component
            for request_product in request.products
            for component in request_product.product.packaging_components
        ]
        if len(components) == 1:
            return components[0].id
        return None
