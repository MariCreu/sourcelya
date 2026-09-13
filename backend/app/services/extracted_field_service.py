"""The only code path allowed to turn an `ExtractedField` proposal into a
real `PackagingComponent` value — always gated on an explicit human
ACCEPT, per the FASE 5 spec's "MUY IMPORTANTE: NO SOBRESCRIBIR". Nothing
in `ExtractionService` (or the extraction provider) ever touches
`PackagingComponent` directly.

Conflict rule: if the target field already has a non-empty value that
differs from the extracted one, `accept()` refuses to apply it and raises
`FieldConflictError` instead — the caller must resubmit with an explicit
`conflict_resolution` ("use_extracted" or "keep_current"). There is no
third, implicit option.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.domain.enums import AuditEventType, ExtractableFieldName, FieldReviewStatus, PackagingType
from app.models.extracted_field import ExtractedField
from app.models.packaging_component import PackagingComponent
from app.repositories.compliance_request_repository import ComplianceRequestRepository
from app.repositories.extracted_field_repository import ExtractedFieldRepository
from app.repositories.packaging_component_repository import PackagingComponentRepository
from app.services.audit_service import AuditService

_NUMERIC_FIELDS = {
    ExtractableFieldName.WEIGHT_GRAMS.value,
    ExtractableFieldName.RECYCLED_CONTENT_PERCENTAGE.value,
}


class ExtractedFieldNotFoundError(Exception):
    pass


class FieldAlreadyReviewedError(Exception):
    pass


class ComponentNotSpecifiedError(Exception):
    """No `packaging_component_id` could be auto-resolved and none was
    given in the accept payload — the reviewer must pick one explicitly."""


class ComponentNotInRequestError(Exception):
    """The chosen component doesn't belong to a product covered by this
    field's own request — never trust a component id from the caller
    without checking it against the request it's actually for."""


class InvalidExtractedValueError(Exception):
    """The extracted value can't be applied to this field (e.g. a
    non-numeric weight, or a packaging_type outside the known set)."""


class FieldConflictError(Exception):
    def __init__(self, field_name: str, current_value: str, extracted_value: str):
        self.field_name = field_name
        self.current_value = current_value
        self.extracted_value = extracted_value
        super().__init__("POSSIBLE CONFLICT")


