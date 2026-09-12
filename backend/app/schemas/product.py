import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.domain.enums import ComplianceStatus
from app.models.product import Product
from app.schemas.packaging_component import PackagingComponentRead


class ProductCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    sku: str | None = Field(default=None, max_length=100)
    description: str | None = None
    supplier_id: uuid.UUID | None = None


class ProductUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    sku: str | None = Field(default=None, max_length=100)
    description: str | None = None
    supplier_id: uuid.UUID | None = None


class ProductRead(BaseModel):
    id: uuid.UUID
    company_id: uuid.UUID
    supplier_id: uuid.UUID | None
    name: str
    sku: str | None
    description: str | None
    created_at: datetime

    # Computed by StatusCalculationService, never stored.
    status: ComplianceStatus
    packaging_component_count: int

    @classmethod
    def from_model(cls, product: Product, status: ComplianceStatus) -> "ProductRead":
        return cls(
            id=product.id,
            company_id=product.company_id,
            supplier_id=product.supplier_id,
            name=product.name,
            sku=product.sku,
            description=product.description,
            created_at=product.created_at,
            status=status,
            packaging_component_count=len(product.packaging_components),
        )


class ProductDetailRead(ProductRead):
    packaging_components: list[PackagingComponentRead]

    @classmethod
    def from_model_with_components(
        cls,
        product: Product,
        status: ComplianceStatus,
        packaging_components: list[PackagingComponentRead],
    ) -> "ProductDetailRead":
        base = ProductRead.from_model(product, status)
        return cls(**base.model_dump(), packaging_components=packaging_components)
