import uuid
from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class UUIDPrimaryKeyMixin:
    """Generates the PK client-side so new entities have an id before the first flush."""

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=lambda: uuid.uuid4()
    )


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class SoftDeleteMixin:
    """`deleted_at` marks a business entity as removed without losing its history.

    Append-only ledgers (inventory transactions, audit logs) must NOT use this mixin —
    they are never soft-deleted either, per the domain's audit requirements.
    """

    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class TenantMixin:
    """Multi-tenant readiness: every business entity carries `tenant_id` even though the
    platform is currently single-tenant. Nullable and unenforced for now — wiring up
    tenant isolation is a deliberately deferred future migration.
    """

    tenant_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )


class BaseEntity(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, Base):
    """Abstract base for all domain entities: UUID PK + audit timestamps + soft delete."""

    __abstract__ = True


class TenantedEntity(TenantMixin, BaseEntity):
    """Abstract base for business entities that must carry the `tenant_id` convention."""

    __abstract__ = True
