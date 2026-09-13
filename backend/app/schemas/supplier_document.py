import uuid
from datetime import datetime

from pydantic import BaseModel

from app.models.extracted_field import ExtractedField
from app.models.supplier_document import SupplierDocument


class SupplierDocumentRead(BaseModel):
    """Company-side view — includes internal ids, unlike the public one."""

    id: uuid.UUID
    filename: str
    content_type: str
    size_bytes: int
    document_type: str
    extraction_status: str
    processing_error: str | None
    extracted_field_count: int
    pending_review_count: int
    uploaded_at: datetime

    @classmethod
    def from_model(
        cls, document: SupplierDocument, extracted_fields: list[ExtractedField] = ()
    ) -> "SupplierDocumentRead":
        return cls(
            id=document.id,
            filename=document.filename,
            content_type=document.content_type,
            size_bytes=document.size_bytes,
            document_type=document.document_type,
            extraction_status=document.extraction_status,
            processing_error=document.processing_error,
            extracted_field_count=len(extracted_fields),
            pending_review_count=sum(
                1 for field in extracted_fields if field.review_status == "pending"
            ),
            uploaded_at=document.created_at,
        )


class PublicSupplierDocumentRead(BaseModel):
    """What the supplier sees of their own uploads in the public portal —
    same fields as the company side; nothing here was ever company/
    supplier-id-shaped to begin with.
    """

    id: uuid.UUID
    filename: str
    content_type: str
    size_bytes: int
    uploaded_at: datetime

    @classmethod
    def from_model(cls, document: SupplierDocument) -> "PublicSupplierDocumentRead":
        return cls(
            id=document.id,
            filename=document.filename,
            content_type=document.content_type,
            size_bytes=document.size_bytes,
            uploaded_at=document.created_at,
        )
