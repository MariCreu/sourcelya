import uuid

from sqlalchemy import Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import GUID, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import ComplianceStatus


class Product(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "products"

    company_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("companies.id"), nullable=False, index=True
    )
    supplier_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("suppliers.id"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    sku: Mapped[str | None] = mapped_column(String(100), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Denormalized cache written by StatusCalculationService — never set by
    # hand from an endpoint, and never treated as the source of truth (the
    # packaging components are).
    status: Mapped[ComplianceStatus] = mapped_column(
        Enum(ComplianceStatus, name="compliance_status"),
        nullable=False,
        default=ComplianceStatus.ORANGE,
    )

    supplier: Mapped["Supplier"] = relationship(back_populates="products")  # noqa: F821
    packaging_components: Mapped[list["PackagingComponent"]] = relationship(  # noqa: F821
        back_populates="product", cascade="all, delete-orphan"
    )
