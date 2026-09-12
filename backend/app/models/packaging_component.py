import uuid

from sqlalchemy import Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import GUID, TimestampMixin, UUIDPrimaryKeyMixin


class PackagingComponent(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """No `status` column: see Product's docstring — status is always
    computed by StatusCalculationService, never cached.

    `packaging_type` is a plain VARCHAR, validated against
    `app.domain.enums.PackagingType` in the application layer rather than a
    native Postgres enum — see that module's docstring for why.
    """

    __tablename__ = "packaging_components"

    product_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("products.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    packaging_type: Mapped[str] = mapped_column(String(50), nullable=False)

    # MVP field set — see product spec section 7. Deliberately no legal
    # fields (recyclability claims, EPR registration numbers, ...) yet.
    material: Mapped[str | None] = mapped_column(String(255), nullable=True)
    weight_grams: Mapped[float | None] = mapped_column(Float, nullable=True)
    recycled_content_percentage: Mapped[float | None] = mapped_column(Float, nullable=True)
    manufacturer: Mapped[str | None] = mapped_column(String(255), nullable=True)
    packaging_reference: Mapped[str | None] = mapped_column(String(255), nullable=True)
    country_of_manufacture: Mapped[str | None] = mapped_column(String(2), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    product: Mapped["Product"] = relationship(back_populates="packaging_components")  # noqa: F821
