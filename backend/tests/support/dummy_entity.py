"""A throwaway entity + repository used only to exercise BaseEntity/TenantedEntity and
BaseRepository in tests. Its table is created/dropped alongside the real schema for the
test session (see conftest._prepare_database) and is never part of the real migrations —
alembic's env.py only imports `app.models`, not this module.
"""

from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import TenantedEntity
from app.repositories.base import BaseRepository


class DummyEntity(TenantedEntity):
    __tablename__ = "test_dummy_entities"

    name: Mapped[str] = mapped_column(nullable=False)


class DummyRepository(BaseRepository[DummyEntity]):
    model = DummyEntity
