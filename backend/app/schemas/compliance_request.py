import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.domain.enums import Locale
from app.models.compliance_request import ComplianceRequest


class ComplianceRequestCreate(BaseModel):
    supplier_id: uuid.UUID
    product_ids: list[uuid.UUID] = Field(min_length=1)
    language: Locale


class ComplianceRequestProductRead(BaseModel):
    product_id: uuid.UUID
    product_name: str
    product_sku: str | None


class ComplianceRequestRead(BaseModel):
    id: uuid.UUID
    company_id: uuid.UUID
    supplier_id: uuid.UUID
    supplier_name: str
    status: str
    language: str
    created_at: datetime
    sent_at: datetime | None
    opened_at: datetime | None
    submitted_at: datetime | None
    completed_at: datetime | None
    # A secure link is a one-time reveal (see send()/resend()) — the hash is
    # never turned back into a URL after that, so this is always None here.
    has_active_link: bool
    products: list[ComplianceRequestProductRead]

    @classmethod
    def from_model(cls, request: ComplianceRequest) -> "ComplianceRequestRead":
        return cls(
            id=request.id,
            company_id=request.company_id,
            supplier_id=request.supplier_id,
            supplier_name=request.supplier.name,
            status=request.status,
            language=request.language,
            created_at=request.created_at,
            sent_at=request.sent_at,
            opened_at=request.opened_at,
            submitted_at=request.submitted_at,
            completed_at=request.completed_at,
            has_active_link=(
                request.secure_token_hash is not None and request.token_revoked_at is None
            ),
            products=[
                ComplianceRequestProductRead(
                    product_id=rp.product_id,
                    product_name=rp.product.name,
                    product_sku=rp.product.sku,
                )
                for rp in request.products
            ],
        )


class ComplianceRequestSendResult(BaseModel):
    """`request_url` is handed back exactly once, at send/resend time — the
    server only ever stores its hash afterwards, so this is the only
    response body that will ever contain it.
    """

    request: ComplianceRequestRead
    request_url: str

    @classmethod
    def from_model(cls, request: ComplianceRequest, request_url: str) -> "ComplianceRequestSendResult":
        return cls(request=ComplianceRequestRead.from_model(request), request_url=request_url)
