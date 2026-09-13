import uuid
from datetime import datetime, timezone

from sqlalchemy import CHAR, DateTime, TypeDecorator
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class UTCDateTime(TypeDecorator):
    """Timezone-aware `DateTime` that stays aware on SQLite too.

    Postgres' `DateTime(timezone=True)` round-trips an aware datetime as-is.
    SQLite has no real timezone-aware storage: it accepts the value but
    hands back a naive `datetime` on the next read (e.g. a later request's
    session `SELECT`-ing a row inserted in a previous one), which then
    blows up the moment application code compares it against
    `datetime.now(timezone.utc)` (see PublicRequestService's token-expiry
    check). Every column that is ever compared against "now" — anything
    token-lifetime related — should use this instead of a bare
    `DateTime(timezone=True)`.
    """

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_result_value(self, value, dialect):
        if value is not None and value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value


class GUID(TypeDecorator):
    """Platform-independent UUID column.

    Uses Postgres' native UUID type in production; falls back to a plain
    CHAR(36) elsewhere so the same models work against SQLite in tests.
    Plain `postgresql.UUID` looks harmless cross-dialect but isn't: SQLite
    gives an unrecognized column type ("UUID") NUMERIC affinity, so a
    digit-only UUID (fine in practice, but exactly what handwritten test
    fixtures tend to use) silently gets stored as a float and comes back
    corrupted. This type sidesteps that by always declaring CHAR(36).
    """

    impl = CHAR
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(PostgresUUID(as_uuid=True))
        return dialect.type_descriptor(CHAR(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        if dialect.name == "postgresql":
            return str(value)
        return str(value) if isinstance(value, uuid.UUID) else str(uuid.UUID(value))

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))


class UUIDPrimaryKeyMixin:
    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
