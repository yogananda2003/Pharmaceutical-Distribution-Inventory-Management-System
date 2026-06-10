---
name: pharma-distribution-builder
description: Build the Pharmaceutical Distribution & Inventory Management System (FastAPI + React) inside VS Code, one stage at a time with mandatory testing after every stage. Use this skill whenever the user wants to start, continue, or resume building this pharma distribution platform — including any mention of inventory, batch tracking, FEFO allocation, purchase orders, customer orders, the order lifecycle, expiry alerts, or any of its domain modules. Trigger it even if the user only says "let's build the next part," "continue the project," or names a single module (e.g., "do the medicine model"), because every part of this system must follow the same phased, test-gated workflow.
---

# Pharmaceutical Distribution & Inventory Management System — Build Skill

This skill turns the project specification into an executable, **stage-by-stage** build process for VS Code. The single most important rule: **you never advance to the next stage until the current stage's tests are written, run, and passing.** This protects an inventory system where a stock-count bug can mean dispensing expired medicine or overselling a batch.

The full product specification (vision, users, all domain fields, business rules, standards) lives in `references/specification.md`. Read it when you need exact field lists, status enums, or rule details — don't reproduce it from memory.

## How to use this skill

1. Figure out where the user is. Ask (or infer from the repo) which stage was last completed. If starting fresh, begin at Stage 0.
2. Work **one stage at a time.** Announce the stage, do the work, then run the stage's test gate.
3. Do not start the next stage until the user has seen passing tests for the current one. If tests fail, fix and re-run before moving on.
4. Keep a running checklist (TodoList if available) of stages and their test status.

### Resuming a session (how to know where you are)
Don't trust memory across sessions — read the repo. To find the last completed stage:
- Read `PROGRESS.md` at the repo root if it exists (see below). It's the source of truth.
- Otherwise infer: list `backend/app/models/` and `alembic/versions/` to see which entities exist, and run the test suite to see what passes.

Maintain `PROGRESS.md` at the repo root. After each stage's gate goes green, append an entry: stage number, date, what was built, the coverage number, and any deferred TODOs. This is what lets a fresh session pick up cleanly. Never mark a stage complete in `PROGRESS.md` before its gate actually passes.

### Definition of Done (applies to every stage)
A stage is done only when ALL are true: code written across the right Clean Architecture layers; migration created and round-trips; the stage's tests written and passing; the full Test Gate green; `PROGRESS.md` updated; relevant docs touched. "It runs" is not "it's done."

## Working in VS Code

- Assume the project lives in a VS Code workspace. Use the integrated terminal for all commands.
- Backend and frontend are separate folders in one repo (`backend/`, `frontend/`).
- After scaffolding, suggest the user install the recommended VS Code extensions: Python, Pylance, Ruff, Even Better TOML, Docker, Tailwind CSS IntelliSense, ESLint, Prettier. Write these into `.vscode/extensions.json`.
- Provide `.vscode/settings.json` (format-on-save, Ruff as formatter, pytest discovery, correct Python interpreter path) and `.vscode/launch.json` (debug configs for FastAPI via uvicorn and for the Vite dev server) so the user can run and debug from the editor.
- Tests must be runnable both from the terminal and from VS Code's Test Explorer — configure pytest discovery accordingly.

## Project layout

Establish this in Stage 0 and keep to it. A consistent layout is what makes the Clean Architecture boundaries enforceable and the per-feature workflow mechanical.

```
repo/
├── backend/
│   ├── app/
│   │   ├── main.py            # app factory, middleware, exception handlers
│   │   ├── core/              # config, security, logging, db session, deps
│   │   ├── models/            # SQLAlchemy ORM models (one file per entity)
│   │   ├── schemas/           # Pydantic v2 request/response models
│   │   ├── repositories/      # data access, no business rules
│   │   ├── services/          # all business logic lives here
│   │   ├── api/v1/            # routers; thin, no business logic
│   │   └── workers/           # Celery tasks
│   ├── alembic/versions/
│   ├── tests/
│   │   ├── unit/              # services, business rules, validators
│   │   ├── integration/       # repositories, DB
│   │   └── api/               # endpoint, auth, authz
│   ├── pyproject.toml
│   └── conftest.py            # shared fixtures (see test strategy)
├── frontend/
│   └── src/{api,components,pages,hooks,lib}/
├── .vscode/
├── docker-compose.yml
└── PROGRESS.md
```

## Commands (canonical)

Wire these into `pyproject.toml`/`package.json` scripts in Stage 0 so the test gate is one command per check, not a recalled incantation.

- Backend tests + coverage: `pytest --cov=app --cov-report=term-missing --cov-fail-under=80`
- Lint/format/type: `ruff check . && ruff format --check . && mypy app`
- Migrations: `alembic revision --autogenerate -m "<msg>"`, then `alembic upgrade head`; round-trip check: `alembic downgrade -1 && alembic upgrade head`
- Boot API: `uvicorn app.main:app --reload`
- Frontend: `npm run dev`, `npm run test`, `npm run lint`, `tsc --noEmit`
- Worker: `celery -A app.workers worker -l info`

