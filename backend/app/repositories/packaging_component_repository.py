import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.packaging_component import PackagingComponent
from app.models.product import Product


class PackagingComponentRepository:
    """Not a `CompanyScopedRepository`: `PackagingComponent` has no
    `company_id` of its own, only `product_id`. Every query here joins
    through `Product` to enforce the same tenant isolation.
    """

    def __init__(self, db: Session):
        self.db = db

    def _scoped_query(self, company_id: uuid.UUID, product_id: uuid.UUID):
        return select(PackagingComponent).join(Product).where(
            PackagingComponent.product_id == product_id,
            Product.company_id == company_id,
        )

    def list_for_product(
        self, company_id: uuid.UUID, product_id: uuid.UUID
    ) -> list[PackagingComponent]:
        return list(self.db.scalars(self._scoped_query(company_id, product_id)).all())

    def get(
        self, company_id: uuid.UUID, product_id: uuid.UUID, component_id: uuid.UUID
    ) -> PackagingComponent | None:
        stmt = self._scoped_query(company_id, product_id).where(
            PackagingComponent.id == component_id
        )
        return self.db.scalars(stmt).first()

    def add(self, component: PackagingComponent) -> PackagingComponent:
        self.db.add(component)
        self.db.flush()
        return component

    def get_by_id(
        self, company_id: uuid.UUID, component_id: uuid.UUID
    ) -> PackagingComponent | None:
        """Company-scoped, but not `product_id`-scoped — used by the FASE 5
        extracted-field review flow, which only ever has a
        `packaging_component_id`, not the product it hangs off of."""
        stmt = select(PackagingComponent).join(Product).where(
            PackagingComponent.id == component_id, Product.company_id == company_id
        )
        return self.db.scalars(stmt).first()
