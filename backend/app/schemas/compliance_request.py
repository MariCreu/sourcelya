import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.domain.enums import Locale
from app.models.compliance_request import ComplianceRequest
from app.models.extracted_field import ExtractedField
from app.models.follow_up_round import FollowUpRound
from app.models.supplier_document import SupplierDocument
from app.schemas.follow_up import FollowUpRoundRead, RecoveryStatsRead, RequestInformationSummaryRead
from app.schemas.supplier_document import SupplierDocumentRead
from app.services.follow_up_service import RecoveryStats
from app.services.missing_information_service import RequestInformationSummary


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
    documents: list[SupplierDocumentRead]
    # FASE 6 — see MissingInformationService/FollowUpService. Optional
    # (default None/[]) because a handful of callers (e.g. the send/resend
    # result, which already returns the request right after a state change
    # unrelated to information completeness) don't need the extra queries.
    automatic_follow_up: bool = False
    information_status: RequestInformationSummaryRead | None = None
    follow_up_rounds: list[FollowUpRoundRead] = Field(default_factory=list)
    recovery_stats: RecoveryStatsRead | None = None

    @classmethod
    def from_model(
        cls,
        request: ComplianceRequest,
        documents: list[SupplierDocument] = (),
        extracted_fields_by_document: dict[uuid.UUID, list[ExtractedField]] = None,
        information_summary: RequestInformationSummary | None = None,
        follow_up_rounds: list[FollowUpRound] = (),
        recovery_stats: RecoveryStats | None = None,
    ) -> "ComplianceRequestRead":
        extracted_fields_by_document = extracted_fields_by_document or {}
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
            automatic_follow_up=request.automatic_follow_up,
            products=[
                ComplianceRequestProductRead(
                    product_id=rp.product_id,
                    product_name=rp.product.name,
                    product_sku=rp.product.sku,
                )
                for rp in request.products
            ],
            documents=[
                SupplierDocumentRead.from_model(
                    document, extracted_fields_by_document.get(document.id, [])
                )
                for document in documents
            ],
            information_status=(
                RequestInformationSummaryRead.from_summary(information_summary)
                if information_summary is not None
                else None
            ),
            follow_up_rounds=[FollowUpRoundRead.from_model(r) for r in follow_up_rounds],
            recovery_stats=(
                RecoveryStatsRead.from_stats(recovery_stats) if recovery_stats is not None else None
            ),
        )


class ComplianceRequestSendResult(BaseModel):
    """`request_url` is handed back exactly once, at send/resend time — the
    server only ever stores its hash afterwards, so this is the only
    response body that will ever contain it.
    """

    request: ComplianceRequestRead
    request_url: str

    @classmethod
    def from_model(
        cls,
        request: ComplianceRequest,
        request_url: str,
        documents: list[SupplierDocument] = (),
    ) -> "ComplianceRequestSendResult":
        return cls(
            request=ComplianceRequestRead.from_model(request, documents),
            request_url=request_url,
        )
