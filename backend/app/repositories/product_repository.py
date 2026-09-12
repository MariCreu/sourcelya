import uuid

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.models.product import Product
from app.repositories.base import CompanyScopedRepository


class ProductRepository(CompanyScopedRepository[Product]):
    model = Product

    def get(self, company_id: uuid.UUID, entity_id: uuid.UUID) -> Product | None:
        stmt = (
            select(Product)
            .options(selectinload(Product.packaging_components))
            .where(Product.id == entity_id, Product.company_id == company_id)
        )
        return self.db.scalars(stmt).first()

    def list(self, company_id: uuid.UUID) -> list[Product]:
        stmt = (
            select(Product)
            .options(selectinload(Product.packaging_components))
            .where(Product.company_id == company_id)
        )
        return list(self.db.scalars(stmt).all())
