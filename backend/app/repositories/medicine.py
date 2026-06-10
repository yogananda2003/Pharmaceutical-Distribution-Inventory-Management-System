from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.medicine import Medicine, MedicineStatus
from app.repositories.base import BaseRepository


class MedicineRepository(BaseRepository[Medicine]):
    model = Medicine

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def get_by_id_not_deleted(self, medicine_id: UUID) -> Medicine | None:
        result = await self.session.execute(
            select(Medicine).where(
                Medicine.id == medicine_id,
                Medicine.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def get_by_code(self, code: str) -> Medicine | None:
        result = await self.session.execute(
            select(Medicine).where(
                Medicine.code == code,
                Medicine.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def search(self, query: str, *, limit: int = 50) -> list[Medicine]:
        pattern = f"%{query}%"
        result = await self.session.execute(
            select(Medicine)
            .where(
                Medicine.deleted_at.is_(None),
                (
                    Medicine.name.ilike(pattern)
                    | Medicine.generic_name.ilike(pattern)
                    | Medicine.code.ilike(pattern)
                ),
            )
            .limit(limit)
        )
        return list(result.scalars().all())

    async def list_active(self, *, limit: int = 100, offset: int = 0) -> list[Medicine]:
        result = await self.session.execute(
            select(Medicine)
            .where(
                Medicine.deleted_at.is_(None),
                Medicine.status == MedicineStatus.ACTIVE,
            )
            .order_by(Medicine.name)
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())
