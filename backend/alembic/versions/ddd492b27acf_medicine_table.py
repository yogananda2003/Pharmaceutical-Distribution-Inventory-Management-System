"""medicine_table

Revision ID: ddd492b27acf
Revises: c5e7141603fd
Create Date: 2026-06-10 15:40:55.662247

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = 'ddd492b27acf'
down_revision: str | None = 'c5e7141603fd'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'medicines',
        sa.Column('code', sa.String(length=50), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('generic_name', sa.String(length=255), nullable=False),
        sa.Column('manufacturer', sa.String(length=255), nullable=False),
        sa.Column('dosage', sa.String(length=100), nullable=False),
        sa.Column('strength', sa.String(length=100), nullable=False),
        sa.Column(
            'dosage_form',
            sa.Enum(
                'tablet', 'capsule', 'injection', 'syrup', 'ointment',
                'drops', 'powder', 'cream', 'gel', 'inhaler',
                name='dosage_form',
            ),
            nullable=False,
        ),
        sa.Column('unit_type', sa.String(length=50), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column(
            'status',
            sa.Enum('active', 'inactive', 'discontinued', name='medicine_status'),
            nullable=False,
        ),
        sa.Column('tenant_id', sa.UUID(), nullable=True),
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_medicines_code'), 'medicines', ['code'], unique=True)
    op.create_index(op.f('ix_medicines_name'), 'medicines', ['name'], unique=False)
    op.create_index(op.f('ix_medicines_tenant_id'), 'medicines', ['tenant_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_medicines_tenant_id'), table_name='medicines')
    op.drop_index(op.f('ix_medicines_name'), table_name='medicines')
    op.drop_index(op.f('ix_medicines_code'), table_name='medicines')
    op.drop_table('medicines')
    # PostgreSQL enum types survive table drops — remove explicitly on downgrade.
    op.execute("DROP TYPE IF EXISTS dosage_form")
    op.execute("DROP TYPE IF EXISTS medicine_status")
