import uuid
from datetime import datetime

from pydantic import BaseModel

from app.models.follow_up_round import FollowUpRound
from app.services.follow_up_service import RecoveryStats
from app.services.missing_information_service import (
    ComponentInformation,
    RequestInformationSummary,
)


class FieldInformationRead(BaseModel):
    field_name: str
    state: str
    current_value: str | None
    extracted_value: str | None
    pending_field_id: uuid.UUID | None


class ComponentInformationRead(BaseModel):
    component_id: uuid.UUID
    component_name: str
    fields: list[FieldInformationRead]

    @classmethod
    def from_model(cls, component: ComponentInformation) -> "ComponentInformationRead":
        return cls(
            component_id=component.component_id,
            component_name=component.component_name,
            fields=[
                FieldInformationRead(
                    field_name=f.field_name,
                    state=f.state.value,
                    current_value=f.current_value,
                    extracted_value=f.extracted_value,
                    pending_field_id=f.pending_field_id,
                )
                for f in component.fields
            ],
        )


class RequestInformationSummaryRead(BaseModel):
    status: str
    total_requested: int
    available_count: int
    missing_count: int
    review_required_count: int
    conflict_count: int
    unresolved_pending_count: int
    components: list[ComponentInformationRead]

    @classmethod
    def from_summary(cls, summary: RequestInformationSummary) -> "RequestInformationSummaryRead":
        return cls(
            status=summary.status.value,
            total_requested=summary.total_requested,
            available_count=summary.available_count,
            missing_count=summary.missing_count,
            review_required_count=summary.review_required_count,
            conflict_count=summary.conflict_count,
            unresolved_pending_count=summary.unresolved_pending_count,
            components=[ComponentInformationRead.from_model(c) for c in summary.components],
        )


class FollowUpRoundRead(BaseModel):
    id: uuid.UUID
    round_number: int
    requested_fields: list[dict]
    trigger: str
    available_count_before: int
    missing_count_before: int
    created_at: datetime

    @classmethod
    def from_model(cls, round_: FollowUpRound) -> "FollowUpRoundRead":
        return cls(
            id=round_.id,
            round_number=round_.round_number,
            requested_fields=round_.requested_fields,
            trigger=round_.trigger,
            available_count_before=round_.available_count_before,
            missing_count_before=round_.missing_count_before,
            created_at=round_.created_at,
        )


class RecoveryStatsRead(BaseModel):
    total_requested: int
    available_after_first_submission: int | None
    available_now: int
    follow_up_recovered: int | None
    recovery_rate: float | None

    @classmethod
    def from_stats(cls, stats: RecoveryStats) -> "RecoveryStatsRead":
        return cls(
            total_requested=stats.total_requested,
            available_after_first_submission=stats.available_after_first_submission,
            available_now=stats.available_now,
            follow_up_recovered=stats.follow_up_recovered,
            recovery_rate=stats.recovery_rate,
        )


class AutomaticFollowUpToggle(BaseModel):
    enabled: bool
