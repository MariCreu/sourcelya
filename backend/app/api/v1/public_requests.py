from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.repositories.company_repository import CompanyRepository
from app.schemas.public_request import PublicComplianceRequestRead, PublicSaveRequestPayload
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
    return PublicComplianceRequestRead.from_model(request, company.name)


@router.get("/{token}", response_model=PublicComplianceRequestRead)
def get_public_request(token: str, db: Session = Depends(get_db)) -> PublicComplianceRequestRead:
    try:
        request = PublicRequestService(db).get_by_token(token)
    except InvalidTokenError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Link not found") from exc
    except TokenExpiredError as exc:
        raise HTTPException(status_code=status.HTTP_410_GONE, detail="This link has expired") from exc
    except TokenRevokedError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="This link has been revoked"
        ) from exc
    return _to_public_read(db, request)


@router.patch("/{token}", response_model=PublicComplianceRequestRead)
def save_public_request(
    token: str, payload: PublicSaveRequestPayload, db: Session = Depends(get_db)
) -> PublicComplianceRequestRead:
    try:
        request = PublicRequestService(db).save_progress(token, payload)
    except InvalidTokenError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Link not found") from exc
    except TokenExpiredError as exc:
        raise HTTPException(status_code=status.HTTP_410_GONE, detail="This link has expired") from exc
    except TokenRevokedError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="This link has been revoked"
        ) from exc
    except ComponentNotInRequestError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except RequestAlreadySubmittedError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return _to_public_read(db, request)


@router.post("/{token}/submit", response_model=PublicComplianceRequestRead)
def submit_public_request(token: str, db: Session = Depends(get_db)) -> PublicComplianceRequestRead:
    try:
        request = PublicRequestService(db).submit(token)
    except InvalidTokenError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Link not found") from exc
    except TokenExpiredError as exc:
        raise HTTPException(status_code=status.HTTP_410_GONE, detail="This link has expired") from exc
    except TokenRevokedError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="This link has been revoked"
        ) from exc
    return _to_public_read(db, request)
