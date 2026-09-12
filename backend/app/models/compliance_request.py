import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import GUID, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import RequestStatus


class ComplianceRequest(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "compliance_requests"

    company_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("companies.id"), nullable=False, index=True
    )
    supplier_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("suppliers.id"), nullable=False, index=True
    )
    status: Mapped[RequestStatus] = mapped_column(
        Enum(RequestStatus, name="request_status"), nullable=False, default=RequestStatus.DRAFT
    )

    # The raw token is only ever known to the supplier (it is emailed once
    # and never stored). Only its hash is persisted so a database leak does
    # not hand out valid supplier links. See core/security.py.
    secure_token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    token_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    token_revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reminder_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_reminder_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    products: Mapped[list["ComplianceRequestProduct"]] = relationship(
        back_populates="request", cascade="all, delete-orphan"
    )


class ComplianceRequestProduct(UUIDPrimaryKeyMixin, Base):
    """Join table: which products a given supplier request covers."""

    __tablename__ = "compliance_request_products"

    request_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("compliance_requests.id"), nullable=False, index=True
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("products.id"), nullable=False, index=True
    )

    request: Mapped["ComplianceRequest"] = relationship(back_populates="products")
