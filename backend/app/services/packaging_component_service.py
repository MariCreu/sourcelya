import uuid

from sqlalchemy.orm import Session

from app.models.packaging_component import PackagingComponent
from app.repositories.packaging_component_repository import PackagingComponentRepository
from app.repositories.product_repository import ProductRepository
from app.schemas.packaging_component import PackagingComponentCreate, PackagingComponentUpdate


class ProductNotFoundError(Exception):
    """Raised when a packaging component operation targets a product that
    doesn't exist, or belongs to a different company than the requester."""


class PackagingComponentService:
    def __init__(self, db: Session):
        self.db = db
        self.repository = PackagingComponentRepository(db)
        self.product_repository = ProductRepository(db)

    def _assert_product_exists(self, company_id: uuid.UUID, product_id: uuid.UUID) -> None:
        if self.product_repository.get(company_id, product_id) is None:
            raise ProductNotFoundError(f"Product {product_id} not found for this company")

    def create(
        self, company_id: uuid.UUID, product_id: uuid.UUID, payload: PackagingComponentCreate
    ) -> PackagingComponent:
        self._assert_product_exists(company_id, product_id)

        component = PackagingComponent(
            product_id=product_id,
            name=payload.name,
            packaging_type=payload.packaging_type.value,
            material=payload.material,
            weight_grams=payload.weight_grams,
            recycled_content_percentage=payload.recycled_content_percentage,
            manufacturer=payload.manufacturer,
            packaging_reference=payload.packaging_reference,
            country_of_manufacture=payload.country_of_manufacture,
            notes=payload.notes,
        )
        return self.repository.add(component)

    def list_for_product(
        self, company_id: uuid.UUID, product_id: uuid.UUID
    ) -> list[PackagingComponent]:
        self._assert_product_exists(company_id, product_id)
        return self.repository.list_for_product(company_id, product_id)

    def update(
        self,
        company_id: uuid.UUID,
        product_id: uuid.UUID,
        component_id: uuid.UUID,
        payload: PackagingComponentUpdate,
    ) -> PackagingComponent | None:
        self._assert_product_exists(company_id, product_id)
        component = self.repository.get(company_id, product_id, component_id)
        if component is None:
            return None

        if payload.name is not None:
            component.name = payload.name
        if payload.packaging_type is not None:
            component.packaging_type = payload.packaging_type.value
        if payload.material is not None:
            component.material = payload.material
        if payload.weight_grams is not None:
            component.weight_grams = payload.weight_grams
        if payload.recycled_content_percentage is not None:
            component.recycled_content_percentage = payload.recycled_content_percentage
        if payload.manufacturer is not None:
            component.manufacturer = payload.manufacturer
        if payload.packaging_reference is not None:
            component.packaging_reference = payload.packaging_reference
        if payload.country_of_manufacture is not None:
            component.country_of_manufacture = payload.country_of_manufacture
        if payload.notes is not None:
            component.notes = payload.notes

        self.db.flush()
        return component
