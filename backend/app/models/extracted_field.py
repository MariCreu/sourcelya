import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import GUID, UUIDPrimaryKeyMixin, utcnow
from app.models.enums import ExtractedFieldEntityType


class ExtractedField(UUIDPrimaryKeyMixin, Base):
    """One AI-suggested value, with full provenance.

    We deliberately never store just "the AI says 30%": every suggestion is
    tied back to the source document, page and quoted text so a human can
    verify it before it overwrites anything. See DocumentExtractionService.
    """

    __tablename__ = "extracted_fields"

    supplier_document_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("supplier_documents.id"), nullable=False, index=True
    )
    entity_type: Mapped[ExtractedFieldEntityType] = mapped_column(
        Enum(ExtractedFieldEntityType, name="extracted_field_entity_type"), nullable=False
    )
    entity_id: Mapped[uuid.UUID] = mapped_column(GUID(), nullable=False, index=True)
    field_name: Mapped[str] = mapped_column(String(100), nullable=False)
    extracted_value: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    source_page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_text: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Never auto-applied. A human must accept it (FIELD_ACCEPTED audit
    # event) before it is written onto the real entity.
    accepted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    supplier_document: Mapped["SupplierDocument"] = relationship(  # noqa: F821
        back_populates="extracted_fields"
    )
