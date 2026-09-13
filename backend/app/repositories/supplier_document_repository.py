import uuid

from sqlalchemy import select

from app.models.supplier_document import SupplierDocument
from app.repositories.base import CompanyScopedRepository


class SupplierDocumentRepository(CompanyScopedRepository[SupplierDocument]):
    model = SupplierDocument

    def list_for_request(self, request_id: uuid.UUID) -> list[SupplierDocument]:
        """Unscoped by company on purpose: the public portal only ever has a
        `request_id` (resolved from the token, itself already trustworthy —
        see `PublicRequestService._resolve`), never a `company_id`.
        """
        stmt = select(SupplierDocument).where(SupplierDocument.request_id == request_id)
        return list(self.db.scalars(stmt).all())

    def get_for_request(
        self, request_id: uuid.UUID, document_id: uuid.UUID
    ) -> SupplierDocument | None:
        stmt = select(SupplierDocument).where(
            SupplierDocument.id == document_id, SupplierDocument.request_id == request_id
        )
        return self.db.scalars(stmt).first()
