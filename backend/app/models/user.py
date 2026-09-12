import uuid

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import GUID, TimestampMixin, UUIDPrimaryKeyMixin


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """The `id` is always the Supabase auth user id, never generated locally.

    A row is created lazily on first authenticated request (see
    `UserService.get_or_create_from_identity`) rather than via a signup
    endpoint, since Supabase Auth owns the actual signup flow.
    """

    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    company_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("companies.id"), nullable=True
    )

    company: Mapped["Company"] = relationship(  # noqa: F821
        back_populates="users", foreign_keys=[company_id]
    )
