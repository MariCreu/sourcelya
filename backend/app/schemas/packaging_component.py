import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.domain.enums import ComplianceStatus, PackagingType
from app.models.packaging_component import PackagingComponent
from app.services.status_calculation_service import ComponentStatusResult


class PackagingComponentCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    packaging_type: PackagingType
    material: str | None = Field(default=None, max_length=255)
    weight_grams: float | None = Field(default=None, ge=0)
    recycled_content_percentage: float | None = Field(default=None, ge=0, le=100)
    manufacturer: str | None = Field(default=None, max_length=255)
    packaging_reference: str | None = Field(default=None, max_length=255)
    country_of_manufacture: str | None = Field(default=None, min_length=2, max_length=2)
    notes: str | None = None


class PackagingComponentUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    packaging_type: PackagingType | None = None
    material: str | None = Field(default=None, max_length=255)
    weight_grams: float | None = Field(default=None, ge=0)
    recycled_content_percentage: float | None = Field(default=None, ge=0, le=100)
    manufacturer: str | None = Field(default=None, max_length=255)
    packaging_reference: str | None = Field(default=None, max_length=255)
    country_of_manufacture: str | None = Field(default=None, min_length=2, max_length=2)
    notes: str | None = None


class PackagingComponentRead(BaseModel):
    id: uuid.UUID
    product_id: uuid.UUID
    name: str
    packaging_type: str
    material: str | None
    weight_grams: float | None
    recycled_content_percentage: float | None
    manufacturer: str | None
    packaging_reference: str | None
    country_of_manufacture: str | None
    notes: str | None
    created_at: datetime

    # Computed by StatusCalculationService, never stored — see that
    # service's docstring for why there is no `status` column to read from.
    status: ComplianceStatus
    missing_fields: list[str]

    @classmethod
    def from_model(
        cls, component: PackagingComponent, result: ComponentStatusResult
    ) -> "PackagingComponentRead":
        return cls(
            id=component.id,
            product_id=component.product_id,
            name=component.name,
            packaging_type=component.packaging_type,
            material=component.material,
            weight_grams=component.weight_grams,
            recycled_content_percentage=component.recycled_content_percentage,
            manufacturer=component.manufacturer,
            packaging_reference=component.packaging_reference,
            country_of_manufacture=component.country_of_manufacture,
            notes=component.notes,
            created_at=component.created_at,
            status=result.status,
            missing_fields=list(result.missing_fields),
        )
