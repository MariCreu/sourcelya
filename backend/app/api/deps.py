from collections.abc import Generator

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.core.security import InvalidTokenError, SupabaseIdentity, decode_supabase_access_token
from app.integrations.email.base import EmailSender
from app.integrations.email.factory import get_email_sender
from app.integrations.extraction.factory import get_extraction_service  # noqa: F401 re-exported
from app.integrations.malware.factory import get_malware_scanner  # noqa: F401 re-exported
from app.integrations.storage.factory import get_storage_service  # noqa: F401 re-exported
from app.models.company import Company
from app.models.user import User
from app.services.company_service import CompanyService
from app.services.email_service import EmailService
from app.services.user_service import UserService

_bearer_scheme = HTTPBearer(auto_error=True)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def get_current_identity(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme),
) -> SupabaseIdentity:
    try:
        return decode_supabase_access_token(credentials.credentials)
    except InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication token",
        ) from exc


def get_current_user(
    identity: SupabaseIdentity = Depends(get_current_identity),
    db: Session = Depends(get_db),
) -> User:
    return UserService(db).get_or_create_from_identity(identity)


def get_current_company(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Company:
    """Fails closed: no company means the user has not finished onboarding.

    Every company-scoped endpoint should depend on this rather than reading
    `user.company_id` directly, so a missing company is always a 404, never
    a silent None used to build a query.
    """
    if user.company_id is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No company associated with this user yet. Create one first.",
        )

    company = CompanyService(db).repository.get_by_id(user.company_id)
    if company is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")
    return company


def get_email_service(sender: EmailSender = Depends(get_email_sender)) -> EmailService:
    return EmailService(sender)
