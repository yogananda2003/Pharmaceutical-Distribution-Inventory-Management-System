from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.warehouse import Warehouse
from app.repositories.warehouse import WarehouseRepository
from app.schemas.warehouse import WarehouseCreate, WarehouseUpdate

logger = get_logger(__name__)


class WarehouseService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = WarehouseRepository(session)

    async def create(self, data: WarehouseCreate, *, tenant_id: UUID | None = None) -> Warehouse:
        if await self._repo.get_by_code(data.warehouse_code):
            raise ValueError(f"warehouse code '{data.warehouse_code}' already exists")
        warehouse = Warehouse(
            warehouse_code=data.warehouse_code,
            warehouse_name=data.warehouse_name,
            address=data.address,
            contact_details=data.contact_details,
            is_active=data.is_active,
            tenant_id=tenant_id,
        )
        result = await self._repo.add(warehouse)
        await self._session.commit()
        logger.info("warehouse_created", code=data.warehouse_code)
        return result

    async def list_warehouses(self, *, limit: int = 100, offset: int = 0) -> list[Warehouse]:
        return list(await self._repo.list(limit=limit, offset=offset))

    async def list_active(self, *, limit: int = 100, offset: int = 0) -> list[Warehouse]:
        return await self._repo.list_active(limit=limit, offset=offset)

    async def get(self, warehouse_id: UUID) -> Warehouse:
        warehouse = await self._repo.get_by_id_not_deleted(warehouse_id)
        if not warehouse:
            raise ValueError("warehouse not found")
        return warehouse

    async def update(self, warehouse_id: UUID, data: WarehouseUpdate) -> Warehouse:
        warehouse = await self._repo.get_by_id_not_deleted(warehouse_id)
        if not warehouse:
            raise ValueError("warehouse not found")
        if data.warehouse_name is not None:
            warehouse.warehouse_name = data.warehouse_name
        if data.address is not None:
            warehouse.address = data.address
        if data.contact_details is not None:
            warehouse.contact_details = data.contact_details
        if data.is_active is not None:
            warehouse.is_active = data.is_active
        await self._session.flush()
        await self._session.commit()
        logger.info("warehouse_updated", warehouse_id=str(warehouse_id))
        return warehouse

    async def delete(self, warehouse_id: UUID) -> None:
        warehouse = await self._repo.get_by_id_not_deleted(warehouse_id)
        if not warehouse:
            raise ValueError("warehouse not found")
        await self._repo.soft_delete(warehouse)
        await self._session.commit()
        logger.info("warehouse_deleted", warehouse_id=str(warehouse_id))
