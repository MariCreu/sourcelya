import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_company, get_db
from app.domain.enums import FieldReviewStatus
from app.models.company import Company
from app.models.extracted_field import ExtractedField
from app.schemas.packaging_component import (
    PackagingComponentCreate,
    PackagingComponentRead,
    PackagingComponentUpdate,
)
from app.schemas.product import ProductCreate, ProductDetailRead, ProductRead, ProductUpdate
from app.services.packaging_component_service import (
    PackagingComponentService,
    ProductNotFoundError,
)
from app.services.product_service import ProductService, SupplierNotFoundError
from app.services.status_calculation_service import StatusCalculationService

router = APIRouter(prefix="/products", tags=["products"])
status_service = StatusCalculationService()


def _pending_review_component_ids(db: Session, company_id: uuid.UUID) -> frozenset:
    """Which `PackagingComponent`s have a FASE 5 `ExtractedField` still
    awaiting a human decision — computed here (not inside
    `StatusCalculationService`, which stays DB-free) and passed in so RED
    can be produced. See that service's docstring.
    """
    stmt = select(ExtractedField.packaging_component_id).where(
        ExtractedField.company_id == company_id,
        ExtractedField.review_status == FieldReviewStatus.PENDING.value,
        ExtractedField.packaging_component_id.is_not(None),
    )
    return frozenset(db.scalars(stmt).all())


def _to_detail_read(db: Session, company_id: uuid.UUID, product) -> ProductDetailRead:
    pending = _pending_review_component_ids(db, company_id)
    component_reads = [
        PackagingComponentRead.from_model(
            component,
            status_service.calculate_component_status(
                component, has_pending_review=component.id in pending
            ),
        )
        for component in product.packaging_components
    ]
    return ProductDetailRead.from_model_with_components(
        product, status_service.calculate_product_status(product, pending), component_reads
    )


@router.post("", response_model=ProductRead, status_code=status.HTTP_201_CREATED)
def create_product(
    payload: ProductCreate,
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
) -> ProductRead:
    try:
        product = ProductService(db).create(company.id, payload)
    except SupplierNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return ProductRead.from_model(product, status_service.calculate_product_status(product))


@router.get("", response_model=list[ProductRead])
def list_products(
    company: Company = Depends(get_current_company), db: Session = Depends(get_db)
) -> list[ProductRead]:
    products = ProductService(db).list(company.id)
    pending = _pending_review_component_ids(db, company.id)
    return [
        ProductRead.from_model(product, status_service.calculate_product_status(product, pending))
        for product in products
    ]


@router.get("/{product_id}", response_model=ProductDetailRead)
def get_product(
    product_id: uuid.UUID,
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
) -> ProductDetailRead:
    product = ProductService(db).get(company.id, product_id)
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    return _to_detail_read(db, company.id, product)


@router.patch("/{product_id}", response_model=ProductRead)
def update_product(
    product_id: uuid.UUID,
    payload: ProductUpdate,
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
) -> ProductRead:
    try:
        product = ProductService(db).update(company.id, product_id, payload)
    except SupplierNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    pending = _pending_review_component_ids(db, company.id)
    return ProductRead.from_model(product, status_service.calculate_product_status(product, pending))


@router.post(
    "/{product_id}/packaging-components",
    response_model=PackagingComponentRead,
    status_code=status.HTTP_201_CREATED,
)
def create_packaging_component(
    product_id: uuid.UUID,
    payload: PackagingComponentCreate,
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
) -> PackagingComponentRead:
    try:
        component = PackagingComponentService(db).create(company.id, product_id, payload)
    except ProductNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return PackagingComponentRead.from_model(
        component, status_service.calculate_component_status(component)
    )  # brand-new component: never has a pending extraction proposal yet


@router.get(
    "/{product_id}/packaging-components", response_model=list[PackagingComponentRead]
)
def list_packaging_components(
    product_id: uuid.UUID,
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
) -> list[PackagingComponentRead]:
    try:
        components = PackagingComponentService(db).list_for_product(company.id, product_id)
    except ProductNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    pending = _pending_review_component_ids(db, company.id)
    return [
        PackagingComponentRead.from_model(
            component,
            status_service.calculate_component_status(
                component, has_pending_review=component.id in pending
            ),
        )
        for component in components
    ]


@router.patch(
    "/{product_id}/packaging-components/{component_id}", response_model=PackagingComponentRead
)
def update_packaging_component(
    product_id: uuid.UUID,
    component_id: uuid.UUID,
    payload: PackagingComponentUpdate,
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
) -> PackagingComponentRead:
    try:
        component = PackagingComponentService(db).update(
            company.id, product_id, component_id, payload
        )
    except ProductNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    if component is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Packaging component not found"
        )
    pending = _pending_review_component_ids(db, company.id)
    return PackagingComponentRead.from_model(
        component,
        status_service.calculate_component_status(
            component, has_pending_review=component.id in pending
        ),
    )
