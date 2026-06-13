from fastapi import APIRouter

from app.api.v1 import (
    auth,
    customers,
    expiry_alerts,
    health,
    inventory,
    invoices,
    medicines,
    orders,
    purchases,
    reports,
    suppliers,
    users,
    warehouse_ops,
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
api_router.include_router(orders.router)
api_router.include_router(warehouse_ops.router)
api_router.include_router(invoices.router)
api_router.include_router(expiry_alerts.router)
api_router.include_router(reports.router)
