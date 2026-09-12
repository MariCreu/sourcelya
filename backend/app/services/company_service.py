from sqlalchemy.orm import Session

from app.models.company import Company
from app.models.user import User
from app.repositories.company_repository import CompanyRepository


class CompanyAlreadyExistsError(Exception):
    """Raised when a user who already belongs to a company tries to onboard again."""


class CompanyService:
    def __init__(self, db: Session):
        self.db = db
        self.repository = CompanyRepository(db)

    def create_company_for_user(self, *, user: User, name: str, country: str) -> Company:
        if user.company_id is not None:
            raise CompanyAlreadyExistsError(f"User {user.id} already belongs to a company")

        company = self.repository.create(name=name, country=country, owner_user_id=user.id)
        user.company_id = company.id
        self.db.flush()
        return company
