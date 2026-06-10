# Pharmaceutical Distribution & Inventory Management System

Enterprise, SaaS-ready platform for pharmaceutical distribution: inventory & batch tracking,
expiry management, purchasing, sales, customer/sales-rep portals, order processing with FEFO
stock allocation, invoicing, and reporting.

See [`specification.md`](specification.md) for the full domain spec and [`PROGRESS.md`](PROGRESS.md)
for what's been built so far.

## Stack
- **Backend:** Python 3.12+, FastAPI, SQLAlchemy 2.0 (async), Alembic, Pydantic v2, PostgreSQL, Redis, Celery, JWT
- **Frontend:** React, TypeScript, Vite, Tailwind CSS v4, TanStack Query, React Hook Form, Zod
- **Infra:** Docker Compose (Postgres + Redis), GitHub Actions, Nginx

## Getting started

### Backend
```powershell
cd backend
uv venv .venv
uv pip install -e ".[dev]"
copy .env.example .env       # then edit DATABASE_URL etc.
copy .env.test.example .env.test
.venv\Scripts\python -m alembic upgrade head
.venv\Scripts\python -m uvicorn app.main:app --reload
```
API docs at http://localhost:8000/docs, health check at `/api/v1/health`.

### Frontend
```powershell
cd frontend
npm install
copy .env.example .env
npm run dev
```
Serves at http://localhost:5173.

### Database & cache
Either run `docker compose up -d` (Postgres + Redis), or point `DATABASE_URL` / `REDIS_URL` in
`.env` at locally installed services. Create `pharma_dev` and `pharma_test` databases before
running the app or the test suite.

## Commands

| Purpose | Command |
|---|---|
| Backend tests + coverage | `pytest --cov=app --cov-report=term-missing --cov-fail-under=80` |
| Backend lint/format/type | `ruff check . && ruff format --check . && mypy app` |
| New migration | `alembic revision --autogenerate -m "<msg>"` |
| Apply migrations | `alembic upgrade head` |
| Migration round-trip check | `alembic downgrade -1 && alembic upgrade head` |
| Run API | `uvicorn app.main:app --reload` |
| Run worker | `celery -A app.workers worker -l info` |
| Frontend dev server | `npm run dev` |
| Frontend tests | `npm run test` |
| Frontend lint / type check | `npm run lint` / `tsc --noEmit` |

## Project layout
```
backend/app/{core,models,schemas,repositories,services,api/v1,workers}
backend/{alembic,tests}
frontend/src/{api,components,pages,hooks,lib}
```

Clean Architecture: **API** (no business logic) → **Service** (business rules) →
**Repository** (data access) → **Database**.
