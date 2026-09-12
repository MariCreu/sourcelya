import uuid

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import GUID, TimestampMixin, UUIDPrimaryKeyMixin


class Product(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """No `status` column on purpose: compliance status is computed on the
    fly by StatusCalculationService from this product's packaging
    components, not cached here. See that service's docstring for why.
    """

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

    supplier: Mapped["Supplier"] = relationship(back_populates="products")  # noqa: F821
    packaging_components: Mapped[list["PackagingComponent"]] = relationship(  # noqa: F821
        back_populates="product", cascade="all, delete-orphan"
    )
