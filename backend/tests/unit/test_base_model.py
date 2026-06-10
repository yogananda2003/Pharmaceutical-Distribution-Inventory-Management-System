import uuid

from sqlalchemy import DateTime
from sqlalchemy.dialects.postgresql import UUID

from app.models.base import BaseEntity, TenantedEntity, TenantMixin
from tests.support.dummy_entity import DummyEntity


def test_base_entity_has_uuid_primary_key() -> None:
    column = DummyEntity.__table__.c.id

    assert column.primary_key is True
    assert isinstance(column.type, UUID)
    assert column.default is not None
    # SQLAlchemy wraps zero-arg callables as `lambda ctx: fn()`, so pass ctx=None
    assert isinstance(column.default.arg(None), uuid.UUID)


def test_base_entity_generates_unique_ids() -> None:
    default = DummyEntity.__table__.c.id.default
    assert default is not None

    first = default.arg(None)
    second = default.arg(None)

    assert first != second


def test_base_entity_has_audit_timestamp_columns() -> None:
    table = DummyEntity.__table__

    for column_name in ("created_at", "updated_at"):
        column = table.c[column_name]
        assert isinstance(column.type, DateTime)
        assert column.nullable is False
        assert column.server_default is not None

    assert table.c.updated_at.onupdate is not None


def test_base_entity_has_optional_soft_delete_column() -> None:
    column = DummyEntity.__table__.c.deleted_at

    assert isinstance(column.type, DateTime)
    assert column.nullable is True


def test_tenanted_entity_adds_tenant_id_but_base_entity_does_not() -> None:
    assert TenantMixin not in BaseEntity.__mro__
    assert TenantMixin in TenantedEntity.__mro__

    # Both abstract bases produce no table of their own; DummyEntity (a TenantedEntity)
    # is the concrete proof that the mixin contributes the tenant_id column.
    assert getattr(BaseEntity, "__table__", None) is None
    assert getattr(TenantedEntity, "__table__", None) is None
    assert "tenant_id" in DummyEntity.__table__.c


def test_tenant_id_is_nullable_and_unenforced_for_now() -> None:
    column = DummyEntity.__table__.c.tenant_id

    assert isinstance(column.type, UUID)
    assert column.nullable is True


def test_python_side_default_is_callable_with_context() -> None:
    """The column default callable must accept one arg (ctx) — SQLAlchemy wraps zero-arg
    callables as ``lambda ctx: fn()`` to match its internal calling convention.
    Calling it twice must return distinct UUIDs.
    """
    default = DummyEntity.__table__.c.id.default
    assert default is not None and default.is_callable

    first, second = default.arg(None), default.arg(None)
    assert first != second
    assert isinstance(first, __import__("uuid").UUID)
