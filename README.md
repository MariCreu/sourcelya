# Sourcelya

**Supplier compliance, without the chasing.**

Sourcelya helps companies obtain, structure, verify and maintain the
documentation and evidence they need from their suppliers. The product's
marketing copy (tagline, one-line explanation) lives in one place —
`frontend/src/app/core/brand.ts` — and is explicitly not final; see
[Product positioning](#product-positioning) below.

> Sourcelya helps you collect and organise supplier documentation. It does
> not constitute legal advice and does not guarantee regulatory compliance.

This repository currently implements **FASE 1–3** of the roadmap:
architecture, database schema, authentication, the Suppliers/Products
catalog, and now the first genuinely critical flow — a company sending a
supplier a secure, no-login-required link to fill in packaging data. See
[Roadmap](#roadmap) below for what's next.

## Product positioning

Sourcelya is **not** a PPWR-only tool. PPWR (packaging waste regulation) is
the first market wedge — the concrete, narrow problem that gets a first
customer to pay — not the product's ceiling. The underlying flow is generic:

```
Buyer -> Supplier -> Request -> Documents -> Structured data -> Missing information
```

which is why the domain model uses generic names —
`ComplianceRequest`, `SupplierDocument`, `PackagingComponent`, `ExtractedField`
— instead of regulation-specific ones (`PPWRRequest`, `PPWRDocument`, ...).
The regulation is meant to be a layer on top of this flow, not something
baked into the architecture. Concretely, that means: no code in this
repository should assume PPWR is the only compliance obligation a request or
document can be about, even though PPWR is the only one the MVP's UI/copy
talks about today.

Explicitly **not** being built now, even though the architecture shouldn't
block them later: Digital Product Passport (DPP), EUDR, REACH, a supplier
network/marketplace, ecommerce integrations, advanced billing. See
[Roadmap](#roadmap) for what actually ships in each phase.

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

**Auth model**: Sourcelya does not implement its own signup/login. The Angular
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

**Supplier tokens** (implemented in FASE 3): a supplier never has an
account. Their request link (`/request/{token}`) uses a cryptographically
random token (`generate_secure_token`); only its SHA-256 hash
(`hash_token`) is ever stored on `ComplianceRequest.secure_token_hash`,
alongside `token_expires_at` and `token_revoked_at`, so links can expire or
be revoked without a usable token ever existing in the database. Every
public-portal request re-derives the `ComplianceRequest` from the token's
hash (`PublicRequestService._resolve`) — there is no code path that lets a
request or company id be passed in directly instead. See [Public supplier
portal](#public-supplier-portal) below for the full request lifecycle and
the specific attacks this is tested against.

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

### Domains

The public target is **https://sourcelya.com**. Nothing needs deploying or
pointing at DNS yet, but the repository is already laid out as three
independently deployable units, one per subdomain:

- **`sourcelya.com`** — public marketing/SEO site. `web/`: plain static
  HTML/CSS/JS, no build step, no auth. See `web/README.md` for why this is
  a separate static site rather than an Angular route (short version:
  indexability and performance beat the convenience of one codebase for a
  handful of marketing pages).
- **`app.sourcelya.com`** — the authenticated application. `frontend/`: the
  Angular SPA (`/login`, `/signup`, `/dashboard`, `/suppliers`,
  `/products`). Its `/` route just redirects to `/login` — it has no
  marketing content of its own anymore, to avoid two different landing
  pages for the same product living on two domains.
- **`api.sourcelya.com`** — the FastAPI backend, already a separate
  deployable unit (`backend/`).

`FRONTEND_BASE_URL` (backend CORS) and `apiBaseUrl`
(`frontend/src/environments/environment.production.ts`) are the two
settings that would need to point at the real subdomains once this is
actually deployed — see [Environment variables](#environment-variables).

## Public landing site (sourcelya.com)

`web/` is a small static site, in Spanish (`/es/`, default — Spain is the
first go-to-market market) and English (`/en/`, root `/` redirects to
`/es/`): one page per locale (six sections — hero, problem, how it works,
who it's for, PPWR-as-first-focus with the legal disclaimer, final CTA),
`robots.txt`, a bilingual `sitemap.xml` with hreflang alternates, and an
analytics abstraction with no provider wired up yet.

Content is centralized, not duplicated per page or hardcoded per component:
`web/content/es.json` / `en.json` hold every string, `web/templates/`
holds the (single, shared) HTML structure, and `web/build.js` — about 100
lines, zero npm dependencies — renders one into the other. See
[Why not an in-process scheduler](#why-not-an-in-process-scheduler-for-jobs)
for the general pattern of "ship the simple thing now, the complex thing
if/when it's actually needed" that also applies here (no framework, no
build pipeline beyond that one script); `web/README.md` covers the
SSR-vs-static tradeoff and the i18n approach in full.

Measured locally with Lighthouse against the static file server (Chromium,
headless, mobile-equivalent throttling as configured by Lighthouse's
defaults) — same scores on both locales:

| Category | `/es/` | `/en/` |
| --- | --- | --- |
| Performance | 100 | 100 |
| Accessibility | 100 | 100 |
| Best Practices | 100 | 100 |
| SEO | 100 | 100 |

Expected for a page with no JS framework, no web fonts, and no
render-blocking requests beyond one small stylesheet. Run it yourself:

```bash
cd web && npm run build && npx serve . -l 5050 &
npx lighthouse http://localhost:5050/es/ --view
```

Future regulation-specific pages (`/es/ppwr`, `/en/ppwr/importers`,
`/es/guias/...`, `/en/dpp/...`) are deliberately not built yet — see
`web/README.md` for the directory convention they'd follow when they are.

### App i18n: what's translated vs. deliberately deferred

`app.sourcelya.com` has its own runtime i18n now — `frontend/src/app/core/i18n/`:
`LocaleService` (a signal holding the active locale, default `es` — Spain is
the first go-to-market market — persisted to `localStorage`, no cookies),
`dictionaries/{es,en}.ts` (flat objects implementing one `Dictionary`
interface, so a missing translation key is a compile error, not a silent
blank), and a small `LocaleSwitchComponent` (the same discreet `ES | EN`
pattern as the landing site). Not `@angular/localize`: that needs a build
per locale, which doesn't fit a runtime switcher and is real build
complexity this app doesn't need yet — a signal-driven dictionary is the
same centralization pattern already proven by `BRAND` and the landing
site's `content/*.json`, just applied at runtime instead of build time.

**Translated**: the nav (`TopNavComponent`), login, signup, and the
onboarding step (dashboard's company-creation form) — the exact minimal
journey a first Spanish customer walks through — plus the FASE 2 screens
(Suppliers, Products, product detail/packaging-components, including the
status badges and packaging-type labels) and, new this phase, the FASE 3
Requests screens (list/new/detail) through the same `LocaleService`.

The **public supplier portal is a special case**: it must speak
`ComplianceRequest.language` (chosen once by the company, e.g. a Spanish
company inviting an English-speaking supplier), never the visiting
browser's own preference or `LocaleService`'s state — a supplier who never
logs in has no relationship to the authenticated app's locale switcher at
all. `PublicRequestComponent` reads straight from `DICTIONARIES[language]`
by that field, bypassing `LocaleService` entirely, and has its own small
`publicRequest` dictionary section (heading, field labels, save/submit
copy, error states) rather than reusing the authenticated app's strings.

**Deliberately left in English**: the post-onboarding dashboard body
(product-count stats, the empty-state message) — it existed before this
phase, isn't part of the "minimal existing journey" the brief named, and
FASE 5 rebuilds it into the real dashboard anyway, so translating it now
means translating it twice. Third-party error text (Supabase's own login/
signup error messages) is shown as-is rather than guessing a translation
for copy we don't control.

Verified against the real backend end to end (not just visual): see
[Manual flow](#manual-flow-verified-end-to-end) below — every screenshot
there is the actual running app in Spanish, switched to English live via
the same `LocaleSwitchComponent` at the end to confirm both directions
work.

### The CTA and the PPWR checker

"Check my first supplier free" / "Comprueba tu primer proveedor gratis"
links straight to `https://app.sourcelya.com/signup`, which already exists
and works (FASE 1). That satisfies the brief's own instruction to pick
"the simplest option that doesn't block launch" — building a placeholder
screen instead of using the signup that's already there would have been
extra work for the same outcome. When a real PPWR/Supplier Readiness
Checker exists, the destination changes in exactly one place —
`APP_SIGNUP_URL` in `web/build.js` — not in the template's five separate
links or in two locale files.

## Data model

FASE 1 kept the schema intentionally minimal — just what's needed for
company/user auth plus the next phase's core catalog, so FASE 2 didn't
immediately redo the model. See `backend/app/models/`:

- **`Company`**, **`User`** — auth/tenancy. A `User.company_id` is set once,
  via `POST /api/companies` (no multi-company-per-user in the MVP).
- **`Supplier`**, **`Product`**, **`PackagingComponent`** — the FASE 2 catalog
  entities: full CRUD now exists on top of these (see
  [API endpoints](#api-endpoints) and [Roadmap](#roadmap)).
- **`ComplianceRequest`**, **`ComplianceRequestProduct`** (FASE 3) — a
  company's request to one supplier covering one or more of that supplier's
  products. `status` is a linear `VARCHAR` state machine (`draft -> sent ->
  opened -> in_progress -> submitted`; `review_required`/`completed` exist
  as future states nothing transitions into yet), `language` is the
  supplier-facing locale chosen explicitly per request (never inferred from
  the supplier's country), and `secure_token_hash`/`token_expires_at`/
  `token_revoked_at` implement the token design described above.
  `ComplianceRequestProduct` is a plain join row (`request_id`,
  `product_id`, unique together) — see [Public supplier
  portal](#public-supplier-portal) for why there is deliberately no
  separate "supplier answers" table.
- **`AuditEvent`** (FASE 3) — an append-only log
  (`REQUEST_CREATED`/`_SENT`/`_OPENED`/`_SAVED`/`_SUBMITTED`,
  `TOKEN_REVOKED`, `EMAIL_RESENT`) written by `AuditService.record()`.
  `actor_user_id` is null for events triggered from the public portal (no
  authenticated user exists there); `metadata_json` is generic `JSON` on
  SQLite, `JSONB` on Postgres, same pattern as elsewhere in this codebase.

Still deliberately **not** modelled (each ships in its own later phase):
`SupplierDocument` (FASE 4), `ExtractedField` (FASE 7). When they're added,
they keep the design decisions already agreed for them — full extraction
provenance (document/page/quoted text), `VARCHAR` instead of native enums
for evolving fields.

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
| `INTEGRATION_DATABASE_URL` | Optional override for `pytest -m integration`; defaults to the `docker-compose.yml` Postgres credentials |

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

### API endpoints

```
GET    /api/health
GET    /api/auth/me
POST   /api/companies
GET    /api/companies/me

POST   /api/suppliers
GET    /api/suppliers
GET    /api/suppliers/{id}
PATCH  /api/suppliers/{id}

POST   /api/products
GET    /api/products
GET    /api/products/{id}                                    # includes packaging_components
PATCH  /api/products/{id}
POST   /api/products/{id}/packaging-components
GET    /api/products/{id}/packaging-components
PATCH  /api/products/{id}/packaging-components/{component_id}

POST   /api/requests                                          # create (DRAFT)
GET    /api/requests
GET    /api/requests/{id}
POST   /api/requests/{id}/send                                # mints the token, emails it, returns request_url once
POST   /api/requests/{id}/revoke
POST   /api/requests/{id}/resend                               # mints a NEW token — see note below

GET    /api/public/requests/{token}                            # no auth — the token IS the credential
PATCH  /api/public/requests/{token}                            # save progress
POST   /api/public/requests/{token}/submit

POST   /api/internal/jobs/process-reminders                  # shared-secret, not user auth
```

Every `suppliers`/`products`/`requests` route requires a
Supabase-authenticated user with a company (`get_current_company`);
responses are always scoped to that company. `Product` and
`PackagingComponent` responses include a computed `status` (and
`missing_fields` for components) from `StatusCalculationService` — see
[Computed status, not cached](#computed-status-not-cached). The
`/api/public/requests/*` routes take **no** auth dependency at all — see
[Public supplier portal](#public-supplier-portal).

### Public supplier portal

The FASE 3 target: *"Sourcelya can send a real request to a supplier and
receive a response back without the supplier creating an account."*

**Company side** (`ComplianceRequestService`): create a `DRAFT` request for
one supplier + one or more of that supplier's own products (both
ownership checks run before any row is written); `send()` generates a
token via `generate_secure_token()`, stores only `hash_token(token)`,
emails the supplier the templated request (ES/EN, exact copy in
`app/integrations/email/templates.py`), and returns the plaintext URL
**exactly once** in the HTTP response — `ComplianceRequestRead` never
includes it again afterwards, only a `has_active_link` boolean. Sending an
already-sent request is rejected (409), not silently re-armed. `revoke()`
sets `token_revoked_at`; **`resend()` mints a brand-new token** rather than
re-sending the old one, because the raw token is never stored anywhere to
resend as-is — this is a deliberate simplification (see [Technical debt
& simplifications](#technical-debt--simplifications)) whose side effect is
that the previous link stops working the moment a new one is issued.

**Supplier side** (`PublicRequestService`, `/request/{token}` in the
Angular app — its own standalone route, no `<app-top-nav>`, no auth
guard): every method re-derives the `ComplianceRequest` from
`hash_token(token)` and checks `token_revoked_at`/`token_expires_at`
before doing anything else, so there is no code path that accepts a
request or company id directly from the caller. The first successful
`GET` flips `SENT -> OPENED`; `PATCH` (save progress) validates that
**every** `component_id` in the payload belongs to one of this specific
request's own products before writing **any** of them (all-or-nothing),
then flips to `IN_PROGRESS`; `POST .../submit` flips to `SUBMITTED` and is
idempotent (submitting an already-submitted request just returns it,
rather than erroring). The public read/write schemas
(`PublicComplianceRequestRead`, `PublicPackagingComponentUpdate`)
deliberately never include `company_id`/`supplier_id` — a supplier's
browser never receives Sourcelya's internal ids, not just doesn't display
them.

No separate "supplier answers" table: the public portal edits the same
`PackagingComponent` rows (`material`, `weight_grams`,
`recycled_content_percentage`, `packaging_reference`, `notes`) the company
already sees on the product — see [Technical debt &
simplifications](#technical-debt--simplifications) for why.

`backend/tests/test_public_requests.py` and
`test_compliance_requests.py` specifically cover: invalid token, expired
token, revoked token, a component belonging to a different request, a
component belonging to a different company's product, sending a request
twice, resending, revoking, and idempotent submit.
`backend/tests/test_e2e_request_flow.py` runs the entire lifecycle once,
start to finish, through the real HTTP API: create supplier/product →
create request → send → parse the emailed URL → open as the supplier →
save progress → submit → confirm the company sees `SUBMITTED` with the
supplier-provided data attached.

### Frontend

```bash
cd frontend
npm install
npm start   # ng serve, http://localhost:4200
```

## Tests

Two suites, run separately on purpose — see `backend/tests/integration/README.md`
for the full reasoning:

```bash
cd backend
source .venv/bin/activate
pytest                 # fast suite: SQLite, no external services, runs on every save

docker compose up -d postgres    # or any reachable Postgres with matching creds
pytest -m integration  # slow suite: real PostgreSQL, catches SQLite/Postgres divergence
```

`pytest -m integration` is excluded from a plain `pytest` run (see
`backend/pytest.ini`) and skips itself with an explanatory message if
Postgres isn't reachable, rather than failing the whole run.

### Fast suite (SQLite)

Covers what matters most for an MVP handling multi-tenant data behind a
public supplier link:

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
- `test_suppliers.py` — CRUD, email validation, and that a company can never
  read/list/edit another company's suppliers.
- `test_products.py` — CRUD, assigning a supplier to a product (rejected if
  the supplier belongs to another company), cross-tenant isolation for both
  products and packaging components, and that a product's computed status
  flips from `orange` to `green` as its packaging component's required
  fields get filled in.
- `test_compliance_requests.py` — company-side request lifecycle: creation
  (rejecting a supplier/product from another company, or a product that
  belongs to a different supplier than the one chosen), send/revoke/resend,
  sending a request twice being rejected, and cross-tenant isolation.
- `test_public_requests.py` — the token/public side: invalid token (404),
  expired token (410), revoked token (403), never exposing
  `company_id`/`supplier_id`, first-open flipping to `OPENED`, save
  progress (including rejecting a component that belongs to a different
  request or a different company's product), idempotent submit, and that
  nothing can be saved after submission.
- `test_e2e_request_flow.py` — the full request lifecycle in one real
  HTTP-API test, company to supplier and back (see [Public supplier
  portal](#public-supplier-portal) for what it covers).

### Integration suite (real PostgreSQL)

Not a duplicate of the fast suite — six tests for exactly the things SQLite
can't validate:

- Alembic migrations apply cleanly against real Postgres.
- **Foreign keys are enforced.** SQLite doesn't enforce them unless `PRAGMA
  foreign_keys=ON` is set, and the fast suite's engine doesn't set it — a
  broken FK would pass every fast-suite run and only surface in
  production/Supabase.
- **`VARCHAR(n)` length limits are enforced.** SQLite has no such concept
  and silently accepts a too-long value; Postgres correctly rejects it.
- The custom `GUID` type round-trips correctly through the real `psycopg`
  driver, not SQLite's fallback.
- `users.email` uniqueness is enforced at the database level.
- `CompanyScopedRepository` isolation holds end to end against the real
  database, not just SQLite.

Written before `ComplianceRequest` existed, so it doesn't cover
`secure_token_hash`/FK behavior on the FASE 3 tables specifically — the
fast suite's token/isolation tests (above) already exercise that logic
against SQLite, and nothing about FASE 3's schema is a new
SQLite-vs-Postgres divergence risk beyond what FASE 1/2 already validated
here (same `GUID` type, same `VARCHAR`-not-native-enum status column, same
FK pattern).

Reuses `docker-compose.yml`'s `postgres` service and credentials rather
than standing up separate test infrastructure, and truncates the app's
tables before each test — **don't point `INTEGRATION_DATABASE_URL` at a
database you care about.**

Frontend: `cd frontend && npm test` runs the Angular/Karma unit tests
(requires a Chromium binary; see `frontend/README.md` if you need to point
Karma at a specific browser).

## Manual flow (verified end to end)

No Supabase project is available in every environment this runs in, so the
full flow below was verified against the **real backend and a real
Postgres**, bypassing only Supabase's own login UI: a Supabase-shaped
session (an HS256 access token accepted because `SUPABASE_JWT_STRATEGY=hs256`
locally, plus a session object matching `@supabase/supabase-js`'s own
`localStorage` schema) is written directly to `localStorage` under its
`sb-<host>-auth-token` key, exactly what the real Supabase Auth client
would have written after a real login. Everything downstream — the
`/api/auth/me` call, company onboarding, suppliers, products, packaging
components, status computation — hit the real FastAPI app and a real
PostgreSQL database, not a mock.

1. Load `/dashboard` with no company yet → onboarding form (Spanish, the
   default locale).
2. Create the company ("Importadora Ejemplo SL") → real dashboard.
3. Suppliers → add "Shenzhen Wonderful Packaging" (CN) → appears in the list.
4. Products → add "Cepillo de bambú" (SKU `CB-001`), assign the supplier
   above → status `Falta información` (orange — no packaging components yet).
5. Open the product → add packaging component "Caja exterior" (box,
   material only) → stays orange, missing fields shown in Spanish
   ("Falta: Peso (gramos), Contenido reciclado (%)").
6. Add a second component "Bolsa interior" (bag, material + weight +
   recycled %, all required fields filled) → that component turns green.
7. Switch to English with the header's `EN` toggle, live, no reload → every
   label (nav, status badges, packaging type, missing-fields list) updates
   instantly; the data entered (product/supplier/component names) is
   unaffected, as it should be — it's data, not UI copy.

**FASE 3**, same technique (real backend, real Postgres, injected session —
see [Public supplier portal](#public-supplier-portal) for the endpoints
involved), run in an actual Chromium browser via Playwright:

1. Requests → New request → pick the supplier and its product → language
   Spanish → create → lands on the request detail page, status `Borrador`.
2. Click "Enviar solicitud" → status flips to `Enviada`, a green banner
   reveals the secure link exactly once (`/request/{token}`) with a copy
   button — refreshing the page never shows it again.
3. Open that link in a **separate, unauthenticated browser context** (no
   Supabase session, no app shell) → the plain public portal renders in
   Spanish, showing only this request's company/supplier/products/
   packaging fields — no internal ids, no top-nav.
4. Fill in material/weight/recycled-%/notes for the one packaging
   component → "Guardar" → progress saved, request now `IN_PROGRESS`.
5. "Enviar solicitud" (with a confirmation prompt) → the portal shows the
   "solicitud enviada" confirmation view, fields now read-only.
6. Back on the authenticated side: the request detail page's timeline
   shows all four events (Creada/Enviada/Abierta/Completada por el
   proveedor) with real timestamps, status badge `Completada`; the
   product detail page shows the supplier-entered packaging data, and its
   status is now `Completo` (green).
7. Sanity check: `/request/not-a-real-token` renders a plain "this link is
   not valid" message — no app chrome, no stack trace, no hint of what a
   valid token would look like.

## Technical debt & simplifications

Decisions made during FASE 3 to keep the scope to "close the request loop,
nothing else" (per the phase brief), worth revisiting once real usage
justifies it:

- **No separate "supplier answers" table.** The public portal edits the
  same `PackagingComponent` rows the company's own product page reads —
  `material`, `weight_grams`, `recycled_content_percentage`,
  `packaging_reference`, `notes` are exactly the fields both sides need,
  so a parallel `ComplianceRequestAnswer` table would only duplicate data
  and need its own sync logic. This stops being the right call the moment
  Sourcelya needs to show *what the supplier changed* versus what was
  already there, or needs one product to be part of two concurrent
  requests with independently-tracked answers.
- **`resend()` mints a new token instead of resending the old one.** The
  raw token is never stored (only its hash), so there is nothing to
  literally resend — issuing a fresh one and emailing it is the only
  option, with the side effect that the previous link stops working. If a
  future phase needs "remind without invalidating," that requires storing
  something recoverable (e.g. a short-lived reminder-only token) instead
  of reusing this mechanism.
- **`review_required`/`completed` are unused states.** They exist on
  `RequestStatus` (see `app/domain/enums.py`) because the spec named them
  as future states, but nothing in FASE 3 transitions a request into
  either — there's no scoring/conflict logic yet to justify
  `review_required`, and no explicit "mark done" action for `completed`.
- **Frontend analytics fire on every portal view, not just the first.**
  `supplier_request_opened` fires on every successful `GET
  /api/public/requests/{token}`, whereas the backend's `REQUEST_OPENED`
  audit event only fires once (on the `SENT -> OPENED` transition) — the
  public read response doesn't tell the frontend whether this was the
  very first open. The backend audit log is the authoritative record;
  analytics is directional, not exact, by design (see
  `AnalyticsService`'s own docstring).
- **New request creation is a standalone screen**, not launched from a
  supplier detail page — there is no supplier detail page yet (Suppliers
  is list-only since FASE 2). `/requests/new` picks the supplier from a
  dropdown instead.
- **No automatic reminders yet.** `reminder_count`/`last_reminder_at`
  exist as columns (per the FASE 3 model spec) but nothing writes to them
  — `ReminderService` still returns a no-op (see [Why not an in-process
  scheduler](#why-not-an-in-process-scheduler-for-jobs)); real reminder
  logic is FASE 6.

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
FASE 2 added no new tables (Supplier/Product/PackagingComponent were already
part of `0001_initial_schema.py`). `0002_compliance_requests.py` (FASE 3)
adds `compliance_requests`, `compliance_request_products`, and
`audit_events` — applied and verified against a real local PostgreSQL 16
instance, not just SQLite.

## Project structure

```
web/                # sourcelya.com — public static site (see web/README.md)
  content/          # es.json / en.json — every string on the page, centralized
  templates/        # page.html (shared structure), redirect.html (root ->/es/)
  build.js          # zero-dependency generator: content + template -> es/, en/
  es/, en/          # generated output (committed — see web/README.md)
  index.html        # generated: root redirect to /es/
  styles.css, analytics.js, favicon.svg, robots.txt, sitemap.xml, _redirects
backend/            # api.sourcelya.com
  app/
    api/            # FastAPI routers + dependencies (auth, DB session)
    core/           # config, database, security (JWT), logging
    models/         # SQLAlchemy models
    domain/         # pure-Python domain enums (not DB-mapped) — includes
                     # Locale (es/en), reserved for ComplianceRequest.language
    schemas/        # Pydantic schemas
    repositories/   # DB access, company-scoped by default
    services/       # business logic
    integrations/   # email / storage / extraction adapters behind interfaces
  alembic/          # migrations
  tests/            # fast suite (SQLite)
  tests/integration/ # `-m integration` suite (real Postgres) — see its README
frontend/           # app.sourcelya.com — the authenticated app, no landing content
  src/app/
    core/           # auth service, HTTP interceptor, route guard, API client,
                     # brand.ts (naming/copy), analytics.service.ts,
                     # i18n/ (LocaleService, es/en dictionaries, locale switch)
    features/       # auth (login/signup), dashboard, suppliers,
                     # products (+ product-detail), requests (list/new/detail),
                     # public-request (the standalone /request/:token portal —
                     # no shared chrome with the rest of the app, on purpose)
    shared/         # cross-feature UI: top-nav, shared list-page styles
  src/environments/
docker-compose.yml
.env.example
```

## Roadmap

Outside the numbered phases below (standalone validation work, done
between FASE 2 and FASE 3): the bilingual [public landing
site](#public-landing-site-sourcelyacom) at `sourcelya.com`, and closing
out FASE 1 with the [Postgres integration
suite](#integration-suite-real-postgresql) and the `Locale` enum.

- **FASE 1 — done**: architecture, minimal database schema, Supabase JWKS
  auth, company onboarding, dashboard shell, internal-jobs endpoint shape,
  and (closed out afterwards) a real-Postgres integration test suite
  alongside the fast SQLite one.
- **FASE 2 — done**: Suppliers and Products CRUD (with nested packaging
  components), company-scoped and cross-tenant-tested end to end; dashboard
  now shows real product counts/status instead of placeholders; all of it
  bilingual (ES/EN) via the new app-level i18n — see [App
  i18n](#app-i18n-whats-translated-vs-deliberately-deferred) — and verified
  against the real backend, not just visually (see [Manual
  flow](#manual-flow-verified-end-to-end)).
- **FASE 3 — done**: `ComplianceRequest` / `ComplianceRequestProduct` +
  `AuditEvent`; the company-side request lifecycle (create, send, revoke,
  resend) and the no-login-required public supplier portal
  (`/request/{token}`) — see [Public supplier
  portal](#public-supplier-portal) for the full flow, security model, and
  tests, and [Technical debt &
  simplifications](#technical-debt--simplifications) for what was
  deliberately kept simple.
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
