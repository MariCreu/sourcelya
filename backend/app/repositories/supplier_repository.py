from app.models.supplier import Supplier
from app.repositories.base import CompanyScopedRepository


class SupplierRepository(CompanyScopedRepository[Supplier]):
    model = Supplier
