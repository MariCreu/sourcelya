"""Deterministic "what's still missing" engine — FASE 6.

Never uses an LLM. `ExtractionService` (FASE 5) is the only place AI ever
runs, and its job stops at proposing evidenced field values; whether a
request is complete is a pure function of already-structured data:
`ComplianceRequest` -> its products' `PackagingComponent`s -> their current
field values -> any still-`PENDING` `ExtractedField` rows for them.

The requested-field set is fixed and reused from FASE 5's
`ExtractableFieldName` (packaging_type, material, weight_grams,
recycled_content_percentage, packaging_reference) — the same five fields
`ExtractionService` already proposes values for. There is deliberately no
"requested field" table: what Sourcelya asks a supplier for, in the MVP, is
always this fixed set for every packaging component the request covers.

Per (component, field_name), exactly one of `FieldInformationState`:

- `CONFLICT` — a PENDING `ExtractedField` exists whose value differs from
  the component's current (non-empty) value. Mirrors the exact conflict
  rule `ExtractedFieldService.accept()` already enforces, computed without
  mutating anything (so it can be shown before a human ever clicks Accept).
- `REVIEW_REQUIRED` — a PENDING `ExtractedField` exists and the component
  has no current value it would conflict with (or the same value).
- `AVAILABLE` — the component already has a non-empty value and no PENDING
  proposal is at odds with it.
- `MISSING` — no value, no pending proposal.
- `NOT_APPLICABLE` — reserved, never produced (see the enum's docstring).

A `PENDING` `ExtractedField` with no resolved `packaging_component_id`
(the FASE 5 multi-component ambiguity case — see `ExtractionService.
_unambiguous_component_id`) cannot be attributed to any specific field
here, so it is surfaced separately (`unresolved_pending_count`) and always
blocks `InformationStatus.COMPLETE` — better an honest "something needs
your attention" than silently ignoring it.
"""

import uuid
from dataclasses import dataclass, field

from app.domain.enums import ExtractableFieldName, FieldInformationState, InformationStatus
from app.models.compliance_request import ComplianceRequest
from app.models.extracted_field import ExtractedField
from app.models.packaging_component import PackagingComponent
from app.repositories.extracted_field_repository import ExtractedFieldRepository

REQUESTED_FIELDS: tuple[str, ...] = tuple(member.value for member in ExtractableFieldName)


@dataclass(frozen=True)
class FieldInformation:
    field_name: str
    state: FieldInformationState
    current_value: str | None = None
    extracted_value: str | None = None
    pending_field_id: uuid.UUID | None = None


@dataclass(frozen=True)
class ComponentInformation:
    component_id: uuid.UUID
    component_name: str
    fields: tuple[FieldInformation, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class RequestInformationSummary:
    status: InformationStatus
    total_requested: int
    available_count: int
    missing_count: int
    review_required_count: int
    conflict_count: int
    unresolved_pending_count: int
    components: tuple[ComponentInformation, ...] = field(default_factory=tuple)

    @property
    def missing_field_refs(self) -> list[dict]:
        """`[{packaging_component_id, field_name}]` for every field not yet
        AVAILABLE — exactly the shape `FollowUpRound.requested_fields`
        snapshots, and what a follow-up email lists."""
        return [
            {"packaging_component_id": str(c.component_id), "field_name": f.field_name}
            for c in self.components
            for f in c.fields
            if f.state != FieldInformationState.AVAILABLE
        ]


def _current_value(component: PackagingComponent, field_name: str) -> str | None:
    value = getattr(component, field_name)
    if value in (None, ""):
        return None
    return str(value)


def _values_differ(field_name: str, current: str, extracted: str) -> bool:
    if field_name in (
        ExtractableFieldName.WEIGHT_GRAMS.value,
        ExtractableFieldName.RECYCLED_CONTENT_PERCENTAGE.value,
    ):
        try:
            return float(current) != float(extracted)
        except ValueError:
            return current.strip() != extracted.strip()
    return current.strip().casefold() != extracted.strip().casefold()


class MissingInformationService:
    def __init__(self, db):
        self.db = db
        self.extracted_field_repository = ExtractedFieldRepository(db)

    def _components_for(self, request: ComplianceRequest) -> list[PackagingComponent]:
        return [
            component
            for request_product in request.products
            for component in request_product.product.packaging_components
        ]

    def summarize(self, company_id: uuid.UUID, request: ComplianceRequest) -> RequestInformationSummary:
        components = self._components_for(request)
        pending_fields = self.extracted_field_repository.list_pending_for_request(
            company_id, request.id
        )
        pending_by_component_field: dict[tuple[uuid.UUID, str], list[ExtractedField]] = {}
        unresolved_pending_count = 0
        for pending in pending_fields:
            if pending.packaging_component_id is None:
                unresolved_pending_count += 1
                continue
            key = (pending.packaging_component_id, pending.field_name)
            pending_by_component_field.setdefault(key, []).append(pending)

        component_summaries: list[ComponentInformation] = []
        available_count = missing_count = review_required_count = conflict_count = 0

        for component in components:
            fields_info: list[FieldInformation] = []
            for field_name in REQUESTED_FIELDS:
                current = _current_value(component, field_name)
                pending_for_field = pending_by_component_field.get((component.id, field_name), [])

                conflicting = next(
                    (
                        p
                        for p in pending_for_field
                        if current is not None and _values_differ(field_name, current, p.extracted_value)
                    ),
                    None,
                )
                if conflicting is not None:
                    state = FieldInformationState.CONFLICT
                    conflict_count += 1
                    info = FieldInformation(
                        field_name=field_name,
                        state=state,
                        current_value=current,
                        extracted_value=conflicting.extracted_value,
                        pending_field_id=conflicting.id,
                    )
                elif pending_for_field:
                    state = FieldInformationState.REVIEW_REQUIRED
                    review_required_count += 1
                    info = FieldInformation(
                        field_name=field_name,
                        state=state,
                        current_value=current,
                        extracted_value=pending_for_field[0].extracted_value,
                        pending_field_id=pending_for_field[0].id,
                    )
                elif current is not None:
                    state = FieldInformationState.AVAILABLE
                    available_count += 1
                    info = FieldInformation(field_name=field_name, state=state, current_value=current)
                else:
                    state = FieldInformationState.MISSING
                    missing_count += 1
                    info = FieldInformation(field_name=field_name, state=state)

                fields_info.append(info)

            component_summaries.append(
                ComponentInformation(
                    component_id=component.id,
                    component_name=component.name,
                    fields=tuple(fields_info),
                )
            )

        if conflict_count > 0:
            status = InformationStatus.CONFLICT
        elif review_required_count > 0 or unresolved_pending_count > 0:
            status = InformationStatus.REVIEW_REQUIRED
        elif missing_count > 0:
            status = InformationStatus.MISSING_INFORMATION
        else:
            status = InformationStatus.COMPLETE

        return RequestInformationSummary(
            status=status,
            total_requested=len(components) * len(REQUESTED_FIELDS),
            available_count=available_count,
            missing_count=missing_count,
            review_required_count=review_required_count,
            conflict_count=conflict_count,
            unresolved_pending_count=unresolved_pending_count,
            components=tuple(component_summaries),
        )
