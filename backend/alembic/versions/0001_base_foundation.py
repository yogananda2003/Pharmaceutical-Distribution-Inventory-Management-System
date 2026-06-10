"""Base foundation: UUID PKs, audit timestamps, soft delete, tenant_id convention.

Stage 1 establishes the shape every domain entity will follow.
No domain tables yet — they arrive in Stages 4–12.

Revision ID: 0001
Revises:
Create Date: 2026-06-09
"""

from collections.abc import Sequence

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Stage 1 has no tables of its own — the base mixins are abstract and produce
    # no tables until a concrete domain entity (Stage 4 onward) uses them.
    # This migration intentionally runs clean so that `alembic upgrade head` works
    # on a fresh database and round-trips (downgrade → upgrade) cleanly.
    pass


def downgrade() -> None:
    pass
