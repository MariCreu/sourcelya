import uuid
from typing import Generic, TypeVar

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import Base

ModelType = TypeVar("ModelType", bound=Base)


class CompanyScopedRepository(Generic[ModelType]):
    """Base repository that makes cross-tenant leaks structurally hard.

    Every repository for a company-owned entity (Supplier, Product, ...)
    should extend this instead of querying `db` directly in a service, so
    the `company_id` filter can never be forgotten by accident.
    """

    model: type[ModelType]

    def __init__(self, db: Session):
        self.db = db

    def get(self, company_id: uuid.UUID, entity_id: uuid.UUID) -> ModelType | None:
        stmt = select(self.model).where(
            self.model.id == entity_id, self.model.company_id == company_id
        )
        return self.db.scalars(stmt).first()

    def list(self, company_id: uuid.UUID) -> list[ModelType]:
        stmt = select(self.model).where(self.model.company_id == company_id)
        return list(self.db.scalars(stmt).all())

    def add(self, entity: ModelType) -> ModelType:
        self.db.add(entity)
        self.db.flush()
        return entity
