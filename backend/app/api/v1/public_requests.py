import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_email_service, get_extraction_service, get_storage_service
from app.core.rate_limit import limiter
from app.integrations.extraction.base import DocumentExtractionService
from app.integrations.storage.base import StorageService
from app.repositories.company_repository import CompanyRepository
from app.repositories.supplier_document_repository import SupplierDocumentRepository
from app.schemas.public_request import PublicComplianceRequestRead, PublicSaveRequestPayload
from app.services.document_service import (
    DocumentNotFoundError,
    DocumentService,
    FileTooLargeError,
    RequestNotEditableError,
    UnsupportedFileTypeError,
    UploadedFilePayload,
)
from app.services.email_service import EmailService
from app.services.extraction_service import ExtractionService
from app.services.follow_up_service import FollowUpService
from app.services.missing_information_service import MissingInformationService
from app.services.public_request_service import (
    ComponentNotInRequestError,
    InvalidTokenError,
    PublicRequestService,
    RequestAlreadySubmittedError,
    TokenExpiredError,
    TokenRevokedError,
)

router = APIRouter(prefix="/public/requests", tags=["public-requests"])


def _to_public_read(db: Session, request) -> PublicComplianceRequestRead:
    company = CompanyRepository(db).get_by_id(request.company_id)
    documents = SupplierDocumentRepository(db).list_for_request(request.id)
    information_summary = MissingInformationService(db).summarize(request.company_id, request)
    return PublicComplianceRequestRead.from_model(
        request, company.name, documents, information_summary
    )


def _token_error_response(exc: Exception) -> HTTPException:
    """The three ways `PublicRequestService`/`resolve_token` can reject a
    token, mapped to HTTP status once so every token-scoped endpoint below
    (get/save/submit/upload/delete) reports them the same way.
    """
    if isinstance(exc, InvalidTokenError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Link not found")
    if isinstance(exc, TokenExpiredError):
        return HTTPException(status_code=status.HTTP_410_GONE, detail="This link has expired")
    if isinstance(exc, TokenRevokedError):
        return HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="This link has been revoked"
        )
    raise AssertionError(f"not a token error: {exc!r}")


@router.get("/{token}", response_model=PublicComplianceRequestRead)
def get_public_request(token: str, db: Session = Depends(get_db)) -> PublicComplianceRequestRead:
    try:
        request = PublicRequestService(db).get_by_token(token)
    except (InvalidTokenError, TokenExpiredError, TokenRevokedError) as exc:
        raise _token_error_response(exc) from exc
    return _to_public_read(db, request)


@router.patch("/{token}", response_model=PublicComplianceRequestRead)
def save_public_request(
    token: str, payload: PublicSaveRequestPayload, db: Session = Depends(get_db)
) -> PublicComplianceRequestRead:
    try:
        request = PublicRequestService(db).save_progress(token, payload)
    except (InvalidTokenError, TokenExpiredError, TokenRevokedError) as exc:
        raise _token_error_response(exc) from exc
    except ComponentNotInRequestError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except RequestAlreadySubmittedError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return _to_public_read(db, request)


@router.post("/{token}/submit", response_model=PublicComplianceRequestRead)
def submit_public_request(
    token: str,
    db: Session = Depends(get_db),
    email_service: EmailService = Depends(get_email_service),
) -> PublicComplianceRequestRead:
    try:
        request = PublicRequestService(db).submit(token)
    except (InvalidTokenError, TokenExpiredError, TokenRevokedError) as exc:
        raise _token_error_response(exc) from exc

    # Submitting never decides completeness by itself — see
    # PublicRequestService.submit's docstring. FollowUpService.reevaluate()
    # is what may flip the request to COMPLETED (+ thank-you email) or,
    # only if this request opted into automatic_follow_up, send the next
    # follow-up round automatically. Needs the Company/EmailService context
    # PublicRequestService deliberately doesn't have (it only knows a
    # token), so this happens here, not inside the service.
    company = CompanyRepository(db).get_by_id(request.company_id)
    FollowUpService(db, email_service).reevaluate(company, None, request)
    return _to_public_read(db, request)


@router.post("/{token}/documents", response_model=PublicComplianceRequestRead)
@limiter.limit("10/minute")
async def upload_public_document(
    request: Request,
    token: str,
    file: UploadFile,
    db: Session = Depends(get_db),
    storage: StorageService = Depends(get_storage_service),
    extractor: DocumentExtractionService = Depends(get_extraction_service),
) -> PublicComplianceRequestRead:
    try:
        request = PublicRequestService(db).resolve_token(token)
    except (InvalidTokenError, TokenExpiredError, TokenRevokedError) as exc:
        raise _token_error_response(exc) from exc

    content = await file.read()
    upload = UploadedFilePayload(
        filename=file.filename or "upload",
        content_type=file.content_type or "",
        content=content,
    )
    try:
        document = DocumentService(db, storage).upload_for_request(request, upload)
    except RequestNotEditableError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except UnsupportedFileTypeError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except FileTooLargeError as exc:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail=str(exc)
        ) from exc

    # Synchronous, inline extraction — see ExtractionService's module
    # docstring for why (no job queue in this codebase) and the FASE 5
    # report's technical-debt section for the tradeoff this accepts.
    ExtractionService(db, extractor, storage).process(document)
    return _to_public_read(db, request)


@router.delete("/{token}/documents/{document_id}", response_model=PublicComplianceRequestRead)
def delete_public_document(
    token: str,
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
    storage: StorageService = Depends(get_storage_service),
) -> PublicComplianceRequestRead:
    try:
        request = PublicRequestService(db).resolve_token(token)
    except (InvalidTokenError, TokenExpiredError, TokenRevokedError) as exc:
        raise _token_error_response(exc) from exc

    try:
        DocumentService(db, storage).delete_for_request(request, document_id)
    except RequestNotEditableError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except DocumentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return _to_public_read(db, request)
