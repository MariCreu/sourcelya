import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import GUID, UUIDPrimaryKeyMixin, utcnow
from app.models.enums import DocumentType, ExtractionStatus


class SupplierDocument(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "supplier_documents"

    request_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("compliance_requests.id"), nullable=False, index=True
    )
    supplier_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("suppliers.id"), nullable=False, index=True
    )
    product_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("products.id"), nullable=True, index=True
    )

    filename: Mapped[str] = mapped_column(String(500), nullable=False)
    storage_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    document_type: Mapped[DocumentType] = mapped_column(
        Enum(DocumentType, name="document_type"), nullable=False, default=DocumentType.OTHER
    )
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    extraction_status: Mapped[ExtractionStatus] = mapped_column(
        Enum(ExtractionStatus, name="extraction_status"),
        nullable=False,
        default=ExtractionStatus.PENDING,
    )

    extracted_fields: Mapped[list["ExtractedField"]] = relationship(  # noqa: F821
        back_populates="supplier_document", cascade="all, delete-orphan"
    )
