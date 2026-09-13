"""Computes compliance status on the fly — never cached.

`Product` and `PackagingComponent` have no `status` column. With the small
number of records the MVP will have while validating the product, computing
status at read time avoids an entire class of bugs where the cached value
drifts from the real data (a field edited without recalculating, a
migration that forgets to backfill, ...). If usage later shows this is a
real performance problem, that's the point to add denormalization,
materialized views, or a cache — not before.
"""

from dataclasses import dataclass

from app.domain.enums import ComplianceStatus
from app.models.packaging_component import PackagingComponent
from app.models.product import Product

# MVP required fields — see product spec section 7. `manufacturer`,
# `packaging_reference`, `notes` and `country_of_manufacture` are optional.
REQUIRED_PACKAGING_FIELDS = (
    "packaging_type",
    "material",
    "weight_grams",
    "recycled_content_percentage",
)


@dataclass(frozen=True)
class ComponentStatusResult:
    status: ComplianceStatus
    missing_fields: tuple[str, ...]


class StatusCalculationService:
    def calculate_component_status(
        self, component: PackagingComponent, has_pending_review: bool = False
    ) -> ComponentStatusResult:
        """`has_pending_review` is computed by the caller — this service
        stays pure/DB-free — from whether any FASE 5 `ExtractedField` for
        this component is still `review_status=PENDING`. RED overrides
        ORANGE/GREEN (a proposal needing a human decision is more urgent
        than "just missing data") but `missing_fields` is still reported
        alongside it, so the UI can show both at once.
        """
        missing = tuple(
            field
            for field in REQUIRED_PACKAGING_FIELDS
            if getattr(component, field) in (None, "")
        )
        if has_pending_review:
            return ComponentStatusResult(status=ComplianceStatus.RED, missing_fields=missing)
        if missing:
            return ComponentStatusResult(status=ComplianceStatus.ORANGE, missing_fields=missing)
        return ComponentStatusResult(status=ComplianceStatus.GREEN, missing_fields=())

    def calculate_product_status(
        self, product: Product, components_with_pending_review: frozenset = frozenset()
    ) -> ComplianceStatus:
        if not product.packaging_components:
            return ComplianceStatus.ORANGE

        statuses = [
            self.calculate_component_status(
                component, has_pending_review=component.id in components_with_pending_review
            ).status
            for component in product.packaging_components
        ]

        if ComplianceStatus.RED in statuses:
            return ComplianceStatus.RED
        if all(status == ComplianceStatus.GREEN for status in statuses):
            return ComplianceStatus.GREEN
        return ComplianceStatus.ORANGE
