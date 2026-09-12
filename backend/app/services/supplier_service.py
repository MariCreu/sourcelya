import uuid

from sqlalchemy.orm import Session

from app.models.supplier import Supplier
from app.repositories.supplier_repository import SupplierRepository
from app.schemas.supplier import SupplierCreate, SupplierUpdate


class SupplierService:
    def __init__(self, db: Session):
        self.db = db
        self.repository = SupplierRepository(db)

    def create(self, company_id: uuid.UUID, payload: SupplierCreate) -> Supplier:
        supplier = Supplier(
            company_id=company_id,
            name=payload.name,
            email=payload.email,
            country=payload.country.upper() if payload.country else None,
        )
        return self.repository.add(supplier)

    def list(self, company_id: uuid.UUID) -> list[Supplier]:
        return self.repository.list(company_id)

    def get(self, company_id: uuid.UUID, supplier_id: uuid.UUID) -> Supplier | None:
        return self.repository.get(company_id, supplier_id)

    def update(
        self, company_id: uuid.UUID, supplier_id: uuid.UUID, payload: SupplierUpdate
    ) -> Supplier | None:
        supplier = self.repository.get(company_id, supplier_id)
        if supplier is None:
            return None

        if payload.name is not None:
            supplier.name = payload.name
        if payload.email is not None:
            supplier.email = payload.email
        if payload.country is not None:
            supplier.country = payload.country.upper()

        self.db.flush()
        return supplier
