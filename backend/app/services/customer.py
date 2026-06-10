from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.customer import Customer, CustomerStatus
from app.repositories.customer import CustomerRepository
from app.schemas.customer import CustomerCreate, CustomerUpdate

logger = get_logger(__name__)


class CustomerService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = CustomerRepository(session)

    async def create(self, data: CustomerCreate, *, tenant_id: UUID | None = None) -> Customer:
        if await self._repo.get_by_code(data.customer_code):
            raise ValueError(f"customer code '{data.customer_code}' already exists")
        customer = Customer(
            customer_code=data.customer_code,
            business_name=data.business_name,
            contact_person=data.contact_person,
            email=str(data.email) if data.email else None,
            phone=data.phone,
            gst_number=data.gst_number,
            drug_license_number=data.drug_license_number,
            address=data.address,
            credit_limit=data.credit_limit,
            status=CustomerStatus(data.status),
            tenant_id=tenant_id,
        )
        result = await self._repo.add(customer)
        await self._session.commit()
        logger.info("customer_created", code=data.customer_code)
        return result

    async def get(self, customer_id: UUID) -> Customer:
        customer = await self._repo.get_by_id_not_deleted(customer_id)
        if not customer:
            raise ValueError("customer not found")
        return customer

    async def list_customers(self, *, active_only: bool = False) -> list[Customer]:
        if active_only:
            return await self._repo.list_active()
        return await self._repo.list_all_not_deleted()

    async def update(self, customer_id: UUID, data: CustomerUpdate) -> Customer:
        customer = await self._repo.get_by_id_not_deleted(customer_id)
        if not customer:
            raise ValueError("customer not found")
        if data.business_name is not None:
            customer.business_name = data.business_name
        if data.contact_person is not None:
            customer.contact_person = data.contact_person
        if data.email is not None:
            customer.email = str(data.email)
        if data.phone is not None:
            customer.phone = data.phone
        if data.gst_number is not None:
            customer.gst_number = data.gst_number
        if data.drug_license_number is not None:
            customer.drug_license_number = data.drug_license_number
        if data.address is not None:
            customer.address = data.address
        if data.credit_limit is not None:
            customer.credit_limit = data.credit_limit
        if data.status is not None:
            customer.status = CustomerStatus(data.status)
        await self._session.flush()
        await self._session.commit()
        await self._session.refresh(customer)
        logger.info("customer_updated", customer_id=str(customer_id))
        return customer

    async def delete(self, customer_id: UUID) -> None:
        customer = await self._repo.get_by_id_not_deleted(customer_id)
        if not customer:
            raise ValueError("customer not found")
        await self._repo.soft_delete(customer)
        await self._session.commit()
        logger.info("customer_deleted", customer_id=str(customer_id))
