import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.security import hash_token
from app.domain.enums import AuditEventType, RequestStatus
from app.models.compliance_request import ComplianceRequest
from app.repositories.compliance_request_repository import ComplianceRequestRepository
from app.schemas.public_request import PublicSaveRequestPayload
from app.services.audit_service import AuditService

_TERMINAL_STATUSES = {RequestStatus.SUBMITTED.value, RequestStatus.COMPLETED.value}


class InvalidTokenError(Exception):
    """No request matches this token at all."""


class TokenExpiredError(Exception):
    pass


class TokenRevokedError(Exception):
    pass


class ComponentNotInRequestError(Exception):
    """A component id in the save payload doesn't belong to any product
    attached to this request — the cross-request/cross-company/cross-supplier
    leak this whole service exists to prevent."""


class RequestAlreadySubmittedError(Exception):
    pass


class PublicRequestService:
    """Everything reachable only by knowing the raw token — no company_id,
    no auth. Every method re-derives the request from the token hash itself,
    so there is no path that lets a caller pass an arbitrary request/company
    id.
    """

    def __init__(self, db: Session):
        self.db = db
        self.repository = ComplianceRequestRepository(db)
        self.audit_service = AuditService(db)

    def _resolve(self, raw_token: str) -> ComplianceRequest:
        request = self.repository.get_by_token_hash(hash_token(raw_token))
        if request is None:
            raise InvalidTokenError("No request matches this token")
        if request.token_revoked_at is not None:
            raise TokenRevokedError("This link has been revoked")
        if request.token_expires_at is not None and datetime.now(timezone.utc) > request.token_expires_at:
            raise TokenExpiredError("This link has expired")
        return request

    def _all_components(self, request: ComplianceRequest) -> dict[uuid.UUID, object]:
        return {
            component.id: component
            for request_product in request.products
            for component in request_product.product.packaging_components
        }

    def resolve_token(self, raw_token: str) -> ComplianceRequest:
        """Public entry point for other token-scoped flows (document
        upload/delete) that need the same invalid/expired/revoked checks
        without going through `get_by_token`'s SENT->OPENED side effect.
        """
        return self._resolve(raw_token)

    def get_by_token(self, raw_token: str) -> ComplianceRequest:
        request = self._resolve(raw_token)
        if request.status == RequestStatus.SENT.value:
            request.status = RequestStatus.OPENED.value
            request.opened_at = datetime.now(timezone.utc)
            self.db.flush()
            self.audit_service.record(
                company_id=request.company_id,
                event_type=AuditEventType.REQUEST_OPENED,
                entity_type="compliance_request",
                entity_id=request.id,
            )
        return request

    def save_progress(
        self, raw_token: str, payload: PublicSaveRequestPayload
    ) -> ComplianceRequest:
        request = self._resolve(raw_token)
        if request.status in _TERMINAL_STATUSES:
            raise RequestAlreadySubmittedError("This request has already been submitted")

        components_by_id = self._all_components(request)
        for item in payload.components:
            if item.id not in components_by_id:
                raise ComponentNotInRequestError(
                    f"Component {item.id} does not belong to this request"
                )

        for item in payload.components:
            component = components_by_id[item.id]
            if item.material is not None:
                component.material = item.material
            if item.weight_grams is not None:
                component.weight_grams = item.weight_grams
            if item.recycled_content_percentage is not None:
                component.recycled_content_percentage = item.recycled_content_percentage
            if item.packaging_reference is not None:
                component.packaging_reference = item.packaging_reference
            if item.notes is not None:
                component.notes = item.notes

        if request.status == RequestStatus.SENT.value:
            request.opened_at = request.opened_at or datetime.now(timezone.utc)
        request.status = RequestStatus.IN_PROGRESS.value
        self.db.flush()
        self.audit_service.record(
            company_id=request.company_id,
            event_type=AuditEventType.REQUEST_SAVED,
            entity_type="compliance_request",
            entity_id=request.id,
        )
        return request

    def submit(self, raw_token: str) -> ComplianceRequest:
        request = self._resolve(raw_token)
        if request.status in _TERMINAL_STATUSES:
            # Idempotent: a repeated submit (e.g. a double click, or a
            # retried request) doesn't error, it just confirms.
            return request

        request.status = RequestStatus.SUBMITTED.value
        request.submitted_at = datetime.now(timezone.utc)
        self.db.flush()
        self.audit_service.record(
            company_id=request.company_id,
            event_type=AuditEventType.REQUEST_SUBMITTED,
            entity_type="compliance_request",
            entity_id=request.id,
        )
        return request