## The Test Gate (run after EVERY stage)

A stage is not "done" until all of the following pass. State the results to the user explicitly before proposing the next stage.

1. **Lint & type check** — `ruff check`, `ruff format --check`, `mypy` (backend); `eslint`, `tsc --noEmit` (frontend).
2. **Migrations apply cleanly** — `alembic upgrade head` runs with no error on a fresh DB, and `alembic downgrade -1` then `upgrade head` round-trips (where a migration was added this stage).
3. **Stage tests pass** — the unit/integration/API tests written for this stage's deliverables, run via `pytest` (or `vitest`/`npm test` for frontend stages).
4. **Coverage holds** — cumulative coverage stays at or above 80%. Report the number.
5. **App boots** — the relevant service starts without error (`uvicorn app.main:app` boots; `npm run dev` serves).

If anything fails, fix it in the current stage. Never carry a red test into the next stage.

## Test strategy (set up once, reuse everywhere)

- **Test database:** run tests against real PostgreSQL, not SQLite — this system relies on Postgres behavior (constraints, transactions, row locking). Spin up a disposable Postgres (the docker-compose service or testcontainers) and point tests at it.
- **Isolation:** wrap each test in a transaction that rolls back, or truncate between tests, so tests don't leak state into each other.
- **Fixtures:** build a small fixture/factory library early (a medicine, a warehouse, a batch with a known expiry, a customer, a user per role). Stage 6 onward depends heavily on being able to seed batches with specific expiry dates and quantities.
- **What each test type owns:** unit tests exercise services with the repository mocked or against a throwaway session (business rules, math, validation); integration tests hit real repositories + DB; API tests go through the HTTP layer with auth and check the response envelope and status codes.
- **Frozen time:** expiry and alert logic must use an injectable/mocked clock so 30/60/90-day thresholds are testable deterministically — never call `datetime.now()` directly in services.

## Correctness traps (where this domain bites)

Call these out and test them explicitly; they're the bugs that matter in a drug-distribution system.

- **Quantity invariant:** for any batch, `quantity_available + quantity_reserved + quantity_damaged` must equal total received minus dispatched/destroyed. Reserving moves quantity from available→reserved (it does not reduce the total). Dispatch moves reserved→out. Test the arithmetic at every transition, and assert the invariant holds after each.
- **Money is Decimal:** use `Decimal`/`NUMERIC`, never float, for prices, discounts, tax, totals, and credit limits. Define rounding rules (e.g. half-up to 2 places) and test them.
- **Idempotent + guarded transitions:** every status/stock transition checks the current state first and is safe to retry. Approving an already-approved order, or dispatching twice, must not double-reserve or double-decrement.
- **Concurrency:** two orders racing for the last units of a batch must not both succeed. Use row-level locking (`SELECT ... FOR UPDATE`) in the allocation path and cover it with a concurrent-access test.
- **Expired-at-boundary:** define whether a batch expiring *today* is sellable, and test the boundary, not just clearly-past dates.
- **Soft delete vs ledger:** business entities may use `deleted_at`; inventory transactions and audit logs are append-only and are never soft-deleted either.

## Build Stages

Each stage below names what to build and what its test gate specifically verifies. Follow the per-feature development workflow (schema → migration → models → schemas → repository → service → endpoint → tests → docs) inside each stage. Detailed field lists and rules for every entity are in `references/specification.md`.

### Stage 0 — Project skeleton & tooling
Scaffold `backend/` (FastAPI, SQLAlchemy 2.0, Alembic, Pydantic v2, structured JSON logging, centralized exception handlers, the standard success/error response envelope) and `frontend/` (React + TypeScript + Vite + Tailwind + TanStack Query + React Hook Form + Zod). Add `docker-compose.yml` (PostgreSQL, Redis), `.vscode/` config, `pyproject.toml`, pre-commit hooks, and a health-check endpoint.
**Test gate:** health endpoint returns the standard success envelope; `docker compose up` brings up Postgres + Redis; lint/type/format all green; an empty `alembic upgrade head` succeeds; frontend dev server boots.

### Stage 1 — Database foundations & base model
Establish the UUID-PK base model with `created_at`/`updated_at`/optional `deleted_at`, the `tenant_id` convention on business entities (present but not yet enforced), audit-column mixins, and the base repository abstraction. No domain tables yet beyond a base.
**Test gate:** base model unit tests (timestamps auto-set, UUID generated); repository CRUD tests against a test database; migration creates the base structure and round-trips.

### Stage 2 — Authentication
Login, logout, refresh token, password reset, email verification. JWT, bcrypt hashing, never store plaintext.
**Test gate:** API tests for the full auth flow (login → access protected route → refresh → logout); password is hashed in DB; expired/invalid tokens rejected; rate limiting on login.

