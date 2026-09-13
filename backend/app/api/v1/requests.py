import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_company, get_current_user, get_db, get_email_service
from app.models.company import Company
from app.models.compliance_request import ComplianceRequest
from app.models.user import User
from app.repositories.extracted_field_repository import ExtractedFieldRepository
from app.repositories.follow_up_round_repository import FollowUpRoundRepository
from app.repositories.supplier_document_repository import SupplierDocumentRepository
from app.schemas.compliance_request import (
    ComplianceRequestCreate,
    ComplianceRequestRead,
    ComplianceRequestSendResult,
)
from app.schemas.follow_up import AutomaticFollowUpToggle
from app.services.compliance_request_service import (
    ComplianceRequestService,
    ProductNotInSupplierError,
    RequestNotDraftError,
    RequestTokenNotActiveError,
    SupplierNotFoundError,
)
from app.services.email_service import EmailService
from app.services.follow_up_service import (
    DuplicateFollowUpError,
    ExtractionStillProcessingError,
    FollowUpService,
    NothingMissingError,
    RecoveryStats,
    RequestNotEligibleForFollowUpError,
    ReviewRequiredBeforeFollowUpError,
)
from app.services.missing_information_service import MissingInformationService

router = APIRouter(prefix="/requests", tags=["requests"])


def _service(db: Session, email_service: EmailService) -> ComplianceRequestService:
    return ComplianceRequestService(db, email_service)


def _read(db: Session, company_id: uuid.UUID, request: ComplianceRequest) -> ComplianceRequestRead:
    documents = SupplierDocumentRepository(db).list_for_request(request.id)
    extracted_fields_by_document = {}
    if documents:
        field_repo = ExtractedFieldRepository(db)
        for document in documents:
            extracted_fields_by_document[document.id] = field_repo.list_for_document(
                company_id, document.id
            )

    # FASE 6: the "Information status" panel + follow-up history + recovery
    # metric — computed live on every read, same pattern as
    # StatusCalculationService (see MissingInformationService's docstring).
    information_summary = MissingInformationService(db).summarize(company_id, request)
    follow_up_rounds = FollowUpRoundRepository(db).list_for_request(company_id, request.id)
    recovery_stats = RecoveryStats(
        total_requested=information_summary.total_requested,
        available_after_first_submission=request.fields_available_after_first_submission,
        available_now=information_summary.available_count,
        follow_up_recovered=(
            information_summary.available_count - request.fields_available_after_first_submission
            if request.fields_available_after_first_submission is not None
            else None
        ),
    )

    return ComplianceRequestRead.from_model(
        request,
        documents,
        extracted_fields_by_document,
        information_summary=information_summary,
        follow_up_rounds=follow_up_rounds,
        recovery_stats=recovery_stats,
    )


@router.post("", response_model=ComplianceRequestRead, status_code=status.HTTP_201_CREATED)
def create_request(
    payload: ComplianceRequestCreate,
    company: Company = Depends(get_current_company),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    email_service: EmailService = Depends(get_email_service),
) -> ComplianceRequestRead:
    try:
        request = _service(db, email_service).create(company.id, user.id, payload)
    except SupplierNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except ProductNotInSupplierError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return _read(db, company.id, request)


@router.get("", response_model=list[ComplianceRequestRead])
def list_requests(
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
    email_service: EmailService = Depends(get_email_service),
) -> list[ComplianceRequestRead]:
    requests = _service(db, email_service).list(company.id)
    return [_read(db, company.id, request) for request in requests]


@router.get("/{request_id}", response_model=ComplianceRequestRead)
def get_request(
    request_id: uuid.UUID,
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
    email_service: EmailService = Depends(get_email_service),
) -> ComplianceRequestRead:
    request = _service(db, email_service).get(company.id, request_id)
    if request is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found")
    return _read(db, company.id, request)


@router.post("/{request_id}/send", response_model=ComplianceRequestSendResult)
def send_request(
    request_id: uuid.UUID,
    company: Company = Depends(get_current_company),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    email_service: EmailService = Depends(get_email_service),
) -> ComplianceRequestSendResult:
    try:
        result = _service(db, email_service).send(company, user.id, request_id)
    except RequestNotDraftError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found")
    request, request_url = result
    documents = SupplierDocumentRepository(db).list_for_request(request.id)
    return ComplianceRequestSendResult.from_model(request, request_url, documents)


@router.post("/{request_id}/revoke", response_model=ComplianceRequestRead)
def revoke_request(
    request_id: uuid.UUID,
    company: Company = Depends(get_current_company),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    email_service: EmailService = Depends(get_email_service),
) -> ComplianceRequestRead:
    try:
        request = _service(db, email_service).revoke(company.id, user.id, request_id)
    except RequestTokenNotActiveError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    if request is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found")
    return _read(db, company.id, request)


@router.post("/{request_id}/resend", response_model=ComplianceRequestSendResult)
def resend_request(
    request_id: uuid.UUID,
    company: Company = Depends(get_current_company),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    email_service: EmailService = Depends(get_email_service),
) -> ComplianceRequestSendResult:
    try:
        result = _service(db, email_service).resend(company, user.id, request_id)
    except RequestTokenNotActiveError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found")
    request, request_url = result
    documents = SupplierDocumentRepository(db).list_for_request(request.id)
    return ComplianceRequestSendResult.from_model(request, request_url, documents)


@router.post("/{request_id}/follow-up", response_model=ComplianceRequestRead)
def create_follow_up(
    request_id: uuid.UUID,
    company: Company = Depends(get_current_company),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    email_service: EmailService = Depends(get_email_service),
) -> ComplianceRequestRead:
    """"Request missing information" — the manual path (FASE 6's default
    and safe way in): the company decides when, `FollowUpService` decides
    whether it's currently possible at all (see its guard exceptions)."""
    request = ComplianceRequestService(db, email_service).get(company.id, request_id)
    if request is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found")
    # Structured error codes (not just a message string) so the frontend
    # can show the exact right guidance — same pattern as the FASE 5
    # accept-conflict body (`detail.detail == "POSSIBLE CONFLICT"`).
    error_codes = {
        NothingMissingError: "nothing_missing",
        ExtractionStillProcessingError: "extraction_processing",
        ReviewRequiredBeforeFollowUpError: "review_required",
        DuplicateFollowUpError: "duplicate_follow_up",
        RequestNotEligibleForFollowUpError: "not_eligible",
    }
    try:
        FollowUpService(db, email_service).create_round(company, user.id, request, trigger="manual")
    except tuple(error_codes) as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": error_codes[type(exc)], "detail": str(exc)},
        ) from exc
    return _read(db, company.id, request)


@router.post("/{request_id}/automatic-follow-up", response_model=ComplianceRequestRead)
def set_automatic_follow_up(
    request_id: uuid.UUID,
    payload: AutomaticFollowUpToggle,
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
    email_service: EmailService = Depends(get_email_service),
) -> ComplianceRequestRead:
    """Opt-in, per-request, off by default — see FollowUpService's module
    docstring for why the company keeps explicit control during validation."""
    request = ComplianceRequestService(db, email_service).get(company.id, request_id)
    if request is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found")
    request.automatic_follow_up = payload.enabled
    db.flush()
    return _read(db, company.id, request)
