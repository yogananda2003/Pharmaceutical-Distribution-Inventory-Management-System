# Build Progress

## Stage 1 — Database foundations & base model
- Date: 2026-06-09
- Built: `app/models/base.py` — `UUIDPrimaryKeyMixin` (Python-side `uuid.uuid4()` default, wrapped
  for SQLAlchemy's context-sensitive callable protocol), `TimestampMixin` (created_at/updated_at
  with server_default+onupdate), `SoftDeleteMixin` (deleted_at nullable), `TenantMixin`
  (tenant_id nullable+indexed, unenforced), `BaseEntity` (abstract, combines all), `TenantedEntity`
  (abstract, adds TenantMixin). `app/repositories/base.py` — generic `BaseRepository[ModelT]`
  with `get_by_id`, `list` (excludes soft-deleted, ordered by created_at), `add`, `delete`,
  `soft_delete`. `alembic/versions/0001_base_foundation.py` — empty migration (no domain tables
  yet; abstract mixins produce no tables).
- Test gate:
  - Lint/format/type: `ruff check`, `ruff format --check`, `mypy app` — all green.
  - Unit tests (no DB): 7/7 passing — UUID PK config, unique ID generation (each call returns
    different UUID via Python-side default), audit timestamp column config, soft-delete column,
    TenantMixin inheritance chain, tenant_id column presence/nullability verified via mapper
    inspection.
  - Integration tests: 7/7 passing — add, get_by_id hit/miss, list excludes soft-deleted,
    soft_delete sets deleted_at, timestamps set on insert, UUID uniqueness across 10 entities.
  - Migration: `alembic upgrade head` ✅ · downgrade -1 → upgrade head round-trip ✅



Source of truth for which stage is complete. Append an entry only after that stage's full test gate is green.

## Stage 3 — User Management & RBAC
- Date: 2026-06-10
- Built:
  - `app/schemas/user.py` — UserRead, UserUpdate (admin), UserUpdateMe (self)
  - `app/services/user.py` — get_me, update_me (duplicate-email check), list_users, get_user, update_user, delete_user (soft)
  - `app/api/v1/users.py` — GET/PUT /users/me (any authed user); GET /users, GET /users/{id}, PUT /users/{id}, DELETE /users/{id} (admin-only via require_roles)
- Test gate:
  - Lint/format/type: all green (30 files)
  - API tests: 13/13 — get_me (profile correct, auth required), update_me (email change, dup email rejected), list_users (admin OK, non-admin 403), get_user (admin OK, 404 for unknown), role change, deactivate, soft delete, non-admin delete blocked, all 4 non-admin roles get 403 on admin endpoints
  - Full suite: 54/54 passing
- Notes:
  - HTTPBearer returns 401 (no credentials), not 403 — 403 is role-insufficient only
  - Role is baked into the JWT at login time; after a DB role change the user must re-login to get a token reflecting the new role

## Stage 2 — Authentication (JWT + refresh tokens)
- Date: 2026-06-10
- Built:
  - `app/models/user.py` — User (TenantedEntity, UserRole StrEnum, bcrypt password_hash, is_active/is_verified)
  - `app/models/refresh_token.py` — RefreshToken (SHA-256 hash of raw JWT, expires_at, revoked_at)
  - `alembic/versions/c5e7141603fd_auth_tables.py` — creates users + refresh_tokens; downgrade drops user_role enum explicitly
  - `app/core/security.py` — bcrypt hash/verify, SHA-256 token hashing, JWT access/refresh create/decode; refresh tokens include jti=uuid4() to prevent hash collisions within the same second
  - `app/schemas/auth.py` — LoginRequest, RegisterRequest (>=8 char password validator), RefreshRequest, LogoutRequest, LoginResponse
  - `app/repositories/user.py` — get_by_email, get_by_id_active, create, update_password, set_verified
  - `app/repositories/refresh_token.py` — create, get_by_hash (non-revoked + non-expired filter), revoke, revoke_all_for_user
  - `app/services/auth.py` — login, logout, refresh (token rotation), register, logout_all
  - `app/core/deps.py` — get_current_user dependency, CurrentUser Annotated alias, require_roles factory
  - `app/api/v1/auth.py` — POST /login, /refresh, /logout, /register
- Test gate:
  - Lint/format/type: ruff check, ruff format --check, mypy app — all green (27 files)
  - Unit: 13/13 — bcrypt hash/verify, token hashing determinism, JWT create/decode, tamper/type/expiry rejection
  - API integration: 12/12 — register (success, dup email, short password), login (success, wrong pw, unknown email), hashed password stored as bcrypt, refresh rotation, replay attack rejected, logout invalidates token
  - Migration round-trip: downgrade -1 → upgrade head ✅
  - Full suite: 41/41 passing
- Notes:
  - jti=str(uuid.uuid4()) in refresh JWT is required: python-jose encodes iat/exp as integer seconds, so same-user tokens issued within the same second are byte-identical → same SHA-256 hash → unique constraint violation
  - conftest._prepare_database must do drop_all before create_all (stale data from a crashed run breaks unique constraints) and must import app.models first so Base.metadata knows about all tables
  - enum.StrEnum (Python 3.11+) replaces the str+enum.Enum pattern

## Stage 0 — Project skeleton & tooling
- Date: 2026-06-08
- Built: `backend/` (FastAPI app factory, structured JSON logging with request-id/user-id context,
  centralized exception handlers, standard `{success, data}` / `{success, message}` envelope,
  Pydantic v2 settings, async SQLAlchemy 2.0 engine/session, Alembic wired for async autogenerate,
  health endpoint). `frontend/` (React 19 + TS + Vite + Tailwind v4 + TanStack Query + React Hook
  Form + Zod + React Router + axios, vitest + RTL). `docker-compose.yml` (Postgres 16, Redis 7),
  `.vscode/` (settings, launch, extensions), `.pre-commit-config.yaml`, `pyproject.toml` with
  ruff/mypy/pytest config.
- Test gate:
  - Backend lint/format/type: `ruff check`, `ruff format --check`, `mypy app` — all green.
  - Frontend lint/type: `eslint .`, `tsc -b` — all green.
  - Frontend tests: `vitest run` — 2/2 passing (Dashboard renders title + shows health status).
  - App boots: `uvicorn app.main:app` serves `/api/v1/health` → `{"success":true,"data":{"status":"ok"}}`
    with `X-Request-ID` header; `npm run dev` serves on :5173.
  - Migrations: pending — see TODO below (no models yet, so nothing to autogenerate).
  - Backend API/integration tests against Postgres: pending — see TODO.
- Gate fully passed on 2026-06-09 after DB credentials were provided.
- Coverage: 94% across 16 tests (2 API + 7 integration + 7 unit).
- Notes:
  - `@` in password URL-encoded as `%40` in DATABASE_URL; alembic `set_main_option` needs
    `%.replace("%", "%%")` escape to avoid configparser interpolation errors.
  - asyncpg on Windows IocpProactor requires all async fixtures AND tests to use the same
    session-scoped event loop; solved via `loop_scope="session"` on all `@pytest_asyncio.fixture`
    decorators + `pytestmark = pytest.mark.asyncio(loop_scope="session")` in test modules.
  - Engine + sessionmaker are lazy (`@lru_cache` factory functions) so tests can inject the
    test DATABASE_URL via `pytest_configure` before the first connection is established.
- Deferred: Redis/Celery wiring to Stage 13 (no Docker locally; docker-compose for CI/future).
