from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.medicine import DosageForm, Medicine, MedicineStatus
from app.repositories.medicine import MedicineRepository
from app.schemas.medicine import MedicineCreate, MedicineUpdate

logger = get_logger(__name__)


class MedicineService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = MedicineRepository(session)

    async def create(self, data: MedicineCreate, *, tenant_id: UUID | None = None) -> Medicine:
        existing = await self._repo.get_by_code(data.code)
        if existing:
            raise ValueError(f"medicine code '{data.code}' already exists")
        medicine = Medicine(
            code=data.code,
            name=data.name,
            generic_name=data.generic_name,
            manufacturer=data.manufacturer,
            dosage=data.dosage,
            strength=data.strength,
            dosage_form=DosageForm(data.dosage_form),
            unit_type=data.unit_type,
            description=data.description,
            status=MedicineStatus(data.status),
            tenant_id=tenant_id,
        )
        result = await self._repo.add(medicine)
        await self._session.commit()
        logger.info("medicine_created", code=data.code)
        return result

    async def list_medicines(self, *, limit: int = 100, offset: int = 0) -> list[Medicine]:
        return list(await self._repo.list(limit=limit, offset=offset))

    async def list_active(self, *, limit: int = 100, offset: int = 0) -> list[Medicine]:
        return await self._repo.list_active(limit=limit, offset=offset)

    async def get(self, medicine_id: UUID) -> Medicine:
        medicine = await self._repo.get_by_id_not_deleted(medicine_id)
        if not medicine:
            raise ValueError("medicine not found")
        return medicine

    async def get_by_code(self, code: str) -> Medicine:
        medicine = await self._repo.get_by_code(code)
        if not medicine:
            raise ValueError("medicine not found")
        return medicine

    async def update(self, medicine_id: UUID, data: MedicineUpdate) -> Medicine:
        medicine = await self._repo.get_by_id_not_deleted(medicine_id)
        if not medicine:
            raise ValueError("medicine not found")
        if data.name is not None:
            medicine.name = data.name
        if data.generic_name is not None:
            medicine.generic_name = data.generic_name
        if data.manufacturer is not None:
            medicine.manufacturer = data.manufacturer
        if data.dosage is not None:
            medicine.dosage = data.dosage
        if data.strength is not None:
            medicine.strength = data.strength
        if data.dosage_form is not None:
            medicine.dosage_form = DosageForm(data.dosage_form)
        if data.unit_type is not None:
            medicine.unit_type = data.unit_type
        if data.description is not None:
            medicine.description = data.description
        if data.status is not None:
            medicine.status = MedicineStatus(data.status)
        await self._session.flush()
        await self._session.commit()
        logger.info("medicine_updated", medicine_id=str(medicine_id))
        return medicine

    async def delete(self, medicine_id: UUID) -> None:
        medicine = await self._repo.get_by_id_not_deleted(medicine_id)
        if not medicine:
            raise ValueError("medicine not found")
        await self._repo.soft_delete(medicine)
        await self._session.commit()
        logger.info("medicine_deleted", medicine_id=str(medicine_id))

    async def search(self, query: str) -> list[Medicine]:
        return await self._repo.search(query)
