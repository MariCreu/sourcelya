import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_company, get_db
from app.models.company import Company
from app.schemas.supplier import SupplierCreate, SupplierRead, SupplierUpdate
from app.services.supplier_service import SupplierService

router = APIRouter(prefix="/suppliers", tags=["suppliers"])


@router.post("", response_model=SupplierRead, status_code=status.HTTP_201_CREATED)
def create_supplier(
    payload: SupplierCreate,
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
) -> SupplierRead:
    return SupplierService(db).create(company.id, payload)


@router.get("", response_model=list[SupplierRead])
def list_suppliers(
    company: Company = Depends(get_current_company), db: Session = Depends(get_db)
) -> list[SupplierRead]:
    return SupplierService(db).list(company.id)


@router.get("/{supplier_id}", response_model=SupplierRead)
def get_supplier(
    supplier_id: uuid.UUID,
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
) -> SupplierRead:
    supplier = SupplierService(db).get(company.id, supplier_id)
    if supplier is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Supplier not found")
    return supplier


@router.patch("/{supplier_id}", response_model=SupplierRead)
def update_supplier(
    supplier_id: uuid.UUID,
    payload: SupplierUpdate,
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
) -> SupplierRead:
    supplier = SupplierService(db).update(company.id, supplier_id, payload)
    if supplier is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Supplier not found")
    return supplier
