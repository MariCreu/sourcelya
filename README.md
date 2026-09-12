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
                                  +--> Supabase Auth (JWKS verification only)
                                  +--> Supabase Storage (documents)
                                  +--> Resend (email)
                                  +--> DocumentExtractionService (pluggable)

Supabase Cron / pg_cron  --HTTP-->  POST /internal/jobs/process-reminders
```

**Backend layering** (`api -> services -> repositories -> models`):

- `api/` — FastAPI routers. Thin: parse request, call a service, return a schema.
- `core/` — config, DB session, Supabase JWT verification, logging.
- `models/` — SQLAlchemy ORM models (the source of truth for the schema).
- `domain/` — pure-Python domain constants (`PackagingType`, `ComplianceStatus`)
  that are validated in the application layer rather than enforced by a
  native Postgres type — see [PostgreSQL enums](#postgresql-enums) below.
- `schemas/` — Pydantic request/response contracts.
- `services/` — business logic (`CompanyService`, `UserService`,
  `StatusCalculationService`, `ReminderService`, and in later phases
  `RequestService`, `DocumentService`, ...).
- `repositories/` — DB access. `CompanyScopedRepository` is the base every
  company-owned entity's repository extends, so a `company_id` filter can
  never be forgotten.
- `integrations/` — adapters behind interfaces for external providers:
  `email/` (Resend), `storage/` (Supabase Storage), `extraction/`
  (`DocumentExtractionService` — no real AI/OCR wired up yet, see below).

**Auth model**: PackProof does not implement its own signup/login. The Angular
app talks directly to Supabase Auth and gets a JWT back; the backend's only job
is to verify that JWT (`app/core/security.py`) and mirror the Supabase user
into a local `users` row on first authenticated call. Company onboarding
(`POST /api/companies`) is a separate, explicit step. See
[JWT verification](#jwt-verification) below for how the token itself is checked.

**Document extraction**: `DocumentExtractionService` (interface in
`app/integrations/extraction/base.py`) is the only thing the domain talks to
for AI/OCR. Today it's `StubDocumentExtractionService`, which returns no
suggestions — see product rationale below. Swapping in a real LLM/OCR provider
later means writing one new adapter class, nothing else in the codebase
changes.

### JWT verification

`app/core/security.py` supports two verifiers, selected by
`SUPABASE_JWT_STRATEGY`:

- **`jwks` (default, production)** — Supabase's current recommended approach:
  asymmetric signing keys, verified against the project's JWKS endpoint
  (`https://<project>.supabase.co/auth/v1/.well-known/jwks.json`) via
  `PyJWKClient`. Validates the signature (against the key matching the
  token's `kid`), `exp`, `iss`, `aud`, and requires `sub` to be present.
- **`hs256`** — a shared secret (`SUPABASE_JWT_SECRET`), only for local/offline
  dev or CI that can't reach a real Supabase project. The strategy defaults to
  `jwks`, not `hs256`, so forgetting to set the variable in production fails
  towards the stronger check instead of silently accepting a weak one.

Both verifiers pass an explicit `algorithms=[...]` allowlist to `jwt.decode`.
PyJWT then refuses to verify a token whose header claims a different
algorithm — the algorithm is never taken dynamically from the token itself,
which is what stops the classic "alg confusion" attack (e.g. resubmitting an
RS256/ES256 token with `alg: HS256`, using the public key as an HMAC secret).
`tests/test_auth_jwks.py` proves this against a real local JWKS HTTP endpoint
and a real EC keypair, not a mocked signature check.

**Supplier tokens** (design decision, applies from FASE 3 onward when
`ComplianceRequest` is introduced): a supplier never has an account. Their
request link uses a cryptographically random token; only its SHA-256 hash
would ever be stored, alongside an expiry and a revoked-at timestamp, so
links can expire or be revoked without ever persisting a usable token in the
database. `generate_secure_token` / `hash_token` in `app/core/security.py`
already implement and test this.

### Why not an in-process scheduler for jobs

Background work (reminders, extraction retries) is **not** driven by a
scheduler running inside the FastAPI process (e.g. APScheduler). With
multiple API instances or workers, an in-process scheduler either double-runs
jobs or needs its own leader-election machinery, and it only runs while that
one process happens to be alive.

Instead: `ReminderService` (`app/services/reminder_service.py`) holds the
business logic, and `POST /internal/jobs/process-reminders`
(`app/api/v1/internal.py`) is a plain, idempotent HTTP endpoint — protected by
a shared secret (`INTERNAL_JOBS_SECRET`), since it's called by a scheduler,
not a logged-in user. In production, **Supabase Cron / pg_cron** calls this
endpoint on a schedule; locally or in tests, it's called manually or from a
test client. Nothing here needs Celery/Redis either — see
`tests/test_internal_jobs.py`.

FASE 1 ships the endpoint and the service shell but not real reminder logic:
`ComplianceRequest` (the thing being reminded about) doesn't exist until
FASE 3. `ReminderService`'s docstring documents the intended idempotency
mechanism (a `reminder_count` guard on the update, so a duplicate or
overlapping cron invocation can never send the same interval's reminder
twice) so FASE 6 implements it against an already-decided shape instead of
inventing one under time pressure.

### PostgreSQL enums

Native Postgres `ENUM` types are reserved for values that are genuinely
closed and stable. Fields whose set of values is likely to grow while the
product is still being validated — `packaging_type` today; `document_type`
and extraction `entity_type` once FASE 4/7 add those tables — are stored as
plain `VARCHAR` and validated in Python (`app/domain/enums.py`, Pydantic
schemas) instead. A native enum needs an `ALTER TYPE ... ADD VALUE`
migration for every new value; a `VARCHAR` needs a one-line code change and
no migration. See `app/domain/enums.py` for the full rationale.

### Computed status, not cached

`Product` and `PackagingComponent` have no `status` column.
`StatusCalculationService` (`app/services/status_calculation_service.py`)
computes the green/orange/red status on read, from the packaging component
fields. With the small number of records the MVP will have during
validation, this avoids an entire class of bugs where a cached value drifts
from the real data. If usage later shows this is a real performance problem,
that's the point to add denormalization or a materialized view — not before.

## Data model

FASE 1 keeps the schema intentionally minimal — just what's needed for
company/user auth plus the next phase's core catalog, so FASE 2 doesn't
immediately redo the model. See `backend/app/models/`:

- **`Company`**, **`User`** — auth/tenancy. A `User.company_id` is set once,
  via `POST /api/companies` (no multi-company-per-user in the MVP).
- **`Supplier`**, **`Product`**, **`PackagingComponent`** — the FASE 2 catalog
  entities, included now since they're immediate next-phase work, not
  speculative.

Deliberately **not** modelled yet (each ships in its own phase, per the
roadmap, rather than being built ahead of the feature that needs it):
`ComplianceRequest` / `ComplianceRequestProduct` (FASE 3), `SupplierDocument`
(FASE 4), `ExtractedField` (FASE 7), `AuditEvent` (incrementally, as the
actions worth auditing get real endpoints). When they're added, they keep
the design decisions already agreed for them — hashed/expirable/revocable
supplier tokens, full extraction provenance (document/page/quoted text),
`VARCHAR` instead of native enums for evolving fields.

Notable implementation detail: **UUID columns use a small custom `GUID`
type** (`app/models/base.py`) instead of `postgresql.UUID` directly, so the
same models work against SQLite in tests without a running Postgres
instance, while still using Postgres' native UUID type in production. This
matters in practice, not just in theory: `postgresql.UUID` compiles into an
untyped column on SQLite, which gets `NUMERIC` affinity and silently
corrupts any digit-only UUID (exactly what handwritten test fixtures tend to
use).

## Requirements

- Python 3.11+
- Node.js 20+ and npm
- Docker + Docker Compose (optional — only needed for local Postgres; you can
  point `DATABASE_URL` at a remote Supabase Postgres instead)
- A Supabase project (Auth + Storage) for anything beyond running the test
  suite — or set `SUPABASE_JWT_STRATEGY=hs256` to develop against the API
  without one (see below)

## Environment variables

Copy `.env.example` to `.env` at the repo root and fill in real values. Never
commit `.env`. See the file itself for what each variable does — the important
ones:

| Variable | Purpose |
| --- | --- |
| `DATABASE_URL` | SQLAlchemy connection string (Postgres) |
| `SUPABASE_JWT_STRATEGY` | `jwks` (production/default) or `hs256` (local/offline dev only) |
| `SUPABASE_URL` | Used to derive the JWKS URL/issuer, and for Storage access |
| `SUPABASE_JWT_SECRET` | Only read when `SUPABASE_JWT_STRATEGY=hs256` |
| `INTERNAL_JOBS_SECRET` | Required by `POST /internal/jobs/process-reminders` |
| `REMINDER_SCHEDULE_DAYS` | Centralized reminder cadence — never hardcode this elsewhere |
| `RESEND_API_KEY` | Leave empty locally: emails are logged instead of sent |
| `DOCUMENT_EXTRACTION_PROVIDER` | `stub` today; a real provider plugs in behind `DocumentExtractionService` |

If you don't have a Supabase project yet, set `SUPABASE_JWT_STRATEGY=hs256`
and `SUPABASE_JWT_SECRET` to any value locally — the frontend won't be able
to sign real users in via Supabase Auth without a project either way, but
this lets you exercise the API directly (mint a token the same way
`tests/conftest.py` does) without one.

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
cp .env.example .env   # fill in Supabase values, or use SUPABASE_JWT_STRATEGY=hs256
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

- `test_auth.py` — the HS256 dev/test verifier: missing/garbage/expired
  tokens, wrong signing secret, wrong audience, missing subject, and that a
  local `users` row is created lazily and idempotently.
- `test_auth_jwks.py` — the production JWKS verifier against a **real**
  local JWKS HTTP server and a real EC keypair (not a mocked signature
  check): valid token, expired, wrong issuer/audience, missing subject,
  unknown key id, and — the important one — a genuinely valid ES256 token
  rejected outright when the verifier is only configured to trust RS256.
- `test_company_isolation.py` — a user can't see another company's data, can't
  onboard twice, and `CompanyScopedRepository` refuses cross-tenant reads even
  if an endpoint forgot to filter.
- `test_security_tokens.py` — supplier tokens are unique, long enough, and
  only their hash is ever compared/stored.
- `test_internal_jobs.py` — the reminders job endpoint requires its shared
  secret and is safe to call repeatedly.
- `test_status_calculation.py` — component/product status is derived
  correctly from packaging component completeness.

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

`0001_initial_schema.py` creates the FASE 1 schema: `users`, `companies`,
`suppliers`, `products`, `packaging_components` — no native Postgres enum
types (see [PostgreSQL enums](#postgresql-enums)). Review autogenerated
migrations before applying — autogenerate can miss some constraint renames.

## Project structure

```
backend/
  app/
    api/            # FastAPI routers + dependencies (auth, DB session)
    core/           # config, database, security (JWT), logging
    models/         # SQLAlchemy models
    domain/         # pure-Python domain enums (not DB-mapped)
    schemas/        # Pydantic schemas
    repositories/   # DB access, company-scoped by default
    services/       # business logic
    integrations/   # email / storage / extraction adapters behind interfaces
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

- **FASE 1 — done**: architecture, minimal database schema, Supabase JWKS
  auth, company onboarding, dashboard shell, internal-jobs endpoint shape.
- **FASE 2**: Products + Suppliers CRUD (the API/UI layer on top of the
  models already in FASE 1).
- **FASE 3**: `ComplianceRequest` / `ComplianceRequestProduct` + secure
  supplier link (`/request/{token}`).
- **FASE 4**: `SupplierDocument` + document uploads (Supabase Storage,
  upload validation).
- **FASE 5**: The real dashboard (completion percentages, missing-fields
  counts) built on `StatusCalculationService`.
- **FASE 6**: Resend email templates + real `ReminderService` logic behind
  the `POST /internal/jobs/process-reminders` shape already in place.
- **FASE 7**: `ExtractedField` + a real `DocumentExtractionService`
  implementation behind the existing interface, plus the accept/conflict UI.
- **FASE 8**: Polish, broader test coverage, deployment readiness.

Explicitly out of scope for the MVP (see the product brief): Digital Product
Passport, EUDR, full REACH, a supplier marketplace/network, ERP or
Shopify/WooCommerce/Amazon integrations, multi-company-per-user, complex
billing, translations, blockchain. The data model doesn't block adding these
later, but none of them are being built now.
