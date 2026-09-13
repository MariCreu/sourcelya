import uuid

from sqlalchemy import select

from app.models.extracted_field import ExtractedField
from app.repositories.base import CompanyScopedRepository


class ExtractedFieldRepository(CompanyScopedRepository[ExtractedField]):
    model = ExtractedField

    def list_for_document(
        self, company_id: uuid.UUID, document_id: uuid.UUID
    ) -> list[ExtractedField]:
        stmt = select(ExtractedField).where(
            ExtractedField.company_id == company_id, ExtractedField.document_id == document_id
        )
        return list(self.db.scalars(stmt).all())
