import uuid

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.domain.enums import DocumentType, ExtractionStatus
from app.models.base import GUID, TimestampMixin, UUIDPrimaryKeyMixin


class SupplierDocument(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A file a supplier attached — today always through the public portal
    for a specific `ComplianceRequest` (FASE 4's only upload path), though
    `supplier_id`/`product_id`/`request_id` are all independently nullable
    so a later phase can attach a document without going through a request.

    No `uploaded_by_user_id`: uploads only ever come from the
    unauthenticated public portal in FASE 4, so there is no user to record
    — see `DocumentService`.

    `content_type` stores Sourcelya's own canonical MIME type for the
    validated extension (see `document_service.EXTENSION_MIME_TYPES`), not
    whatever the uploading browser happened to send — never trust a
    client-supplied Content-Type when serving the file back on download.

    The API's `uploaded_at` is served from `TimestampMixin.created_at`
    (identical meaning, this row is immutable after creation) rather than a
    second column — see the FASE 4 report's simplifications.
    """

    __tablename__ = "supplier_documents"

    company_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("companies.id"), nullable=False, index=True
    )
    supplier_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("suppliers.id"), nullable=True, index=True
    )
    product_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("products.id"), nullable=True, index=True
    )
    request_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("compliance_requests.id"), nullable=True, index=True
    )

    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    storage_path: Mapped[str] = mapped_column(String(500), nullable=False, unique=True)
    content_type: Mapped[str] = mapped_column(String(255), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    document_type: Mapped[str] = mapped_column(
        String(50), nullable=False, default=DocumentType.OTHER.value
    )
    extraction_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=ExtractionStatus.PENDING.value
    )

    request: Mapped["ComplianceRequest | None"] = relationship()  # noqa: F821
