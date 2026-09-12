# PackProof

PackProof helps small and medium European importers collect packaging compliance
documentation from their suppliers — starting with PPWR — instead of chasing it
over email and spreadsheets.

> PackProof helps you collect and organise supplier packaging documentation. It
> does not constitute legal advice and does not guarantee regulatory compliance.

This repository currently implements **FASE 1** of the roadmap: architecture,
database schema and authentication. See [Roadmap](#roadmap) below for what's
next.

## Architecture

Monolith, modular by layer — deliberately not microservices for an MVP this size.

```
Angular SPA  --HTTP/JWT-->  FastAPI monolith  --SQL-->  PostgreSQL (Supabase)
                                  |
                                  +--> Supabase Auth (JWT verification only)
                                  +--> Supabase Storage (documents)
                                  +--> Resend (email)
                                  +--> DocumentExtractionService (pluggable)
```

**Backend layering** (`api -> services -> repositories -> models`):

- `api/` — FastAPI routers. Thin: parse request, call a service, return a schema.
- `core/` — config, DB session, Supabase JWT verification, logging.
- `models/` — SQLAlchemy ORM models (the source of truth for the schema).
- `schemas/` — Pydantic request/response contracts.
- `services/` — business logic (`CompanyService`, `UserService`, and in later
  phases `RequestService`, `DocumentService`, `StatusCalculationService`, ...).
- `repositories/` — DB access. `CompanyScopedRepository` is the base every
  company-owned entity's repository extends, so a `company_id` filter can
  never be forgotten.
- `integrations/` — adapters behind interfaces for external providers:
  `email/` (Resend), `storage/` (Supabase Storage), `extraction/`
  (`DocumentExtractionService` — no real AI/OCR wired up yet, see below).
- `jobs/` — in-process background scheduler (APScheduler, not Celery/Redis —
  see [Why no Celery/Redis](#why-no-celeryredis-for-jobs)).

**Auth model**: PackProof does not implement its own signup/login. The Angular
app talks directly to Supabase Auth and gets a JWT back; the backend's only job
is to verify that JWT (`app/core/security.py`, HS256 against
`SUPABASE_JWT_SECRET`) and mirror the Supabase user into a local `users` row on
first authenticated call. Company onboarding (`POST /api/companies`) is a
separate, explicit step.

**Document extraction**: `DocumentExtractionService` (interface in
`app/integrations/extraction/base.py`) is the only thing the domain talks to
for AI/OCR. Today it's `StubDocumentExtractionService`, which returns no
suggestions — see product rationale below. Swapping in a real LLM/OCR provider
later means writing one new adapter class, nothing else in the codebase
changes.

**Supplier tokens**: a supplier never has an account. Their request link
(`/request/{secureToken}`) uses a cryptographically random token; only its
SHA-256 hash is stored (`compliance_requests.secure_token_hash`), alongside
`token_expires_at` / `token_revoked_at` so links can expire or be revoked.

### Why no Celery/Redis for jobs

The MVP's background work (a handful of reminder emails and extraction retries
per day) doesn't justify a message broker. `app/jobs/scheduler.py` runs an
in-process APScheduler instead — zero extra infrastructure, easy to reason
about, and if volume ever grows enough to matter, only that one module and the
service that enqueues into it need to change.

## Data model

All entities from the product spec are modelled (see `backend/app/models/`):
`Company`, `User`, `Supplier`, `Product`, `PackagingComponent`,
`ComplianceRequest` / `ComplianceRequestProduct`, `SupplierDocument`,
`ExtractedField`, `AuditEvent`.

Notable decisions beyond the spec:

- **`ExtractedField` keeps full provenance** (source document, page, quoted
  text) and is never auto-applied — a human must accept a suggestion before it
  overwrites a real field. See the model's docstring.
- **`Product.status` / `PackagingComponent.status`** (`green`/`orange`/`red`)
  are denormalized caches written by `StatusCalculationService` (FASE 5), not
  editable directly — the packaging component fields are the source of truth.
- **UUID columns use a small custom `GUID` type** (`app/models/base.py`)
  instead of `postgresql.UUID` directly, so the same models work against
  SQLite in tests without a running Postgres instance, while still using
  Postgres' native UUID type in production.
- **`AuditEvent.metadata_json`** uses `JSON().with_variant(JSONB, "postgresql")`
  for the same reason — generic JSON everywhere, JSONB specifically on
  Postgres.

## Requirements

- Python 3.11+
- Node.js 20+ and npm
- Docker + Docker Compose (optional — only needed for local Postgres; you can
  point `DATABASE_URL` at a remote Supabase Postgres instead)
- A Supabase project (Auth + Storage) for anything beyond running the test suite

## Environment variables

Copy `.env.example` to `.env` at the repo root and fill in real values. Never
commit `.env`. See the file itself for what each variable does — the important
ones:

| Variable | Purpose |
| --- | --- |
| `DATABASE_URL` | SQLAlchemy connection string (Postgres) |
| `SUPABASE_JWT_SECRET` | Used to verify Supabase-issued access tokens |
| `SUPABASE_URL` / `SUPABASE_SERVICE_ROLE_KEY` | Supabase Storage access |
| `REMINDER_SCHEDULE_DAYS` | Centralized reminder cadence — never hardcode this elsewhere |
| `RESEND_API_KEY` | Leave empty locally: emails are logged instead of sent |
| `DOCUMENT_EXTRACTION_PROVIDER` | `stub` today; a real provider plugs in behind `DocumentExtractionService` |

The frontend does not use `.env` — Angular config lives in
`frontend/src/environments/environment.ts` (dev) and
`environment.production.ts` (prod build, swapped in via `angular.json`
`fileReplacements`). Fill in `supabaseUrl` / `supabaseAnonKey` /
`apiBaseUrl` there. These are public client-side values (the anon key is
meant to be public), so they aren't secrets the way the backend's
`SUPABASE_JWT_SECRET` is.

## Installation & running

### With Docker Compose (Postgres + backend)

```bash
cp .env.example .env   # fill in Supabase values
docker compose up --build
```

This starts Postgres, runs `alembic upgrade head`, and serves the API on
`http://localhost:8000` with hot reload (the backend directory is mounted).

### Backend, without Docker

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp ../.env.example ../.env   # or export the variables another way
alembic upgrade head
uvicorn app.main:app --reload
```

API docs: `http://localhost:8000/docs`. Health check: `GET /api/health`.

### Frontend

```bash
cd frontend
npm install
npm start   # ng serve, http://localhost:4200
```

## Tests

```bash
cd backend
source .venv/bin/activate
pytest
```

Tests run against an in-memory SQLite database (no Postgres needed) and cover
what matters most for an MVP handling multi-tenant data behind a public
supplier link:

- `test_auth.py` — Supabase JWT verification: missing/garbage/expired tokens,
  wrong signing secret, wrong audience, and that a local `users` row is
  created lazily and idempotently.
- `test_company_isolation.py` — a user can't see another company's data, can't
  onboard twice, and `CompanyScopedRepository` refuses cross-tenant reads even
  if an endpoint forgot to filter.
- `test_security_tokens.py` — supplier tokens are unique, long enough, and
  only their hash is ever compared/stored.

Frontend: `cd frontend && npm test` runs the Angular/Karma unit tests
(requires a Chromium binary; see `frontend/README.md` if you need to point
Karma at a specific browser).

## Migrations

[Alembic](https://alembic.sqlalchemy.org/), driven from `backend/alembic/`.

```bash
cd backend
alembic upgrade head                          # apply
alembic revision --autogenerate -m "message"  # generate a new one after model changes
alembic downgrade -1                          # roll back one
```

`0001_initial_schema.py` creates the full FASE 1 schema (all tables and enum
types). Review autogenerated migrations before applying — autogenerate can
miss enum value changes and some constraint renames.

## Project structure

```
backend/
  app/
    api/            # FastAPI routers + dependencies (auth, DB session)
    core/           # config, database, security (JWT), logging
    models/         # SQLAlchemy models
    schemas/        # Pydantic schemas
    repositories/   # DB access, company-scoped by default
    services/       # business logic
    integrations/   # email / storage / extraction adapters behind interfaces
    jobs/           # in-process background scheduler
  alembic/          # migrations
  tests/
frontend/
  src/app/
    core/           # auth service, HTTP interceptor, route guard, API client
    features/       # landing, auth (login/signup), dashboard
    shared/         # reserved for cross-feature UI (empty for now)
  src/environments/
docker-compose.yml
.env.example
```

## Roadmap

- **FASE 1 — done**: architecture, database schema, Supabase JWT auth, company
  onboarding, dashboard shell.
- **FASE 2**: Products + Suppliers CRUD.
- **FASE 3**: Compliance requests + secure supplier link (`/request/{token}`).
- **FASE 4**: Document uploads (Supabase Storage, upload validation).
- **FASE 5**: `StatusCalculationService` and the real dashboard (completion
  percentages, missing-fields counts).
- **FASE 6**: Resend email templates + centralized reminder scheduling.
- **FASE 7**: A real `DocumentExtractionService` implementation behind the
  existing interface, plus the accept/conflict UI for `ExtractedField`.
- **FASE 8**: Polish, broader test coverage, deployment readiness.

Explicitly out of scope for the MVP (see the product brief): Digital Product
Passport, EUDR, full REACH, a supplier marketplace/network, ERP or
Shopify/WooCommerce/Amazon integrations, multi-company-per-user, complex
billing, translations, blockchain. The data model doesn't block adding these
later, but none of them are being built now.
