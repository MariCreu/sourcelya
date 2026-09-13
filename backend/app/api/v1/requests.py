import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_company, get_current_user, get_db, get_email_service
from app.models.company import Company
from app.models.user import User
from app.schemas.compliance_request import (
    ComplianceRequestCreate,
    ComplianceRequestRead,
    ComplianceRequestSendResult,
)
from app.services.compliance_request_service import (
    ComplianceRequestService,
    ProductNotInSupplierError,
    RequestNotDraftError,
    RequestTokenNotActiveError,
    SupplierNotFoundError,
)
from app.services.email_service import EmailService

router = APIRouter(prefix="/requests", tags=["requests"])


def _service(db: Session, email_service: EmailService) -> ComplianceRequestService:
    return ComplianceRequestService(db, email_service)


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
    return ComplianceRequestRead.from_model(request)


@router.get("", response_model=list[ComplianceRequestRead])
def list_requests(
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
    email_service: EmailService = Depends(get_email_service),
) -> list[ComplianceRequestRead]:
    requests = _service(db, email_service).list(company.id)
    return [ComplianceRequestRead.from_model(request) for request in requests]


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
    return ComplianceRequestRead.from_model(request)


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
    return ComplianceRequestSendResult.from_model(request, request_url)


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
    return ComplianceRequestRead.from_model(request)


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
    return ComplianceRequestSendResult.from_model(request, request_url)
