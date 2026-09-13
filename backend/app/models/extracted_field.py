import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.domain.enums import FieldReviewStatus
from app.models.base import GUID, TimestampMixin, UTCDateTime, UUIDPrimaryKeyMixin


class ExtractedField(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One proposed value for one `PackagingComponent` field, produced by
    `ExtractionService` from one `SupplierDocument`. Never written by the
    extractor into `PackagingComponent` directly — see this table's whole
    reason for existing: `ExtractionService`/`ExtractedFieldService`
    module docstrings, and the FASE 5 report's "MUY IMPORTANTE: NO
    SOBRESCRIBIR" section.

    Only ever created for fields the model reported as FOUND — a NOT_FOUND
    or UNKNOWN field produces no row here at all (that absence is exactly
    what `StatusCalculationService.missing_fields` already means; a row
    with no useful value would just be noise).

    `packaging_component_id` is nullable: FASE 5 auto-resolves it only when
    the request unambiguously covers a single `PackagingComponent` (the
    common case for a first request); when a request covers several, the
    reviewer picks the target component at accept time instead of a
    heuristic guessing for them.
    """

    __tablename__ = "extracted_fields"

    company_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("companies.id"), nullable=False, index=True
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("supplier_documents.id"), nullable=False, index=True
    )
    request_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("compliance_requests.id"), nullable=False, index=True
    )
    packaging_component_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("packaging_components.id"), nullable=True, index=True
    )

    field_name: Mapped[str] = mapped_column(String(50), nullable=False)
    extracted_value: Mapped[str] = mapped_column(String(500), nullable=False)
    confidence: Mapped[str] = mapped_column(String(10), nullable=False)

    # Evidence. `quote_verified` is set by our own deterministic check
    # against text WE extracted from the document — never trust the
    # model's claim about its own citation unchecked; see
    # extraction_service.py's verification pass.
    source_page: Mapped[int | None] = mapped_column(nullable=True)
    source_quote: Mapped[str | None] = mapped_column(Text, nullable=True)
    quote_verified: Mapped[bool] = mapped_column(nullable=False, default=False)

    review_status: Mapped[str] = mapped_column(
        String(10), nullable=False, default=FieldReviewStatus.PENDING.value
    )
    reviewed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("users.id"), nullable=True
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)

    document: Mapped["SupplierDocument"] = relationship(  # noqa: F821
        back_populates="extracted_fields"
    )
