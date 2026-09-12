import uuid

from sqlalchemy.orm import Session

from app.models.product import Product
from app.repositories.product_repository import ProductRepository
from app.repositories.supplier_repository import SupplierRepository
from app.schemas.product import ProductCreate, ProductUpdate


class SupplierNotFoundError(Exception):
    """Raised when a product references a supplier that doesn't exist, or
    belongs to a different company than the one making the request."""


class ProductService:
    def __init__(self, db: Session):
        self.db = db
        self.repository = ProductRepository(db)
        self.supplier_repository = SupplierRepository(db)

    def _assert_supplier_belongs_to_company(
        self, company_id: uuid.UUID, supplier_id: uuid.UUID
    ) -> None:
        if self.supplier_repository.get(company_id, supplier_id) is None:
            raise SupplierNotFoundError(f"Supplier {supplier_id} not found for this company")

    def create(self, company_id: uuid.UUID, payload: ProductCreate) -> Product:
        if payload.supplier_id is not None:
            self._assert_supplier_belongs_to_company(company_id, payload.supplier_id)

        product = Product(
            company_id=company_id,
            supplier_id=payload.supplier_id,
            name=payload.name,
            sku=payload.sku,
            description=payload.description,
        )
        return self.repository.add(product)

    def list(self, company_id: uuid.UUID) -> list[Product]:
        return self.repository.list(company_id)

    def get(self, company_id: uuid.UUID, product_id: uuid.UUID) -> Product | None:
        return self.repository.get(company_id, product_id)

    def update(
        self, company_id: uuid.UUID, product_id: uuid.UUID, payload: ProductUpdate
    ) -> Product | None:
        product = self.repository.get(company_id, product_id)
        if product is None:
            return None

        if payload.supplier_id is not None:
            self._assert_supplier_belongs_to_company(company_id, payload.supplier_id)
            product.supplier_id = payload.supplier_id
        if payload.name is not None:
            product.name = payload.name
        if payload.sku is not None:
            product.sku = payload.sku
        if payload.description is not None:
            product.description = payload.description

        self.db.flush()
        return product