class ExtractedFieldService:
    def __init__(self, db: Session):
        self.db = db
        self.repository = ExtractedFieldRepository(db)
        self.request_repository = ComplianceRequestRepository(db)
        self.component_repository = PackagingComponentRepository(db)
        self.audit_service = AuditService(db)

    def list_for_document(
        self, company_id: uuid.UUID, document_id: uuid.UUID
    ) -> list[ExtractedField]:
        return self.repository.list_for_document(company_id, document_id)

    def _resolve_component(
        self,
        company_id: uuid.UUID,
        field: ExtractedField,
        requested_component_id: uuid.UUID | None,
    ) -> PackagingComponent:
        component_id = field.packaging_component_id or requested_component_id
        if component_id is None:
            raise ComponentNotSpecifiedError(
                "This request has more than one packaging component — specify which one"
            )
        component = self.component_repository.get_by_id(company_id, component_id)
        if component is None:
            raise ComponentNotInRequestError(f"Component {component_id} not found")

        request = self.request_repository.get(company_id, field.request_id)
        valid_component_ids = (
            {c.id for rp in request.products for c in rp.product.packaging_components}
            if request is not None
            else set()
        )
        if component.id not in valid_component_ids:
            raise ComponentNotInRequestError(
                f"Component {component_id} does not belong to this field's request"
            )
        return component

    @staticmethod
    def _current_value(component: PackagingComponent, field_name: str) -> str | None:
        value = getattr(component, field_name)
        return None if value is None else str(value)

    @staticmethod
    def _values_conflict(field_name: str, current: str, extracted: str) -> bool:
        if field_name in _NUMERIC_FIELDS:
            try:
                return float(current) != float(extracted)
            except ValueError:
                return current.strip() != extracted.strip()
        return current.strip().casefold() != extracted.strip().casefold()

    @staticmethod
    def _apply(component: PackagingComponent, field_name: str, value: str) -> None:
        if field_name == ExtractableFieldName.PACKAGING_TYPE.value:
            valid_values = {member.value for member in PackagingType}
            if value not in valid_values:
                raise InvalidExtractedValueError(f"'{value}' is not a valid packaging_type")
            component.packaging_type = value
        elif field_name in _NUMERIC_FIELDS:
            try:
                parsed = float(value)
            except ValueError as exc:
                raise InvalidExtractedValueError(
                    f"'{value}' is not a valid number for {field_name}"
                ) from exc
            setattr(component, field_name, parsed)
        else:
            setattr(component, field_name, value)

    def accept(
        self,
        company_id: uuid.UUID,
        actor_user_id: uuid.UUID,
        field_id: uuid.UUID,
        *,
        packaging_component_id: uuid.UUID | None = None,
        conflict_resolution: str | None = None,
    ) -> ExtractedField:
        field = self.repository.get(company_id, field_id)
        if field is None:
            raise ExtractedFieldNotFoundError(f"Extracted field {field_id} not found")
        if field.review_status != FieldReviewStatus.PENDING.value:
            raise FieldAlreadyReviewedError(f"Field {field_id} has already been reviewed")

        component = self._resolve_component(company_id, field, packaging_component_id)
        current_value = self._current_value(component, field.field_name)
        has_conflict = current_value not in (None, "") and self._values_conflict(
            field.field_name, current_value, field.extracted_value
        )

        if has_conflict and conflict_resolution is None:
            raise FieldConflictError(field.field_name, current_value, field.extracted_value)

        if has_conflict and conflict_resolution == "keep_current":
            field.review_status = FieldReviewStatus.REJECTED.value
            field.reviewed_by_user_id = actor_user_id
            field.reviewed_at = datetime.now(timezone.utc)
            self.db.flush()
            self.audit_service.record(
                company_id=company_id,
                event_type=AuditEventType.EXTRACTED_FIELD_REJECTED,
                entity_type="extracted_field",
                entity_id=field.id,
                actor_user_id=actor_user_id,
                metadata={"reason": "conflict_kept_current"},
            )
            return field

        self._apply(component, field.field_name, field.extracted_value)
        field.packaging_component_id = component.id
        field.review_status = FieldReviewStatus.ACCEPTED.value
        field.reviewed_by_user_id = actor_user_id
        field.reviewed_at = datetime.now(timezone.utc)
        self.db.flush()
        self.audit_service.record(
            company_id=company_id,
            event_type=AuditEventType.EXTRACTED_FIELD_ACCEPTED,
            entity_type="extracted_field",
            entity_id=field.id,
            actor_user_id=actor_user_id,
            metadata={"field_name": field.field_name, "value": field.extracted_value},
        )
        return field

    def reject(
        self, company_id: uuid.UUID, actor_user_id: uuid.UUID, field_id: uuid.UUID
    ) -> ExtractedField:
        field = self.repository.get(company_id, field_id)
        if field is None:
            raise ExtractedFieldNotFoundError(f"Extracted field {field_id} not found")
        if field.review_status != FieldReviewStatus.PENDING.value:
            raise FieldAlreadyReviewedError(f"Field {field_id} has already been reviewed")

        field.review_status = FieldReviewStatus.REJECTED.value
        field.reviewed_by_user_id = actor_user_id
        field.reviewed_at = datetime.now(timezone.utc)
        self.db.flush()
        self.audit_service.record(
            company_id=company_id,
            event_type=AuditEventType.EXTRACTED_FIELD_REJECTED,
            entity_type="extracted_field",
            entity_id=field.id,
            actor_user_id=actor_user_id,
        )
        return field
