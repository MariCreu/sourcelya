import uuid

from sqlalchemy import select

from app.domain.enums import FieldReviewStatus
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

    def list_pending_for_request(
        self, company_id: uuid.UUID, request_id: uuid.UUID
    ) -> list[ExtractedField]:
        """Used by `MissingInformationService` — every still-undecided
        proposal for this request, whether or not it's been auto-linked to
        a specific `PackagingComponent` yet."""
        stmt = select(ExtractedField).where(
            ExtractedField.company_id == company_id,
            ExtractedField.request_id == request_id,
            ExtractedField.review_status == FieldReviewStatus.PENDING.value,
        )
        return list(self.db.scalars(stmt).all())
