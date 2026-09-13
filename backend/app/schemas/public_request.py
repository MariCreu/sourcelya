import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.models.compliance_request import ComplianceRequest
from app.models.supplier_document import SupplierDocument
from app.schemas.supplier_document import PublicSupplierDocumentRead
from app.services.missing_information_service import RequestInformationSummary


class PublicPackagingComponentRead(BaseModel):
    id: uuid.UUID
    name: str
    packaging_type: str
    material: str | None
    weight_grams: float | None
    recycled_content_percentage: float | None
    packaging_reference: str | None
    notes: str | None


class PublicProductRead(BaseModel):
    id: uuid.UUID
    name: str
    sku: str | None
    packaging_components: list[PublicPackagingComponentRead]


class PublicMissingFieldRef(BaseModel):
    packaging_component_id: uuid.UUID
    field_name: str


class PublicComplianceRequestRead(BaseModel):
    """What a supplier who only has the raw token is allowed to see.
    Deliberately excludes company_id/supplier_id/internal ids beyond what's
    needed to address this request's own products — see the spec's
    "seguridad" section.
    """

    status: str
    language: str
    company_name: str
    supplier_name: str
    submitted_at: datetime | None
    products: list[PublicProductRead]
    documents: list[PublicSupplierDocumentRead]
    # FASE 6: non-empty only once the supplier has submitted at least once
    # (`submitted_at is not None`) and something is still outstanding —
    # drives the portal's "ALMOST THERE" scoped view. No evidence,
    # confidence, or pending-review internals leak here — a supplier never
    # sees anything beyond "these fields still need a value", same
    # boundary FASE 5 already draws around ExtractedField.
    missing_fields: list[PublicMissingFieldRef] = Field(default_factory=list)

    @classmethod
    def from_model(
        cls,
        request: ComplianceRequest,
        company_name: str,
        documents: list[SupplierDocument] = (),
        information_summary: RequestInformationSummary | None = None,
    ) -> "PublicComplianceRequestRead":
        missing_fields = (
            [
                PublicMissingFieldRef(
                    packaging_component_id=ref["packaging_component_id"],
                    field_name=ref["field_name"],
                )
                for ref in information_summary.missing_field_refs
            ]
            if information_summary is not None
            else []
        )
        return cls(
            status=request.status,
            language=request.language,
            company_name=company_name,
            supplier_name=request.supplier.name,
            submitted_at=request.submitted_at,
            missing_fields=missing_fields,
            documents=[PublicSupplierDocumentRead.from_model(document) for document in documents],
            products=[
                PublicProductRead(
                    id=rp.product.id,
                    name=rp.product.name,
                    sku=rp.product.sku,
                    packaging_components=[
                        PublicPackagingComponentRead(
                            id=component.id,
                            name=component.name,
                            packaging_type=component.packaging_type,
                            material=component.material,
                            weight_grams=component.weight_grams,
                            recycled_content_percentage=component.recycled_content_percentage,
                            packaging_reference=component.packaging_reference,
                            notes=component.notes,
                        )
                        for component in rp.product.packaging_components
                    ],
                )
                for rp in request.products
            ],
        )


class PublicPackagingComponentUpdate(BaseModel):
    id: uuid.UUID
    material: str | None = Field(default=None, max_length=255)
    weight_grams: float | None = Field(default=None, ge=0)
    recycled_content_percentage: float | None = Field(default=None, ge=0, le=100)
    packaging_reference: str | None = Field(default=None, max_length=255)
    notes: str | None = None


class PublicSaveRequestPayload(BaseModel):
    components: list[PublicPackagingComponentUpdate] = Field(default_factory=list)
