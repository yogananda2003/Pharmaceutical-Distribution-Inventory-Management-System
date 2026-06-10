from fastapi import APIRouter

from app.api.v1 import (
    auth,
    customers,
    health,
    inventory,
    medicines,
    purchases,
    suppliers,
    users,
    warehouses,
)

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(medicines.router)
api_router.include_router(suppliers.router)
api_router.include_router(warehouses.router)
api_router.include_router(inventory.router)
api_router.include_router(purchases.router)
api_router.include_router(customers.router)
