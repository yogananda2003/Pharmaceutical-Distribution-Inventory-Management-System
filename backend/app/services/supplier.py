from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.supplier import Supplier, SupplierStatus
from app.repositories.supplier import SupplierRepository
from app.schemas.supplier import SupplierCreate, SupplierUpdate

logger = get_logger(__name__)


class SupplierService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = SupplierRepository(session)

    async def create(self, data: SupplierCreate, *, tenant_id: UUID | None = None) -> Supplier:
        if await self._repo.get_by_code(data.supplier_code):
            raise ValueError(f"supplier code '{data.supplier_code}' already exists")
        supplier = Supplier(
            supplier_code=data.supplier_code,
            supplier_name=data.supplier_name,
            gst_number=data.gst_number,
            drug_license_number=data.drug_license_number,
            address=data.address,
            contact_person=data.contact_person,
            email=str(data.email) if data.email else None,
            phone=data.phone,
            status=SupplierStatus(data.status),
            tenant_id=tenant_id,
        )
        result = await self._repo.add(supplier)
        await self._session.commit()
        logger.info("supplier_created", code=data.supplier_code)
        return result

    async def list_suppliers(self, *, limit: int = 100, offset: int = 0) -> list[Supplier]:
        return list(await self._repo.list(limit=limit, offset=offset))

    async def get(self, supplier_id: UUID) -> Supplier:
        supplier = await self._repo.get_by_id_not_deleted(supplier_id)
        if not supplier:
            raise ValueError("supplier not found")
        return supplier

    async def update(self, supplier_id: UUID, data: SupplierUpdate) -> Supplier:
        supplier = await self._repo.get_by_id_not_deleted(supplier_id)
        if not supplier:
            raise ValueError("supplier not found")
        if data.supplier_name is not None:
            supplier.supplier_name = data.supplier_name
        if data.gst_number is not None:
            supplier.gst_number = data.gst_number
        if data.drug_license_number is not None:
            supplier.drug_license_number = data.drug_license_number
        if data.address is not None:
            supplier.address = data.address
        if data.contact_person is not None:
            supplier.contact_person = data.contact_person
        if data.email is not None:
            supplier.email = str(data.email)
        if data.phone is not None:
            supplier.phone = data.phone
        if data.status is not None:
            supplier.status = SupplierStatus(data.status)
        await self._session.flush()
        await self._session.commit()
        logger.info("supplier_updated", supplier_id=str(supplier_id))
        return supplier

    async def delete(self, supplier_id: UUID) -> None:
        supplier = await self._repo.get_by_id_not_deleted(supplier_id)
        if not supplier:
            raise ValueError("supplier not found")
        await self._repo.soft_delete(supplier)
        await self._session.commit()
        logger.info("supplier_deleted", supplier_id=str(supplier_id))
