import uuid

from sqlalchemy.orm import Session

from app.models.company import Company


class CompanyRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, company_id: uuid.UUID) -> Company | None:
        return self.db.get(Company, company_id)

    def create(self, *, name: str, country: str, owner_user_id: uuid.UUID) -> Company:
        company = Company(name=name, country=country.upper(), owner_user_id=owner_user_id)
        self.db.add(company)
        self.db.flush()
        return company
