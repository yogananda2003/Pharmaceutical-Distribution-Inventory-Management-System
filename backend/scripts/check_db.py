"""Quick DB health check — prints table list and row counts."""
import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from app.core.config import get_settings

TABLES = [
    "users", "medicines", "suppliers", "warehouses", "customers",
    "inventory_batches", "inventory_transactions",
    "purchase_orders", "purchase_order_items",
    "customer_orders", "customer_order_items", "invoices",
]

async def main():
    settings = get_settings()
    engine = create_async_engine(settings.database_url, echo=False)

    async with engine.connect() as conn:
        # All tables in public schema
        result = await conn.execute(text(
            "SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename"
        ))
        print("=== TABLES IN DATABASE ===")
        for row in result:
            print(f"  {row[0]}")

        print("\n=== ROW COUNTS ===")
        for tbl in TABLES:
            try:
                r = await conn.execute(text(f"SELECT COUNT(*) FROM {tbl}"))
                count = r.scalar()
                print(f"  {tbl:<30} {count}")
            except Exception as e:
                print(f"  {tbl:<30} ERROR: {e}")

        # Show sample users
        print("\n=== USERS ===")
        result = await conn.execute(text("SELECT email, role, is_active FROM users ORDER BY created_at"))
        for row in result:
            print(f"  {row[0]:<35} role={row[1]}  active={row[2]}")

        # Show sample medicines
        print("\n=== MEDICINES (first 5) ===")
        result = await conn.execute(text("SELECT code, name, dosage_form, strength FROM medicines LIMIT 5"))
        rows = result.fetchall()
        if rows:
            for row in rows:
                print(f"  [{row[0]}] {row[1]} — {row[2]} {row[3]}")
        else:
            print("  (none)")

        # Show inventory batches
        print("\n=== INVENTORY BATCHES (first 5) ===")
        result = await conn.execute(text("""
            SELECT b.batch_number, m.name, b.quantity_available, b.status, b.expiry_date
            FROM inventory_batches b
            JOIN medicines m ON m.id = b.medicine_id
            ORDER BY b.created_at DESC LIMIT 5
        """))
        rows = result.fetchall()
        if rows:
            for row in rows:
                print(f"  {row[0]}  {row[1]}  avail={row[2]}  status={row[3]}  exp={row[4]}")
        else:
            print("  (none)")

    await engine.dispose()
    print("\nDone.")

if __name__ == "__main__":
    asyncio.run(main())
