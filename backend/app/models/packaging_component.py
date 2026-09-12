import uuid

from sqlalchemy import Enum, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import GUID, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import ComplianceStatus, PackagingType


class PackagingComponent(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "packaging_components"

    product_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("products.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    packaging_type: Mapped[PackagingType] = mapped_column(
        Enum(PackagingType, name="packaging_type"), nullable=False
    )

    # MVP field set — see product spec section 7. Deliberately no legal
    # fields (recyclability claims, EPR registration numbers, ...) yet.
    material: Mapped[str | None] = mapped_column(String(255), nullable=True)
    weight_grams: Mapped[float | None] = mapped_column(Float, nullable=True)
    recycled_content_percentage: Mapped[float | None] = mapped_column(Float, nullable=True)
    manufacturer: Mapped[str | None] = mapped_column(String(255), nullable=True)
    packaging_reference: Mapped[str | None] = mapped_column(String(255), nullable=True)
    country_of_manufacture: Mapped[str | None] = mapped_column(String(2), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    status: Mapped[ComplianceStatus] = mapped_column(
        Enum(ComplianceStatus, name="compliance_status"),
        nullable=False,
        default=ComplianceStatus.ORANGE,
    )

    product: Mapped["Product"] = relationship(back_populates="packaging_components")  # noqa: F821
