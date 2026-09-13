import uuid

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.models.compliance_request import ComplianceRequest, ComplianceRequestProduct
from app.repositories.base import CompanyScopedRepository


def _with_relations(stmt):
    return stmt.options(
        selectinload(ComplianceRequest.supplier),
        selectinload(ComplianceRequest.products)
        .selectinload(ComplianceRequestProduct.product),
    )


class ComplianceRequestRepository(CompanyScopedRepository[ComplianceRequest]):
    model = ComplianceRequest

    def get(self, company_id: uuid.UUID, entity_id: uuid.UUID) -> ComplianceRequest | None:
        stmt = _with_relations(select(ComplianceRequest)).where(
            ComplianceRequest.id == entity_id, ComplianceRequest.company_id == company_id
        )
        return self.db.scalars(stmt).first()

    def list(self, company_id: uuid.UUID) -> list[ComplianceRequest]:
        stmt = _with_relations(select(ComplianceRequest)).where(
            ComplianceRequest.company_id == company_id
        )
        return list(self.db.scalars(stmt).all())

    def get_by_token_hash(self, token_hash: str) -> ComplianceRequest | None:
        """Unscoped by company: the public supplier flow only ever has the
        raw token, not a company_id — the token itself is what proves which
        request (and therefore which company) this access is for.
        """
        stmt = _with_relations(select(ComplianceRequest)).where(
            ComplianceRequest.secure_token_hash == token_hash
        )
        return self.db.scalars(stmt).first()
