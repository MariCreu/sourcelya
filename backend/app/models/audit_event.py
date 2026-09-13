import uuid

from sqlalchemy import JSON, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import GUID, TimestampMixin, UUIDPrimaryKeyMixin


class AuditEvent(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Append-only log of things worth being able to answer "when did this
    happen and who/what triggered it" about later. `actor_user_id` is null
    for events triggered from the public supplier portal (no authenticated
    user exists there) — `entity_type`/`entity_id` is enough to trace those
    back to the request.

    No admin UI for this yet, on purpose (see product spec section 15) —
    just the table and `AuditService.record()`.
    """

    __tablename__ = "audit_events"

    company_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("companies.id"), nullable=False, index=True
    )
    event_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_id: Mapped[uuid.UUID] = mapped_column(GUID(), nullable=False, index=True)
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("users.id"), nullable=True
    )
    # Generic JSON so the fast test suite can run against SQLite; Postgres
    # still gets the indexable JSONB storage in production.
    metadata_json: Mapped[dict | None] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), nullable=True
    )
