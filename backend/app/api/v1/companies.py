from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_company, get_current_user, get_db
from app.models.company import Company
from app.models.user import User
from app.schemas.company import CompanyCreate, CompanyRead
from app.services.company_service import CompanyAlreadyExistsError, CompanyService

router = APIRouter(prefix="/companies", tags=["companies"])


@router.post("", response_model=CompanyRead, status_code=status.HTTP_201_CREATED)
def create_company(
    payload: CompanyCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Company:
    try:
        return CompanyService(db).create_company_for_user(
            user=user, name=payload.name, country=payload.country
        )
    except CompanyAlreadyExistsError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.get("/me", response_model=CompanyRead)
def read_my_company(company: Company = Depends(get_current_company)) -> Company:
    return company
