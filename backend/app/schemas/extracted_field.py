import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from app.models.extracted_field import ExtractedField


class ExtractedFieldRead(BaseModel):
    id: uuid.UUID
    document_id: uuid.UUID
    packaging_component_id: uuid.UUID | None
    field_name: str
    extracted_value: str
    confidence: str
    source_page: int | None
    source_quote: str | None
    quote_verified: bool
    review_status: str
    created_at: datetime

    @classmethod
    def from_model(cls, field: ExtractedField) -> "ExtractedFieldRead":
        return cls(
            id=field.id,
            document_id=field.document_id,
            packaging_component_id=field.packaging_component_id,
            field_name=field.field_name,
            extracted_value=field.extracted_value,
            confidence=field.confidence,
            source_page=field.source_page,
            source_quote=field.source_quote,
            quote_verified=field.quote_verified,
            review_status=field.review_status,
            created_at=field.created_at,
        )


class AcceptExtractedFieldPayload(BaseModel):
    packaging_component_id: uuid.UUID | None = None
    conflict_resolution: Literal["use_extracted", "keep_current"] | None = None


class ExtractedFieldConflict(BaseModel):
    """The 409 body when accepting would silently overwrite a different
    existing value — see the FASE 5 spec's conflict example verbatim."""

    detail: Literal["POSSIBLE CONFLICT"] = "POSSIBLE CONFLICT"
    field_name: str
    current_value: str
    extracted_value: str
