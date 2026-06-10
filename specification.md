# Full Specification — Pharmaceutical Distribution & Inventory Management System

This is the authoritative reference for exact fields, enums, rules, and standards. The SKILL.md drives *when* to build things; this file says *what* the things contain.

## Table of contents
- Vision & users
- Core business workflow
- Technology stack
- Architecture & multi-tenancy
- Domain entities (fields)
- Inventory rules & transaction types
- FEFO
- Order lifecycle & allocation rule
- Expiry alerts
- Reports
- API / DB / security / logging / testing standards
- Per-feature dev workflow

## Vision & users
Enterprise, SaaS-ready pharmaceutical distribution platform: inventory, batch tracking, expiry, purchasing, sales, customer & sales-rep portals, order processing, stock allocation, invoicing, reporting. Designed to later support multiple distributors and warehouses.

Users and responsibilities:
- **System Administrator** — user/role management, system configuration, reports, inventory oversight.
- **Inventory Manager** — medicine management, batch management, stock receiving, stock adjustments, expiry tracking.
- **Sales Representative** — customer management, order creation, customer visits, product availability checks, order tracking.
- **Customer** — product search, order placement, order tracking, invoice downloads, purchase history.
- **Warehouse Staff** — picking, packing, dispatch, inventory movement.

## Core business workflow
Supplier → Purchase Order → Goods Receipt → Inventory Batch Creation → Available Inventory → Customer Order → Order Approval → Stock Allocation → Invoice Generation → Dispatch → Delivery.

## Technology stack
- **Backend:** Python 3.12+, FastAPI, SQLAlchemy 2.0, Alembic, Pydantic v2, PostgreSQL, Redis, Celery, JWT auth.
- **Frontend:** React, TypeScript, Vite, Tailwind CSS, TanStack Query, React Hook Form, Zod.
- **Infrastructure:** Docker, Docker Compose, Nginx, GitHub Actions, AWS, Terraform (future).

## Architecture & multi-tenancy
Clean Architecture, four layers:
- **API Layer** — request handling, authentication, authorization, response formatting. No business logic.
- **Service Layer** — business rules, inventory calculations, order workflows, validation. All business logic here.
- **Repository Layer** — database operations, query abstraction. No business rules.
- **Database Layer** — persistence, relationships, constraints.

Multi-tenant readiness: include `tenant_id` on all applicable business entities even before multi-tenant is enabled, so future migration is possible.

## Domain entities (fields)

### Medicine
id, code, name, generic_name, manufacturer, dosage, strength, dosage_form, unit_type, description, status, created_at, updated_at.
Dosage form examples: Tablet, Capsule, Injection, Syrup, Ointment, Drops, Powder.

### Inventory Batch
id, medicine_id, batch_number, manufacturing_date, expiry_date, quantity_available, quantity_reserved, quantity_damaged, warehouse_id, status.
Inventory is **always** tracked by batch — never only at medicine level.

### Inventory Transaction (immutable ledger)
id, batch_id, transaction_type, quantity, reference_number, remarks, created_by, created_at.

### Supplier
supplier_code, supplier_name, gst_number, drug_license_number, address, contact_person, email, phone.

### Warehouse
warehouse_code, warehouse_name, address, contact_details. (Designed for multiple warehouses later.)

### Customer
customer_code, business_name, contact_person, email, phone, gst_number, drug_license_number, address, credit_limit, status.

### Sales Representative
employee_code, name, email, phone, territory, manager_id.

### Customer Order
order_number, customer_id, sales_rep_id, order_date, status, total_amount.

### Order Item
medicine_id, quantity, unit_price, discount, tax_amount.

### Purchase Order
po_number, supplier_id, order_date, status.

### Purchase Item
medicine_id, quantity, purchase_price.

## Inventory rules & transaction types

Transaction types: STOCK_IN, STOCK_OUT, ADJUSTMENT, RETURN, DAMAGE, TRANSFER, ALLOCATION, RELEASE.

Five rules (every one needs an explicit passing test in Stage 6):
1. Quantity cannot become negative.
2. Expired inventory cannot be sold.
3. Inventory movements must always generate transactions.
4. Inventory updates must occur within database transactions.
5. Maintain complete audit history — never delete inventory transactions.

## FEFO
First Expiry First Out: allocation prioritizes the earliest expiry date first.

## Order lifecycle & allocation rule
Lifecycle: DRAFT → PLACED → APPROVED → ALLOCATED → PICKED → PACKED → DISPATCHED → DELIVERED → COMPLETED.

Allocation rule (prevents inventory inconsistency):
- Creating an order must **NOT** reduce stock.
- Approval must **reserve** stock.
- Dispatch must **reduce** stock.

## Expiry alerts
Generate alerts at 30, 60, and 90 days before expiry. Dashboard shows expired inventory and near-expiry inventory.

## Reports
Current Inventory, Batch Inventory, Expiry, Stock Movement, Purchase, Sales, Customer, Order Fulfillment.

## Notification system (future)
Email, SMS, WhatsApp via asynchronous background jobs.

## API standards
REST conventions, versioned APIs (e.g. `/api/v1/medicines`, `/api/v1/orders`, `/api/v1/customers`).
Standard response envelope:
- Success: `{ "success": true, "data": {} }`
- Error: `{ "success": false, "message": "Validation Error" }`

## Database standards
PostgreSQL. UUID primary keys, foreign keys, indexes, constraints, audit columns. Every table has id, created_at, updated_at; optional deleted_at.

## Security standards
JWT auth, RBAC, bcrypt password hashing, API rate limiting, input validation, SQL injection protection, CORS configuration. Never store plaintext passwords.

## Audit logging
Track login activity, order creation, inventory changes, stock adjustments, user actions. Never delete audit logs.

## Error handling
Centralized exception handlers, structured responses, never expose internal stack traces.

## Logging standards
Structured JSON logs with request ID, user ID, action, timestamp.

## Testing requirements
- Unit tests: services, business rules, validators.
- Integration tests: repositories, database interactions.
- API tests: endpoints, authentication, authorization.
- Target: minimum 80% coverage.

## Code quality standards
Type hints, Pydantic validation, dependency injection, small focused functions, reusable services. Avoid god classes, business logic in controllers, duplicate code.

## Per-feature development workflow (inside every stage)
1. Define requirements
2. Create database schema
3. Create migration
4. Create models
5. Create schemas
6. Create repository
7. Create service
8. Create API endpoint
9. Create tests
10. Update documentation

No shortcuts.

## Documentation set
README.md, ARCHITECTURE.md, API.md, DEPLOYMENT.md, DATABASE.md.

## Production readiness checklist
Authentication, authorization, logging, monitoring, error handling, automated tests, Docker support, CI/CD pipeline, database migrations, backups, audit logging.
