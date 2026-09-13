import uuid

from sqlalchemy import JSON, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import GUID, TimestampMixin, UUIDPrimaryKeyMixin


class FollowUpRound(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One "we asked the supplier for exactly these fields" event — created
    the instant a follow-up email is sent (creation and sending are the
    same atomic action here, see `FollowUpService`, so there is no separate
    `sent_at`).

    `requested_fields` is an immutable snapshot (`[{"packaging_component_id":
    ..., "field_name": ...}]`) of what `MissingInformationService` reported
    as missing/review-required/conflicting *at the moment this round was
    created* — never re-read to decide anything (the live source of truth
    for "what's still missing" is always `MissingInformationService`,
    re-computed fresh). This table exists purely for the auditable history
    the spec asks for ("solo historial auditable de qué se pidió y cuándo")
    and for the information-recovery metric — not for driving behavior.

    `available_count_before`/`missing_count_before` are stored alongside
    the snapshot rather than recomputed later, because `PackagingComponent`
    has no history: once fields are filled in, there is no way to ask
    "how many were available right before round 2" after the fact.
    """

    __tablename__ = "follow_up_rounds"

    company_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("companies.id"), nullable=False, index=True
    )
    request_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("compliance_requests.id"), nullable=False, index=True
    )
    round_number: Mapped[int] = mapped_column(Integer, nullable=False)
    requested_fields: Mapped[list] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), nullable=False
    )
    trigger: Mapped[str] = mapped_column(String(20), nullable=False)
    available_count_before: Mapped[int] = mapped_column(Integer, nullable=False)
    missing_count_before: Mapped[int] = mapped_column(Integer, nullable=False)
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("users.id"), nullable=True
    )

    request: Mapped["ComplianceRequest"] = relationship()  # noqa: F821
