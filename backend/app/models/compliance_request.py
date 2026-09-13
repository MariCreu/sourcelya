import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.domain.enums import RequestStatus
from app.models.base import GUID, TimestampMixin, UTCDateTime, UUIDPrimaryKeyMixin


class ComplianceRequest(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A company's request for packaging information/documentation from one
    supplier, covering one or more of that supplier's products. The first
    genuinely critical Sourcelya flow — see app/services/compliance_request_service.py
    and app/services/public_request_service.py for the two sides of it.

    `status` and `event_type`-like fields across this app are VARCHAR, not
    native Postgres enums — see app/domain/enums.py's module docstring.
    """

    __tablename__ = "compliance_requests"

    company_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("companies.id"), nullable=False, index=True
    )
    supplier_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("suppliers.id"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=RequestStatus.DRAFT.value)
    language: Mapped[str] = mapped_column(String(2), nullable=False)

    # The raw token is only ever known to the supplier (emailed once, never
    # stored — see app/core/security.py generate_secure_token/hash_token).
    # Null until the request is sent (DRAFT has no token yet).
    secure_token_hash: Mapped[str | None] = mapped_column(
        String(64), nullable=True, unique=True, index=True
    )
    token_expires_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    token_revoked_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)

    sent_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    opened_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    submitted_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)

    reminder_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_reminder_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)

    products: Mapped[list["ComplianceRequestProduct"]] = relationship(
        back_populates="request", cascade="all, delete-orphan"
    )
    supplier: Mapped["Supplier"] = relationship()  # noqa: F821


class ComplianceRequestProduct(UUIDPrimaryKeyMixin, Base):
    """Join table: which of the supplier's products a given request covers."""

    __tablename__ = "compliance_request_products"
    __table_args__ = (UniqueConstraint("request_id", "product_id", name="uq_request_product"),)

    request_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("compliance_requests.id"), nullable=False, index=True
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("products.id"), nullable=False, index=True
    )

    request: Mapped["ComplianceRequest"] = relationship(back_populates="products")
    product: Mapped["Product"] = relationship()  # noqa: F821
