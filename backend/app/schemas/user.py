import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.schemas.company import CompanyRead


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    name: str | None
    company_id: uuid.UUID | None
    created_at: datetime


class CurrentUserRead(BaseModel):
    user: UserRead
    company: CompanyRead | None
