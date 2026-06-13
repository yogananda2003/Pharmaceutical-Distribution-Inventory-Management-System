"""
Create seed users for local development.

Usage (from the backend/ directory, with .venv activated):
    python scripts/seed_users.py

Creates:
    admin@pharma.com        / Admin@1234!   (admin)
    sales@pharma.com        / Sales@1234!   (sales_representative)
    inventory@pharma.com    / Inventory@1   (inventory_manager)
    warehouse@pharma.com    / Warehouse@1   (warehouse_staff)
    customer@pharma.com     / Customer@1    (customer)
"""
from __future__ import annotations

import asyncio
import sys
import os

# Make sure we can import from the backend app package
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.core.security import hash_password
from app.repositories.user import UserRepository

SEED_USERS = [
    ("admin@pharma.com",     "Admin@1234!",   "admin"),
    ("sales@pharma.com",     "Sales@1234!",   "sales_representative"),
    ("inventory@pharma.com", "Inventory@1",   "inventory_manager"),
    ("warehouse@pharma.com", "Warehouse@1",   "warehouse_staff"),
    ("customer@pharma.com",  "Customer@1",    "customer"),
]


async def main() -> None:
    settings = get_settings()
    engine = create_async_engine(settings.database_url, echo=False)
    Session = async_sessionmaker(engine, expire_on_commit=False)

    async with Session() as session:
        repo = UserRepository(session)
        created, skipped = 0, 0

        for email, password, role in SEED_USERS:
            existing = await repo.get_by_email(email)
            if existing:
                print(f"  SKIP  {email}  (already exists, role={existing.role.value})")
                skipped += 1
                continue

            user = await repo.create(
                email=email,
                password_hash=hash_password(password),
                role=role,
            )
            await session.commit()
            print(f"  OK    {email}  (role={role}, id={user.id})")
            created += 1

    await engine.dispose()
    print(f"\nDone. {created} created, {skipped} skipped.")


if __name__ == "__main__":
    asyncio.run(main())
