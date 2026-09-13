import uuid

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.api.deps import (
    get_current_company,
    get_current_user,
    get_db,
    get_email_service,
    get_extraction_service,
    get_storage_service,
)
from app.integrations.extraction.base import DocumentExtractionService
from app.integrations.storage.base import StorageService
from app.models.company import Company
from app.models.user import User
from app.repositories.compliance_request_repository import ComplianceRequestRepository
from app.repositories.extracted_field_repository import ExtractedFieldRepository
from app.repositories.supplier_document_repository import SupplierDocumentRepository
from app.schemas.extracted_field import AcceptExtractedFieldPayload, ExtractedFieldConflict, ExtractedFieldRead
from app.schemas.supplier_document import SupplierDocumentRead
from app.services.document_service import DocumentService
from app.services.email_service import EmailService
from app.services.extracted_field_service import (
    ComponentNotInRequestError,
    ComponentNotSpecifiedError,
    ExtractedFieldNotFoundError,
    ExtractedFieldService,
    FieldAlreadyReviewedError,
    FieldConflictError,
    InvalidExtractedValueError,
)
from app.services.extraction_service import ExtractionService
from app.services.follow_up_service import FollowUpService

router = APIRouter(prefix="/documents", tags=["documents"])


def _safe_filename(filename: str) -> str:
    """Strips characters that could break the Content-Disposition header
    (quotes, CR/LF) — the filename is company-controlled data by the time
    it reaches here, but nothing downstream should have to trust that."""
    return filename.replace('"', "'").replace("\r", "").replace("\n", "")


@router.get("/{document_id}/download")
def download_document(
    document_id: uuid.UUID,
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
    storage: StorageService = Depends(get_storage_service),
) -> Response:
    result = DocumentService(db, storage).get_for_download(company.id, document_id)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    document, content = result
    return Response(
        content=content,
        media_type=document.content_type,
        headers={
            "Content-Disposition": f'attachment; filename="{_safe_filename(document.filename)}"'
        },
    )


@router.get("/{document_id}/extracted-fields", response_model=list[ExtractedFieldRead])
def list_extracted_fields(
    document_id: uuid.UUID,
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
) -> list[ExtractedFieldRead]:
    if SupplierDocumentRepository(db).get(company.id, document_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    fields = ExtractedFieldRepository(db).list_for_document(company.id, document_id)
    return [ExtractedFieldRead.from_model(field) for field in fields]


@router.post(
    "/{document_id}/extracted-fields/{field_id}/accept", response_model=ExtractedFieldRead
)
def accept_extracted_field(
    document_id: uuid.UUID,
    field_id: uuid.UUID,
    payload: AcceptExtractedFieldPayload,
    company: Company = Depends(get_current_company),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    email_service: EmailService = Depends(get_email_service),
) -> ExtractedFieldRead:
    service = ExtractedFieldService(db)
    try:
        field = service.accept(
            company.id,
            user.id,
            field_id,
            packaging_component_id=payload.packaging_component_id,
            conflict_resolution=payload.conflict_resolution,
        )
    except ExtractedFieldNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except FieldAlreadyReviewedError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except (ComponentNotSpecifiedError, ComponentNotInRequestError, InvalidExtractedValueError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except FieldConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=ExtractedFieldConflict(
                field_name=exc.field_name,
                current_value=exc.current_value,
                extracted_value=exc.extracted_value,
            ).model_dump(),
        ) from exc
    if field.document_id != document_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Field not found")

    _reevaluate_after_review(db, email_service, company, field.request_id, user.id)
    return ExtractedFieldRead.from_model(field)


def _reevaluate_after_review(
    db: Session,
    email_service: EmailService,
    company: Company,
    request_id: uuid.UUID,
    actor_user_id: uuid.UUID,
) -> None:
    """Accepting/rejecting a field is the other moment (besides supplier
    submit) that can make a request COMPLETE, or clear the way for an
    automatic follow-up — see FollowUpService.reevaluate's docstring."""
    request = ComplianceRequestRepository(db).get(company.id, request_id)
    if request is not None:
        FollowUpService(db, email_service).reevaluate(company, actor_user_id, request)


@router.post(
    "/{document_id}/extracted-fields/{field_id}/reject", response_model=ExtractedFieldRead
)
def reject_extracted_field(
    document_id: uuid.UUID,
    field_id: uuid.UUID,
    company: Company = Depends(get_current_company),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    email_service: EmailService = Depends(get_email_service),
) -> ExtractedFieldRead:
    try:
        field = ExtractedFieldService(db).reject(company.id, user.id, field_id)
    except ExtractedFieldNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except FieldAlreadyReviewedError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    if field.document_id != document_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Field not found")

    _reevaluate_after_review(db, email_service, company, field.request_id, user.id)
    return ExtractedFieldRead.from_model(field)


@router.post("/{document_id}/retry-extraction", response_model=SupplierDocumentRead)
def retry_extraction(
    document_id: uuid.UUID,
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
    storage: StorageService = Depends(get_storage_service),
    extractor: DocumentExtractionService = Depends(get_extraction_service),
) -> SupplierDocumentRead:
    document = SupplierDocumentRepository(db).get(company.id, document_id)
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    document = ExtractionService(db, extractor, storage).process(document)
    fields = ExtractedFieldRepository(db).list_for_document(company.id, document_id)
    return SupplierDocumentRead.from_model(document, fields)
