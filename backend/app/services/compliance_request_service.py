import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.security import generate_secure_token, hash_token
from app.domain.enums import AuditEventType, RequestStatus
from app.integrations.email.templates import ComplianceRequestEmailContext
from app.models.company import Company
from app.models.compliance_request import ComplianceRequest, ComplianceRequestProduct
from app.repositories.compliance_request_repository import ComplianceRequestRepository
from app.repositories.product_repository import ProductRepository
from app.repositories.supplier_repository import SupplierRepository
from app.schemas.compliance_request import ComplianceRequestCreate
from app.services.audit_service import AuditService
from app.services.email_service import EmailService


class SupplierNotFoundError(Exception):
    """Supplier doesn't exist, or belongs to a different company."""


class ProductNotInSupplierError(Exception):
    """A product either doesn't belong to this company, or isn't one of
    the chosen supplier's products."""


class RequestNotDraftError(Exception):
    """Raised by send() when the request has already been sent — sending
    the same request twice would silently mint a second live token, which
    is exactly the "solicitud enviada dos veces" case the spec calls out.
    """


class RequestTokenNotActiveError(Exception):
    """Raised by resend()/revoke() when there is no live token to act on
    (never sent, or already revoked)."""


class ComplianceRequestService:
    def __init__(self, db: Session, email_service: EmailService, settings: Settings | None = None):
        self.db = db
        self.repository = ComplianceRequestRepository(db)
        self.supplier_repository = SupplierRepository(db)
        self.product_repository = ProductRepository(db)
        self.audit_service = AuditService(db)
        self.email_service = email_service
        self.settings = settings or get_settings()

    def _assert_products_belong_to_supplier(
        self, company_id: uuid.UUID, supplier_id: uuid.UUID, product_ids: list[uuid.UUID]
    ) -> None:
        for product_id in product_ids:
            product = self.product_repository.get(company_id, product_id)
            if product is None or product.supplier_id != supplier_id:
                raise ProductNotInSupplierError(
                    f"Product {product_id} does not belong to supplier {supplier_id} "
                    "of this company"
                )

    def create(
        self, company_id: uuid.UUID, actor_user_id: uuid.UUID, payload: ComplianceRequestCreate
    ) -> ComplianceRequest:
        if self.supplier_repository.get(company_id, payload.supplier_id) is None:
            raise SupplierNotFoundError(f"Supplier {payload.supplier_id} not found for this company")
        self._assert_products_belong_to_supplier(company_id, payload.supplier_id, payload.product_ids)

        request = ComplianceRequest(
            company_id=company_id,
            supplier_id=payload.supplier_id,
            status=RequestStatus.DRAFT.value,
            language=payload.language.value,
        )
        request.products = [
            ComplianceRequestProduct(product_id=product_id) for product_id in payload.product_ids
        ]
        self.repository.add(request)
        self.audit_service.record(
            company_id=company_id,
            event_type=AuditEventType.REQUEST_CREATED,
            entity_type="compliance_request",
            entity_id=request.id,
            actor_user_id=actor_user_id,
        )
        return self.repository.get(company_id, request.id)

    def list(self, company_id: uuid.UUID) -> list[ComplianceRequest]:
        return self.repository.list(company_id)

    def get(self, company_id: uuid.UUID, request_id: uuid.UUID) -> ComplianceRequest | None:
        return self.repository.get(company_id, request_id)

    def _build_request_url(self, raw_token: str) -> str:
        return f"{self.settings.frontend_base_url}/request/{raw_token}"

    def _issue_token_and_email(self, company: Company, request: ComplianceRequest) -> str:
        raw_token = generate_secure_token()
        request.secure_token_hash = hash_token(raw_token)
        request.token_expires_at = datetime.now(timezone.utc) + timedelta(
            days=self.settings.supplier_token_default_expiry_days
        )
        request.token_revoked_at = None

        request_url = self._build_request_url(raw_token)
        self.email_service.send_compliance_request(
            ComplianceRequestEmailContext(
                supplier_email=request.supplier.email,
                supplier_name=request.supplier.name,
                company_name=company.name,
                number_of_products=len(request.products),
                request_url=request_url,
                language=request.language,
            )
        )
        return request_url

    def send(
        self, company: Company, actor_user_id: uuid.UUID, request_id: uuid.UUID
    ) -> tuple[ComplianceRequest, str] | None:
        request = self.repository.get(company.id, request_id)
        if request is None:
            return None
        if request.status != RequestStatus.DRAFT.value:
            raise RequestNotDraftError(f"Request {request_id} has already been sent")

        request_url = self._issue_token_and_email(company, request)
        request.status = RequestStatus.SENT.value
        request.sent_at = datetime.now(timezone.utc)
        self.db.flush()

        self.audit_service.record(
            company_id=company.id,
            event_type=AuditEventType.REQUEST_SENT,
            entity_type="compliance_request",
            entity_id=request.id,
            actor_user_id=actor_user_id,
        )
        return request, request_url

    def revoke(
        self, company_id: uuid.UUID, actor_user_id: uuid.UUID, request_id: uuid.UUID
    ) -> ComplianceRequest | None:
        request = self.repository.get(company_id, request_id)
        if request is None:
            return None
        if request.secure_token_hash is None or request.token_revoked_at is not None:
            raise RequestTokenNotActiveError(f"Request {request_id} has no active token to revoke")

        request.token_revoked_at = datetime.now(timezone.utc)
        self.db.flush()
        self.audit_service.record(
            company_id=company_id,
            event_type=AuditEventType.TOKEN_REVOKED,
            entity_type="compliance_request",
            entity_id=request.id,
            actor_user_id=actor_user_id,
        )
        return request

    def resend(
        self, company: Company, actor_user_id: uuid.UUID, request_id: uuid.UUID
    ) -> tuple[ComplianceRequest, str] | None:
        """Re-sending mints a brand-new token (the old raw token was never
        retrievable to resend as-is — only its hash is stored) and emails it
        again, which as a side effect invalidates the previous link. This is
        a deliberate simplification: see the FASE 3 report's "simplification
        decisions" section.
        """
        request = self.repository.get(company.id, request_id)
        if request is None:
            return None
        if request.status not in (
            RequestStatus.SENT.value,
            RequestStatus.OPENED.value,
            RequestStatus.IN_PROGRESS.value,
        ):
            raise RequestTokenNotActiveError(
                f"Request {request_id} is not in a state that can be resent"
            )

        request_url = self._issue_token_and_email(company, request)
        self.db.flush()
        self.audit_service.record(
            company_id=company.id,
            event_type=AuditEventType.EMAIL_RESENT,
            entity_type="compliance_request",
            entity_id=request.id,
            actor_user_id=actor_user_id,
        )
        return request, request_url
