"""customer_order_tables

Revision ID: c3d4e5f6a1b2
Revises: b2c3d4e5f6a1
Create Date: 2026-06-10 23:30:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c3d4e5f6a1b2"
down_revision: str | None = "b2c3d4e5f6a1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "customer_orders",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("tenant_id", sa.UUID(), nullable=True),
        sa.Column("order_number", sa.String(50), nullable=False),
        sa.Column("customer_id", sa.UUID(), nullable=False),
        sa.Column("sales_rep_id", sa.UUID(), nullable=True),
        sa.Column("order_date", sa.Date(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "draft", "placed", "approved", "allocated", "picked",
                "packed", "dispatched", "delivered", "completed", "cancelled",
                name="order_status",
            ),
            nullable=False,
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("total_amount", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["sales_rep_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("order_number"),
    )
    op.create_index("ix_customer_orders_order_number", "customer_orders", ["order_number"])
    op.create_index("ix_customer_orders_customer_id", "customer_orders", ["customer_id"])
    op.create_index("ix_customer_orders_sales_rep_id", "customer_orders", ["sales_rep_id"])
    op.create_index("ix_customer_orders_tenant_id", "customer_orders", ["tenant_id"])

    op.create_table(
        "order_items",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("order_id", sa.UUID(), nullable=False),
        sa.Column("medicine_id", sa.UUID(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("unit_price", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("discount", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("tax_amount", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("line_total", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.ForeignKeyConstraint(["medicine_id"], ["medicines.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["order_id"], ["customer_orders.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_order_items_order_id", "order_items", ["order_id"])
    op.create_index("ix_order_items_medicine_id", "order_items", ["medicine_id"])

    op.create_table(
        "order_item_allocations",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("order_item_id", sa.UUID(), nullable=False),
        sa.Column("batch_id", sa.UUID(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["batch_id"], ["inventory_batches.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["order_item_id"], ["order_items.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_order_item_allocations_order_item_id", "order_item_allocations", ["order_item_id"])
    op.create_index("ix_order_item_allocations_batch_id", "order_item_allocations", ["batch_id"])


def downgrade() -> None:
    op.drop_table("order_item_allocations")
    op.drop_table("order_items")
    op.drop_table("customer_orders")
    op.execute("DROP TYPE IF EXISTS order_status")
