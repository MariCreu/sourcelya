import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CompanyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    country: str = Field(min_length=2, max_length=2, description="ISO 3166-1 alpha-2")


class CompanyRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    country: str
    owner_user_id: uuid.UUID
    created_at: datetime
