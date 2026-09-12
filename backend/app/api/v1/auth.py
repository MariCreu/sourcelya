from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.repositories.company_repository import CompanyRepository
from app.schemas.user import CurrentUserRead

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/me", response_model=CurrentUserRead)
def read_current_user(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> CurrentUserRead:
    """Returns the authenticated user and, if onboarding is complete, their company.

    `company` is null when the Supabase user has no PackProof company yet —
    the frontend uses that to route to the onboarding screen instead of the
    dashboard.
    """
    company = CompanyRepository(db).get_by_id(user.company_id) if user.company_id else None
    return CurrentUserRead(user=user, company=company)