### Stage 3 — User management & RBAC
Users and the five roles (Admin, Inventory Manager, Sales Representative, Customer, Warehouse Staff). Role-based access control dependency.
**Test gate:** authorization tests proving each role can reach only its permitted endpoints; admin user CRUD; audit log entry on user actions.

### Stage 4 — Medicine management
Medicine entity with all spec fields and dosage-form enum.
**Test gate:** CRUD API tests; unique `code` enforced; validation rejects bad dosage_form; service-layer tests for any business rules.

### Stage 5 — Supplier & warehouse management
Suppliers (GST, drug license, etc.) and warehouses, designed for future multi-warehouse.
**Test gate:** CRUD tests for both; required regulatory fields validated; foreign-key integrity.

### Stage 6 — Inventory: batches & transactions (the critical stage)
Inventory batches (quantity_available/reserved/damaged) and the immutable inventory-transaction ledger with all eight transaction types. Enforce **all five inventory rules**: no negative quantity, no selling expired stock, every movement creates a transaction, all updates inside DB transactions, transactions never deleted.
**Test gate:** this stage gets the heaviest testing. Unit tests for each rule (attempt to drive quantity negative → rejected; attempt to allocate expired batch → rejected); every transaction type creates a ledger row; concurrent-update test confirms atomicity; audit history is append-only. Do not proceed until every rule has an explicit passing test.

### Stage 7 — FEFO allocation engine
First-Expiry-First-Out allocation service that reserves across batches by earliest expiry, skipping expired stock.
**Test gate:** allocation tests with multiple batches confirm earliest-expiry consumed first; partial-fill across batches; expired batches excluded; reservation creates ALLOCATION transactions without reducing available-for-sale incorrectly.

### Stage 8 — Purchase management
Purchase orders and items; goods receipt that creates inventory batches (STOCK_IN).
**Test gate:** receiving a PO creates batches and STOCK_IN transactions with correct quantities; PO status transitions tested.

### Stage 9 — Customer management
Customer entity with credit limit, regulatory fields, status.
**Test gate:** CRUD; credit-limit and status validations; unique customer_code.

### Stage 10 — Order management & lifecycle
Customer orders and items, plus the full status lifecycle (DRAFT → PLACED → APPROVED → ALLOCATED → PICKED → PACKED → DISPATCHED → DELIVERED → COMPLETED). Enforce the allocation rule: **order creation must NOT reduce stock; approval reserves; dispatch reduces.**
**Test gate:** state-machine tests reject illegal transitions; creating an order leaves available stock unchanged; approval reserves (RESERVE/ALLOCATION); dispatch reduces (STOCK_OUT); totals/discount/tax computed correctly.

### Stage 11 — Warehouse operations
Picking, packing, dispatch, inventory movement tied to the order lifecycle stages.
**Test gate:** pick/pack/dispatch transitions produce the right transactions and status changes; can't dispatch unallocated orders.

### Stage 12 — Invoice generation
Invoice produced at the correct lifecycle point with line items, tax, totals.
**Test gate:** invoice numbers unique and sequential; amounts reconcile with order items; invoice generated only for eligible statuses.

### Stage 13 — Expiry management & alerts
30/60/90-day expiry alerts via async background jobs (Celery); dashboard data for expired and near-expiry inventory.
**Test gate:** alert logic flags batches at each threshold; Celery task enqueues and runs; expired vs near-expiry correctly categorized.

### Stage 14 — Reporting module
All eight reports (current inventory, batch inventory, expiry, stock movement, purchase, sales, customer, order fulfillment).
**Test gate:** each report endpoint returns correct aggregates against seeded data; pagination/filtering tested.

### Stage 15 — Frontend portals
Customer ordering portal and sales-rep portal (product search, order placement, tracking, invoice download, history). Wire to the API via TanStack Query; forms with React Hook Form + Zod.
**Test gate:** component/integration tests (vitest + React Testing Library) for the order-placement and tracking flows; type check clean; key user flows covered.

### Stage 16 — Production readiness
Monitoring, backups, CI/CD via GitHub Actions, Dockerfiles, final audit-logging review, documentation set (README, ARCHITECTURE, API, DEPLOYMENT, DATABASE).
**Test gate:** CI pipeline runs lint + type + full test suite + coverage on push; Docker images build; full suite green at ≥80% coverage; deployment checklist items all satisfied.

## Non-negotiables across all stages

- Clean Architecture layering: API (no business logic) → Service (all business logic) → Repository (no business rules) → Database.
- Every inventory movement is wrapped in a DB transaction and recorded in the immutable ledger.
- Audit logs and inventory transactions are never deleted.
- Structured JSON logs with request ID, user ID, action, timestamp.
- Standard response envelope on every endpoint.
- Type hints, Pydantic validation, dependency injection, small focused functions; no god classes, no business logic in controllers.

Build every feature as if a real distributor will run thousands of medicines, customers, orders, and inventory transactions through it daily — and as if a missed test could put expired medicine into someone's hands. That's why the gate after every stage is not optional.
