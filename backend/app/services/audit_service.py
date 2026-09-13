import uuid

from sqlalchemy.orm import Session

from app.domain.enums import AuditEventType
from app.models.audit_event import AuditEvent


class AuditService:
    """Thin wrapper around inserting an AuditEvent row — see that model's
    docstring for what this is (and isn't) for.
    """

    def __init__(self, db: Session):
        self.db = db

    def record(
        self,
        *,
        company_id: uuid.UUID,
        event_type: AuditEventType,
        entity_type: str,
        entity_id: uuid.UUID,
        actor_user_id: uuid.UUID | None = None,
        metadata: dict | None = None,
    ) -> AuditEvent:
        event = AuditEvent(
            company_id=company_id,
            event_type=event_type.value,
            entity_type=entity_type,
            entity_id=entity_id,
            actor_user_id=actor_user_id,
            metadata_json=metadata,
        )
        self.db.add(event)
        self.db.flush()
        return event
