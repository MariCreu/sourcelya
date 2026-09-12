import uuid

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import GUID, TimestampMixin, UUIDPrimaryKeyMixin


class Company(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "companies"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    country: Mapped[str] = mapped_column(String(2), nullable=False)
    owner_user_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("users.id", use_alter=True), nullable=False
    )

    users: Mapped[list["User"]] = relationship(  # noqa: F821
        back_populates="company", foreign_keys="User.company_id"
    )
