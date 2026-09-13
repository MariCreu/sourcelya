from fastapi import APIRouter

from app.api.v1 import (
    auth,
    companies,
    health,
    internal,
    products,
    public_requests,
    requests,
    suppliers,
)

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(companies.router)
api_router.include_router(internal.router)
api_router.include_router(suppliers.router)
api_router.include_router(products.router)
api_router.include_router(requests.router)
api_router.include_router(public_requests.router)
