from fastapi import APIRouter

from app.api.v1 import auth, health, inventory, medicines, suppliers, users, warehouses

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(medicines.router)
api_router.include_router(suppliers.router)
api_router.include_router(warehouses.router)
api_router.include_router(inventory.router)
