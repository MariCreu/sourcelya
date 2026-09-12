import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class SupplierCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    email: EmailStr
    country: str | None = Field(default=None, min_length=2, max_length=2, description="ISO 3166-1 alpha-2")


class SupplierUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    email: EmailStr | None = None
    country: str | None = Field(default=None, min_length=2, max_length=2)


class SupplierRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    company_id: uuid.UUID
    name: str
    email: str
    country: str | None
    created_at: datetime
