# Sourcelya

**Supplier compliance, without the chasing.**

Sourcelya helps companies obtain, structure, verify and maintain the
documentation and evidence they need from their suppliers. The product's
marketing copy (tagline, one-line explanation) lives in one place —
`frontend/src/app/core/brand.ts` — and is explicitly not final; see
[Product positioning](#product-positioning) below.

> Sourcelya helps you collect and organise supplier documentation. It does
> not constitute legal advice and does not guarantee regulatory compliance.

This repository currently implements **FASE 1–6** of the roadmap:
architecture, database schema, authentication, the Suppliers/Products
catalog, the secure no-login-required supplier request flow, the supplier
attaching real documents to that request, turning those documents into
structured, evidence-backed proposals a human reviews before anything ever
touches `PackagingComponent`, and now closing the loop end to end —
Sourcelya works out exactly what's still missing and asks the supplier for
only that, without anyone writing a follow-up email by hand. See
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
for AI/OCR. `StubDocumentExtractionService` (default, no API key required)
returns no suggestions; `ClaudeDocumentExtractionService` (FASE 5,
`DOCUMENT_EXTRACTION_PROVIDER=anthropic`) calls the real Claude API and is
the only code path that ever produces `ExtractedField` proposal rows — never
`PackagingComponent` itself. See [Document extraction
(FASE 5)](#document-extraction-fase-5) below for the full pipeline, the
provider/cost rationale, and the anti-hallucination design.

**Storage**: same adapter-behind-an-interface pattern as email —
`StorageService` (`app/integrations/storage/base.py`), with
`SupabaseStorageService` for production and `InMemoryStorageService` as the
local/test fallback when no Supabase project is configured. See [Document
uploads](#document-uploads-fase-4).

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
product is still being validated — `packaging_type`, `document_type`,
`extraction_status`, `confidence`, `field_name` — are stored as plain
`VARCHAR` and validated in Python (`app/domain/enums.py`, Pydantic schemas)
instead. A native enum needs an `ALTER TYPE ... ADD VALUE`
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
status badges and packaging-type labels) and the FASE 3 Requests screens
(list/new/detail) through the same `LocaleService` — now extended with the
FASE 4 documents list/download strings on the company side.

The **public supplier portal is a special case**: it must speak
`ComplianceRequest.language` (chosen once by the company, e.g. a Spanish
company inviting an English-speaking supplier), never the visiting
browser's own preference or `LocaleService`'s state — a supplier who never
logs in has no relationship to the authenticated app's locale switcher at
all. `PublicRequestComponent` reads straight from `DICTIONARIES[language]`
by that field, bypassing `LocaleService` entirely, and has its own small
`publicRequest` dictionary section (heading, field labels, save/submit
copy, error states, and now upload/delete copy for FASE 4) rather than
reusing the authenticated app's strings.

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
- **`ComplianceRequest`**, **`ComplianceRequestProduct`** (FASE 3, extended
  FASE 6) — a company's request to one supplier covering one or more of
  that supplier's products. `status` is a `VARCHAR` state machine (`draft
  -> sent -> opened -> in_progress -> submitted -> completed`, looping back
  to `in_progress` on each follow-up round's edit — see [Document
  extraction (FASE 5)](#document-extraction-fase-5)'s sibling section
  [Missing-information follow-up
  (FASE 6)](#missing-information-follow-up-fase-6) for the full state
  machine and why the previously-unused `review_required` value was
  removed), `language` is the supplier-facing locale chosen explicitly per
  request (never inferred from the supplier's country), and
  `secure_token_hash`/`token_expires_at`/`token_revoked_at` implement the
  token design described above. FASE 6 added `automatic_follow_up` (bool,
  default `False`) and `fields_available_after_first_submission` (int,
  nullable — a one-time snapshot for the recovery-rate metric).
  `ComplianceRequestProduct` is a plain join row (`request_id`,
  `product_id`, unique together) — see [Public supplier
  portal](#public-supplier-portal) for why there is deliberately no
  separate "supplier answers" table.
- **`FollowUpRound`** (FASE 6) — an immutable snapshot of one "we asked the
  supplier for exactly these fields" event: `round_number`,
  `requested_fields` (JSON `[{packaging_component_id, field_name}]`),
  `trigger` (`manual`/`automatic`), `available_count_before`/
  `missing_count_before`. Created the instant a follow-up email is sent —
  see [Missing-information follow-up
  (FASE 6)](#missing-information-follow-up-fase-6).
- **`AuditEvent`** (FASE 3) — an append-only log
  (`REQUEST_CREATED`/`_SENT`/`_OPENED`/`_SAVED`/`_SUBMITTED`,
  `TOKEN_REVOKED`, `EMAIL_RESENT`) written by `AuditService.record()`.
  `actor_user_id` is null for events triggered from the public portal (no
  authenticated user exists there); `metadata_json` is generic `JSON` on
  SQLite, `JSONB` on Postgres, same pattern as elsewhere in this codebase.

- **`SupplierDocument`** (FASE 4, extended FASE 5) — a file the supplier
  attached, today always through the public portal for a specific
  `ComplianceRequest` (`supplier_id`/`product_id`/`request_id` are all
  independently nullable, so a later phase can attach a document without
  going through a request). `content_type` stores Sourcelya's own canonical
  MIME type for the validated extension, never whatever the browser claimed
  — see [Document uploads](#document-uploads-fase-4). `document_type`
  (`DocumentType` enum: `packaging_specification`, `technical_datasheet`,
  `certificate`, `declaration`, `invoice_commercial`, `other`) and
  `extraction_status` (`ExtractionStatus` enum: `pending`, `processing`,
  `completed`, `failed`, `review_required`) are now driven by a real
  pipeline — see [Document extraction (FASE 5)](#document-extraction-fase-5).
  FASE 5 also added bookkeeping columns for cost/observability:
  `processing_error`, `extraction_attempts`, `extraction_model`,
  `extraction_duration_ms`, `extraction_input_tokens`,
  `extraction_output_tokens`, `extraction_cost_usd`.
- **`ExtractedField`** (FASE 5) — one proposed value for one
  `PackagingComponent` field, produced from one `SupplierDocument`. Carries
  full provenance (`source_page`, `source_quote`, `quote_verified`) and a
  `confidence` (`high`/`medium`/`low`), plus a `review_status`
  (`pending`/`accepted`/`rejected`). **Never written into
  `PackagingComponent` by the extractor** — only a human ACCEPT
  (`ExtractedFieldService.accept()`) ever does that. See [Document
  extraction (FASE 5)](#document-extraction-fase-5) for the full design.

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
| `DOCUMENT_EXTRACTION_PROVIDER` | `stub` (default, no suggestions, no API calls) or `anthropic` (real extraction — see [Document extraction (FASE 5)](#document-extraction-fase-5)) |
| `ANTHROPIC_API_KEY` | Required only when `DOCUMENT_EXTRACTION_PROVIDER=anthropic` |
| `ANTHROPIC_EXTRACTION_MODEL` | Defaults to `claude-opus-5` |
| `MAX_UPLOAD_SIZE_MB` | Supplier document upload size ceiling (default 20) — see [Document uploads](#document-uploads-fase-4) |
| `ALLOWED_UPLOAD_EXTENSIONS` | Accepted document extensions (default `pdf,xlsx,csv,docx,png,jpg,jpeg`) |
| `SUPABASE_SERVICE_ROLE_KEY` | Required (with `SUPABASE_URL`) for real Supabase Storage; otherwise documents use the in-memory fallback |
| `INTEGRATION_DATABASE_URL` | Optional override for `pytest -m integration`; defaults to the `docker-compose.yml` Postgres credentials |
| `MAX_AUTOMATIC_FOLLOW_UP_ROUNDS` | Ceiling on **automatic** follow-up rounds per request before Sourcelya stops auto-sending and flags `REQUEST_NEEDS_HUMAN_ATTENTION` (default 3) — manual follow-up is never capped. See [Missing-information follow-up (FASE 6)](#missing-information-follow-up-fase-6) |

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
POST   /api/requests/{id}/follow-up                            # manual: ask again for only what's still missing — 409 with a structured code if not eligible
POST   /api/requests/{id}/automatic-follow-up                  # toggle the per-request automatic_follow_up flag (off by default)

GET    /api/public/requests/{token}                            # no auth — the token IS the credential
PATCH  /api/public/requests/{token}                            # save progress
POST   /api/public/requests/{token}/submit
POST   /api/public/requests/{token}/documents                 # upload (multipart/form-data, field "file")
DELETE /api/public/requests/{token}/documents/{document_id}

GET    /api/documents/{document_id}/download                  # authenticated, company-scoped
GET    /api/documents/{document_id}/extracted-fields           # proposals for one document
POST   /api/documents/{document_id}/extracted-fields/{field_id}/accept   # 409 on conflict — see below
POST   /api/documents/{document_id}/extracted-fields/{field_id}/reject
POST   /api/documents/{document_id}/retry-extraction           # re-runs the pipeline, original file untouched

POST   /api/internal/jobs/process-reminders                  # shared-secret, not user auth
```

`POST /api/requests/{id}/follow-up` returns a structured `{"detail":
{"code": ..., "detail": ...}}` body on 409 (`duplicate_follow_up`,
`nothing_missing`, `review_required`, `not_eligible`,
`max_rounds_reached`) instead of a bare string, the same pattern FASE 5's
conflict error established — see [Missing-information follow-up
(FASE 6)](#missing-information-follow-up-fase-6).

Every `suppliers`/`products`/`requests`/`documents` route requires a
Supabase-authenticated user with a company (`get_current_company`);
responses are always scoped to that company. `Product` and
`PackagingComponent` responses include a computed `status` (and
`missing_fields` for components) from `StatusCalculationService` — see
[Computed status, not cached](#computed-status-not-cached). The
`/api/public/requests/*` routes take **no** auth dependency at all — see
[Public supplier portal](#public-supplier-portal). `ComplianceRequestRead`/
`PublicComplianceRequestRead` both carry a `documents[]` array now — see
[Document uploads](#document-uploads-fase-4). On the authenticated side,
each document also carries `extracted_field_count`/`pending_review_count`,
and `GET /api/documents/{id}/extracted-fields` returns the full proposals
with evidence — see [Document extraction (FASE 5)](#document-extraction-fase-5).

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

### Document uploads (FASE 4)

The FASE 4 target: *"Sourcelya can now receive real documentation from a
supplier."* No OCR, no LLM extraction, no automatic classification — just
getting the file from the supplier's browser into storage and in front of
the company, safely.

**Storage strategy**: `StorageService` (`app/integrations/storage/base.py`)
has three methods — `upload`, `download`, `delete` — implemented by
`SupabaseStorageService` (production, talks to the Supabase Storage REST
API with the service-role key) and `InMemoryStorageService` (local
dev/tests, a process-lifetime dict — the same role `ConsoleEmailSender`
plays for email). `get_storage_service()`
(`app/integrations/storage/factory.py`) picks whichever one applies based
on whether `SUPABASE_URL`/`SUPABASE_SERVICE_ROLE_KEY` are set — a config
change, not a code change, same pattern as the email factory. Downloads go
**through the backend** (`GET /api/documents/{id}/download` reads the
bytes via `StorageService.download` and streams them back with the right
`Content-Type`/`Content-Disposition`) rather than redirecting the browser
to a Supabase signed URL — one code path behaves identically in tests,
local dev, and production, and the company's auth check happens on every
download, not just once when a signed URL was minted.

Storage path convention (decided back in FASE 1, implemented now):
`companies/{company_id}/requests/{request_id}/{document_id}.{extension}`
— the **document's own id**, generated up front, not the user-supplied
filename, so there is no path-traversal or collision surface from
attacker-controlled input. The original filename is kept only as metadata
(`SupplierDocument.filename`) for display and the download's
`Content-Disposition`.

**Validations** (`DocumentService._validate`,
`app/services/document_service.py`): extension against
`Settings.allowed_upload_extensions` (`pdf`, `xlsx`, `csv`, `docx`, `png`,
`jpg`/`jpeg` — already configured back in FASE 1, unused until now);
declared `Content-Type` checked against a per-extension allow-list
(`EXTENSION_MIME_TYPES`), tolerating the generic
`application/octet-stream` some browsers send instead of a real MIME type;
size against `Settings.max_upload_size_mb` (also an existing FASE 1
setting). Critically, **the client-declared Content-Type is only ever
checked, never stored or replayed** — `SupplierDocument.content_type`
holds Sourcelya's own canonical MIME type for the validated extension, so
`GET /api/documents/{id}/download` can never be made to serve a file back
with an attacker-chosen `Content-Type` (e.g. `text/html`, inviting a
stored-XSS-via-download scenario).

**Portal side** (`POST`/`DELETE .../documents`, both resolving the token
through the same `PublicRequestService.resolve_token` every other
public-portal action uses — no separate validation path to keep in sync):
upload and delete are both rejected once the request is `SUBMITTED` or
`COMPLETED` (`RequestNotEditableError`, 409) — see the spec's "subir y
eliminar antes de submit". Delete additionally re-checks that the
`document_id` belongs to *this specific* `request_id`
(`SupplierDocumentRepository.get_for_request`) — a document id from a
different request (even one the same supplier owns) is a 404, not a
silent no-op.

**Company side**: `ComplianceRequestRead`/`PublicComplianceRequestRead`
both got a `documents: []` field rather than a separate list endpoint —
the request detail screen a company already fetches is where its
documents belong. `GET /api/documents/{id}/download` is the one dedicated
endpoint, company-scoped via the same `CompanyScopedRepository.get`
pattern as everything else.

Audit events: `DOCUMENT_UPLOADED`/`DOCUMENT_DELETED`, recorded by the same
`AuditService.record()` every other FASE 3/4 action uses.

`backend/tests/test_document_service.py` unit-tests the validation logic
directly (disallowed extension, mismatched MIME, oversized file, rejected
after submit) without going through HTTP.
`backend/tests/test_documents.py` covers the HTTP/isolation surface:
invalid token, cross-request document deletion rejected, upload/delete
rejected after submit, a company can only download its own documents
(another company's `GET` on the same `document_id` is a 404), and both
audit events actually land in the table.
`backend/tests/test_e2e_document_upload.py` runs the whole thing through
the real HTTP API: supplier opens the request → uploads a PDF → submits →
company downloads it and gets back the exact same bytes.

### Document extraction (FASE 5)

The FASE 5 target: turn an unstructured supplier document into
evidence-backed, structured **proposals** for the existing
`PackagingComponent` fields — never an autonomous rewrite of them. The one
rule everything else here serves: **Sourcelya must never invent compliance
data**, and it must never silently overwrite a value someone already
entered.

**Pipeline**: `DocumentService.create()` still only handles upload/storage
(unchanged from FASE 4); once a document exists, `ExtractionService.process()`
(`app/services/extraction_service.py`) runs **synchronously, inline, in the
same request** — `pending -> processing -> completed | review_required |
failed`. No job queue: at this volume (one document per upload) the
inline call is simpler to reason about and to test than adding
Celery/Redis for a single background step, matching this codebase's
existing "no in-process scheduler, no message broker" stance (see [Why not
an in-process scheduler](#why-not-an-in-process-scheduler-for-jobs)). A
failed extraction (provider error, timeout, malformed response) is caught,
recorded on `processing_error`, and leaves `extraction_status=failed` —
**the original uploaded file is never touched or lost**, and `POST
/api/documents/{id}/retry-extraction` re-runs the same pipeline against it.
`review_required` is used when the extraction produced at least one `LOW`
confidence field, so the company's UI can flag "look at this one first"
without a separate polling mechanism.

**Provider: Anthropic Claude** (`ClaudeDocumentExtractionService`,
`app/integrations/extraction/claude_extraction.py`), model `claude-opus-5`
by default, called via `client.messages.parse(..., output_format=
DocumentExtractionSchema)` — Pydantic **structured outputs**, not a "parse
the model's prose" approach. `DocumentExtractionSchema` uses `Literal`
types for every closed field (`field_name`, `status`, `confidence`,
`document_classification`) and `ConfigDict(extra="forbid")`, so the SDK
itself rejects any response shape outside the exact schema Sourcelya
defined — this is real, load-bearing input validation, not a formatting
nicety. **Why Claude over a cheaper/local OCR pipeline**: the source
documents are exactly the kind of messy, inconsistently-formatted PDFs/
scans/spreadsheets a real packaging supplier sends, where a fixed OCR +
regex pipeline breaks on the first document that doesn't match the assumed
layout; a vision-capable LLM reads the *whole* page (or sheet) and
distinguishes "the weight of this specific SKU's box" from other numbers
on the same page, which brittle template matching cannot.

**Cost estimate** (`app/integrations/extraction/pricing.py`,
`estimate_cost_usd`): at Claude Opus 5 list pricing ($5/MTok input, $25/MTok
output) a typical one-to-two-page packaging spec (image/vision tokens for a
scanned page, or a few hundred tokens of extracted text for a native-text
PDF/XLSX/CSV/DOCX) runs on the order of **$0.02–$0.08 per document** in our
own manual testing, with the `effort: "low"` output config keeping output
tokens (a handful of short structured fields) minimal. `SupplierDocument`
persists `extraction_model`/`extraction_input_tokens`/
`extraction_output_tokens`/`extraction_duration_ms`/`extraction_cost_usd`
on every real run specifically so "what does processing 1,000 documents
cost us" is a `SELECT sum(extraction_cost_usd) FROM supplier_documents`
away, without needing a cost dashboard in this phase.

**Format handling** (`app/integrations/extraction/document_text.py`,
no OCR library, no separate vision pipeline):

| Format | How it reaches the model |
| --- | --- |
| PDF with a text layer | Deterministic text extracted per-page with `pypdf`, sent as plain text — cheaper and exactly reproducible, no vision call needed |
| Scanned PDF (no text layer) | `pypdf` returns no text → the **raw PDF bytes** go to Claude as a native `document` content block; Claude's built-in vision reads the scan directly — no separate OCR step or library |
| XLSX | `openpyxl` converts every sheet to a plain-text grid, sent as text |
| CSV | Decoded and sent as text directly |
| DOCX | `python-docx` extracts paragraph/table text |
| PNG / JPG | Sent as a native `image` content block — Claude's vision handles it the same way it handles a scanned PDF page |

Deliberately **not** using OCR/vision for every format: a text-layer PDF,
XLSX, CSV, or DOCX already has a lossless, free, deterministic text
representation, so sending it as an image would just add cost and a new
failure mode (mis-read digits) for zero benefit — vision is reserved for
the two cases (scans, photos) that genuinely need it.

**Evidence and anti-hallucination design** — the two things enforced
together, never just one:

1. The model must report, for every field it claims to have found, the
   page number and the **exact quoted text** it based the value on
   (`source_page`, `source_quote` in the schema) — not just the value.
   A field the model can't support with a quote must be reported as
   `NOT_FOUND`, and `NOT_FOUND`/`UNKNOWN` fields produce **no
   `ExtractedField` row at all** — silence, not a low-confidence guess (see
   `ExtractedField`'s own docstring).
2. Sourcelya **independently verifies** that quote (`verify_quote()` in
   `claude_extraction.py`) against text *we* extracted ourselves (the same
   `document_text.py` pass above) for every format where a deterministic
   text layer exists — never trusting the model's citation of its own
   accuracy unchecked. A vision-read scan/image has no independent text to
   check against, so its quote is unverifiable by construction — that's
   reflected honestly in `quote_verified=False`, not hidden.

**Confidence is a deterministic ceiling, not the model's raw self-report**
(`resolve_confidence()`): `final = min(model's claimed level, a ceiling
derived from verification)` — a verified quote can reach `HIGH`; no
independently-checkable text layer to verify against (a scan/image) caps at
`MEDIUM`; a claimed quote that verification could *not* find in our own
extracted text caps at `LOW`. Sourcelya never presents a numeric confidence
percentage the provider doesn't actually give a defensible basis for —
three named categories, each backed by a specific, auditable rule, is what
the FASE 5 spec asked for instead of an invented number.

**Document classification**: a small closed set on purpose —
`packaging_specification`, `technical_datasheet`, `certificate`,
`declaration`, `invoice_commercial`, `other` — not a large taxonomy. The
model classifies the whole document once per extraction call, for display
only; nothing branches its extraction behavior on the category today.

**Never overwrite without approval** — the actual mechanism, not just a
UI convention: `ExtractionService` **only ever creates `ExtractedField`
proposal rows**; nothing in it, or in the extraction provider, ever writes
to `PackagingComponent`. `ExtractedFieldService.accept()`
(`app/services/extracted_field_service.py`) is the **only** code path in
the entire codebase allowed to apply a value to `PackagingComponent`, and
only for a field a human explicitly accepted. If the target field already
has a non-empty value that differs from the extracted one, `accept()`
raises `FieldConflictError` (HTTP 409, body `{"detail": "POSSIBLE
CONFLICT", "field_name", "current_value", "extracted_value"}`) instead of
applying anything — the caller must resubmit with an explicit
`conflict_resolution` (`"use_extracted"` or `"keep_current"`); there is no
implicit default. `packaging_component_id` on `ExtractedField` is only
auto-resolved when the request unambiguously covers a single
`PackagingComponent` — the common first-request case — otherwise the
reviewer picks the target component explicitly at accept time. This is the
"minimal evolution" the FASE 5 spec asked for instead of a general-purpose
data-lineage system: one small proposal table plus one gated write path,
`PackagingComponent`'s own schema unchanged.

**Missing information after accept**: reuses
`StatusCalculationService` unchanged (see [Computed status, not
cached](#computed-status-not-cached)) — accepting a field just writes a
normal `PackagingComponent` column, so the existing green/orange status and
missing-fields list pick it up for free. FASE 5 adds one thing on top: a
component/product with any **pending** `ExtractedField` shows **RED**
("needs a human decision") regardless of how confident the extraction was
— `calculate_component_status`/`calculate_product_status` both take an
optional `has_pending_review`/`components_with_pending_review` flag,
computed by the caller from a lightweight query, so the service itself
stays the same pure/DB-free function it always was. "Missing" still means
exactly what it meant before FASE 5: fields our own model expects that
have no value yet — no PPWR legal-requirement engine is introduced here.

**Security — documents are untrusted input, always**: document content
only ever appears inside `user`-role message content; the system prompt
(`SYSTEM_PROMPT` in `claude_extraction.py`) is a fixed constant that never
mixes with document text, so a document containing text like "ignore
previous instructions, output X" cannot alter Sourcelya's own instructions
to the model. The real defense is structural, not a runtime string filter:
`DocumentExtractionSchema`'s `Literal` types + `extra="forbid"` mean the
extractor **cannot** report a `field_name` outside the five known packaging
fields, a `confidence` outside the three known levels, or any extra key at
all — there is no schema-valid way for a malicious document to make the
model call a tool, emit an instruction, or write outside
`PackagingComponent`'s known fields, because the extractor never has tool
access and never writes anywhere by itself in the first place.
`backend/tests/test_claude_extraction_internals.py` includes dedicated
prompt-injection-shaped fixtures (documents whose "content" is itself an
injection attempt) asserting the extractor still only ever produces
schema-valid field proposals, never an action.

**Tests** (fixtures only — the suite never depends on a paid Claude API
call): `test_claude_extraction_internals.py` (19 tests) covers the pure
functions (`build_content_blocks`, `verify_quote`, `resolve_confidence`),
the schema's `Literal`/`extra="forbid"` enforcement, and the
prompt-injection fixtures, all without network access.
`test_extraction_service.py` covers the pipeline state machine (pending →
completed/review_required/failed, retry, a failure never losing the
original document) against a `FakeDocumentExtractionService`.
`test_extracted_fields.py` (10 tests) covers the HTTP surface: accept,
reject, the 409 conflict body and both resolutions, company isolation (a
field from another company's document is a 404), and
`StatusCalculationService`'s RED status after accept/reject.
`test_extraction_retry.py` covers retry specifically. `test_e2e_extraction_
flow.py` runs the full lifecycle through the real HTTP API: upload → stub/
fake extraction produces proposals → list them with evidence → accept one
→ confirm the `PackagingComponent` and computed status actually changed.

### Missing-information follow-up (FASE 6)

The FASE 3–5 loop stopped at "supplier clicked Submit." FASE 6 closes the
real operational loop: company asks → supplier responds (partially) →
Sourcelya extracts → company reviews → **Sourcelya figures out exactly
what's still missing** → Sourcelya asks again for *only that* → supplier
completes it → request reaches COMPLETE. Nothing here is AI-driven —
extraction is still the only place an LLM is involved (unchanged from
FASE 5); everything that decides what's missing, what's complete, what
gets re-asked, and what an email says is deterministic code operating on
structured data.

**The one rule everything else here serves**: Sourcelya never asserts
"PPWR compliant," "non-compliant," or "legally valid" — there is no legal
rules engine in this MVP and building one is explicitly out of scope (see
[Roadmap](#roadmap)). The only vocabulary Sourcelya uses is
**information complete / information missing / review required /
conflict** — a statement about data completeness, never a legal judgment.
`InformationStatus` and `FieldInformationState`
(`app/domain/enums.py`) are named accordingly.

**What counts as "requested"**: FASE 6 does not invent a new concept for
this — it reuses FASE 5's `ExtractableFieldName` enum (`material`,
`packaging_type`, `weight_grams`, `recycled_content_percentage`,
`packaging_reference`) as the canonical "fields a request expects back"
per `PackagingComponent`. The same five fields are both "what extraction
can find" and "what a request expects" — one enum, not two parallel ones
that could drift apart.

**`MissingInformationService`** (`app/services/missing_information_
service.py`) — the deterministic engine the spec insisted on ("NO usar LLM
para decidir si falta información"). For every requested field on every
`PackagingComponent` covered by a request, it looks at exactly three
structured inputs — the component's current column value, and any
`ExtractedField` proposals for that field that are still `pending` — and
classifies the field into one of:

| State | Meaning |
| --- | --- |
| `AVAILABLE` | The component column already has a value, no pending proposal conflicts with it |
| `MISSING` | No value, no pending proposal either |
| `REVIEW_REQUIRED` | A pending proposal exists and there's no current value to compare it against (or it agrees) — a human still has to accept/reject it before it counts |
| `CONFLICT` | A pending proposal's value **differs** from an existing current value — blocks completion until a human resolves it via `accept(conflict_resolution=...)` (see [Document extraction](#document-extraction-fase-5)) |
| `NOT_APPLICABLE` | Reserved for a future per-request "this field doesn't apply to this component" flag — never produced today (see [Technical debt](#technical-debt--simplifications)) |

`summarize()` rolls these per-field states up into one
`InformationStatus` for the whole request: `complete` (all fields
`AVAILABLE`/`NOT_APPLICABLE`), `conflict` (any `CONFLICT`, wins over
everything else), `review_required` (any pending review, no conflict), or
`missing_information` otherwise. This is a pure function over data already
in Postgres — no new tables, no caching, same "computed status, not
cached" philosophy as [`StatusCalculationService`](#computed-status-not-cached).

**Request state machine, extended**: `RequestStatus` grew from the FASE 3
one-way `draft -> sent -> opened -> in_progress -> submitted -> completed`
into a machine that can **loop**: `submitted` can go back to
`in_progress` when a follow-up round is created, and only reaches
`completed` when `MissingInformationService.summarize()` says `complete`
— not merely when the supplier clicks Submit. The unused `review_required`
status value from FASE 3 was removed rather than repurposed, since FASE 6
needed that concept to live at the *information* level
(`InformationStatus`), not the request-workflow level — conflating the
two would have meant a component's field-level state directly renaming
the request's own workflow stage, which stops making sense once a request
can have some fields under review and others already complete. This is
deliberately a **smaller** state machine than the spec's own example list
(`DRAFT/SENT/SUPPLIER_RESPONDED/PROCESSING/REVIEW_REQUIRED/
MISSING_INFORMATION/FOLLOW_UP_SENT/COMPLETE/REVOKED`) — most of those are
already expressible as `RequestStatus` × `InformationStatus` combinations
(e.g. "FOLLOW_UP_SENT" is just `in_progress` + a `FollowUpRound` row;
"REVIEW_REQUIRED" is `submitted` + `InformationStatus.review_required`),
so adding them as first-class statuses would have meant tracking the same
fact twice.

**Supplier submission no longer means "done"**
(`PublicRequestService.submit()`): submitting now runs
`FollowUpService.reevaluate()` — process what was uploaded, recompute
`MissingInformationService`, and only transition to `completed` if the
result is actually `complete`; otherwise the request stays
`submitted`/`in_progress` and the company sees exactly what's still
outstanding. The supplier-facing confirmation copy was changed to "Thanks,
your information has been submitted" — never "everything is complete" —
since FASE 6 made completeness a fact Sourcelya computes independently,
not one the supplier's own action can assert.

**`FollowUpService`** (`app/services/follow_up_service.py`) is the
orchestrator with two entry points:

- `create_round(trigger="manual"|"automatic")` — the company clicks
  **"Request missing information"** (`POST /api/requests/{id}/follow-up`),
  or the automatic path triggers it. Before creating anything it asserts
  the request is eligible — not revoked, not already complete, extraction
  not still `processing`, no live conflict, no pending review affecting a
  requested field, at least one field actually missing, and (for
  `automatic` only) under `MAX_AUTOMATIC_FOLLOW_UP_ROUNDS` — raising a
  specific exception per violation (`DuplicateFollowUpError`,
  `NothingMissingError`, `ReviewRequiredError`,
  `RequestNotEligibleForFollowUpError`, `MaxAutomaticRoundsReachedError`),
  each mapped to a distinct HTTP 409 `code` (see [API
  endpoints](#api-endpoints)) so the frontend renders exact guidance
  instead of a generic error. On success it snapshots exactly the still-
  missing fields into one immutable `FollowUpRound` row, mints a fresh
  token (see below), and sends the missing-information email.
- `reevaluate()` — called after every event that could change
  completeness (supplier submit, a field accepted, a field rejected). It
  recomputes `MissingInformationService`, transitions the request to
  `completed` if warranted (recording `REQUEST_COMPLETED` and, when
  `automatic_follow_up` is enabled on the request, sending the optional
  thank-you email), or — if still incomplete **and** automatic follow-up
  is on **and** the missing fields are unambiguous (no pending review, no
  conflict) — calls `create_round(trigger="automatic")` itself. A request
  with **zero** requested fields (a request whose product has no
  `PackagingComponent`s yet) is guarded out explicitly: without the guard,
  `total_requested == 0` is vacuously "complete," which would silently
  auto-complete and email a "thank you, all done!" for a request that
  never tracked anything.

**Follow-up rounds are minimal, on purpose**: a `FollowUpRound` is one
immutable snapshot row (`round_number`, `requested_fields` JSON,
`trigger`, `available_count_before`/`missing_count_before`) — not a
thread, not a chat, not a mutable checklist. "What's still missing right
now" is never read from round history; it's always recomputed live by
`MissingInformationService`. Rounds exist purely as an auditable record of
*when* and *for what* Sourcelya asked again — exactly the "minimal round
modeling" the spec asked for.

**Token security — kept, not weakened**: every follow-up (and every
reminder) mints a brand-new raw token and stores only its hash
(`hash_token()`, unchanged from FASE 3), immediately revoking the
previous one implicitly (its hash no longer matches anything, so the old
link now reads as an unknown/invalid token — verified directly in
`test_e2e_follow_up_flow.py`). This isn't a new design decision so much as
a **forced consequence of an already-made one**: FASE 3 chose a one-way
hash (never storing the raw token, so it can't be re-sent or looked up
later) specifically so a leaked database dump can't be used to impersonate
a supplier — but that same property means Sourcelya itself cannot recover
the previous raw token to reuse it. Token rotation-per-round was never
actually a choice between "keep" and "rotate" (option A vs B from the
spec) — once the hash-only, non-reversible design was accepted for FASE 3,
rotation on every new email was already the only option consistent with
it. The alternative (persisting the raw token so it *could* be reused)
would have reintroduced exactly the risk FASE 3 was built to avoid, just
to save minting one token. Expiry and manual revocation
(`POST /api/requests/{id}/revoke`) both still work exactly as before.

**Automatic follow-up — manual first, opt-in, capped**
(`ComplianceRequest.automatic_follow_up`, default `False`): FASE 6
implements the spec's "MANUAL as the safe path first," and stops there for
default behavior — the company must explicitly turn a per-request switch
on (`POST /api/requests/{id}/automatic-follow-up`) before Sourcelya will
ever auto-send a follow-up on its own. This is a deliberate control
decision, not a missing feature: the company should keep control during
validation of a new tenant/supplier relationship, and only opt in once
they trust the extraction + missing-information logic for that request.
When enabled, `reevaluate()` is the only trigger — there is **no new
scheduler**; automatic follow-up rides the same request-response cycle
that already exists (submit/accept/reject), consistent with this
codebase's "no in-process scheduler, no Celery/Redis" stance (see [Why
not an in-process scheduler](#why-not-an-in-process-scheduler-for-jobs)).
`MAX_AUTOMATIC_FOLLOW_UP_ROUNDS` (default 3) stops an automatic loop from
ever running forever: once hit, Sourcelya records
`REQUEST_NEEDS_HUMAN_ATTENTION` and stops auto-sending — manual follow-up
remains available, uncapped, at any time.

**Never pester the supplier** — the concrete rules
`_assert_can_follow_up()` enforces before any follow-up (manual or
automatic) is created: nothing is actually missing, extraction is still
`processing`, a relevant `REVIEW_REQUIRED` exists, a relevant `CONFLICT`
exists, the request is `revoked`, the request is already `completed`, or
an identical follow-up (same missing fields) was already just sent
(`DuplicateFollowUpError`) — all enforced in
`test_follow_up_service.py`.

**Follow-up vs. reminder — two different concepts, not merged**: a
**follow-up** is new content — "here's specifically what's still
missing" — and always creates a `FollowUpRound`. A **reminder** is a
re-delivery of content that hasn't changed — "you haven't responded yet"
— and creates no new round; it just re-mints a token (same rotation logic
above) and resends whatever the request's *current* state already implies
(the original request, or the current outstanding follow-up, whichever is
live). `ReminderService` (`app/services/reminder_service.py`, rewritten in
FASE 6) reuses the exact job/scheduling mechanism from FASE 3 —
`REMINDER_SCHEDULE_DAYS`, `reminder_count`/`last_reminder_at`, the same
`POST /api/internal/jobs/process-reminders` shared-secret endpoint, and
the same idempotent `UPDATE ... WHERE reminder_count = :i` claim-before-
send guard — no new scheduler was introduced for FASE 6.

**Company review UI — Information Status**: the request detail view shows
a live "N/M requested fields available" summary plus four lists —
available (✓), missing (○), review required (⚠, linking to the pending
extracted-field proposal), conflict (⚠, showing both the current and the
proposed value side by side) — computed from the same
`MissingInformationService` output the backend uses, never a separate
frontend calculation. The **"Request missing information"** button is
disabled (with the specific reason shown) whenever `_assert_can_follow_up`
would reject it, so the company never sees a click succeed only to get a
409 back.

**Supplier portal — "Almost there," not "start over"**: opening a
follow-up link shows only the fields still missing for that round
(`missing_fields` on the public request read schema) — previously-
supplied fields render as completed/read-only, and previously-uploaded
documents are never re-requested. This reuses the same public-request
form components from FASE 3/4, just scoped to the round's
`requested_fields` rather than showing the full form from scratch.

**Emails — deterministic copy, two languages, no template engine**
(`app/integrations/email/templates.py`, `EmailService`): FASE 6 added two
builders — the missing-information follow-up (lists only the fields still
needed, with copy explicitly saying "you don't need to resend the
information you've already provided") and an optional request-complete
thank-you, both in `es`/`en` selected from the request's own `language`
column (never inferred). Same `ConsoleEmailSender`-locally /
configurable-`RESEND_API_KEY`-in-production setup as FASE 3 — no generic
templating system was introduced, and no LLM writes any email copy.

**Recovery-rate metric** (`FollowUpService.recovery_stats()`) — the ROI
number the spec wants demonstrable later: `total_requested`,
`available_now`, `available_after_first_submission` (a **one-time
snapshot** taken the instant the supplier's first-ever submission is
processed — never overwritten again), `follow_up_recovered` (the
difference), and `recovery_rate` (`available_now / total_requested`).
Deliberately avoids building an event-sourcing/history system to compute
this: one persisted snapshot column
(`fields_available_after_first_submission`) plus the always-live
`MissingInformationService` output is enough to answer "how much did
follow-up recover that the first response didn't" without a general
timeline feature.

**Audit trail additions**: `SUPPLIER_RESUBMITTED`, `FOLLOW_UP_CREATED`,
`REQUEST_COMPLETED`, `REQUEST_NEEDS_HUMAN_ATTENTION` were added to
`AuditEventType` alongside the FASE 3/5 events already recorded
(`REQUEST_SENT`, `REQUEST_SUBMITTED`, `EMAIL_RESENT`, etc.) — no new
generic event bus, just a few more values on the existing append-only log.

**Tests**: `test_missing_information_service.py` (6) — every field state
in isolation (available, missing, review-required, conflict, an accepted
proposal becomes available, a rejected one stays missing).
`test_follow_up_service.py` (8) — a follow-up contains only missing
fields and never re-asks an available one, duplicate follow-ups are
blocked, a conflict/pending-review blocks both follow-up and completion,
an incomplete submit never marks `completed`, a fully-supplied submit
does, automatic follow-up is off by default, and the round cap is
respected. `test_reminder_service.py` (4) covers the reminder/follow-up
distinction and the idempotent claim guard.
`test_e2e_follow_up_flow.py` (2) runs the full loop through the real HTTP
API end to end — see [Manual flow](#manual-flow-verified-end-to-end) —
plus the conflict-blocks-completion scenario, and asserts the audit trail
and recovery metric both come out right at the end.

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
- `test_document_service.py` / `test_documents.py` /
  `test_e2e_document_upload.py` — document upload validation, cross-request/
  cross-company isolation, audit events, and the full upload → submit →
  download lifecycle (see [Document uploads](#document-uploads-fase-4)).
- `test_claude_extraction_internals.py` / `test_extraction_service.py` /
  `test_extracted_fields.py` / `test_extraction_retry.py` /
  `test_e2e_extraction_flow.py` — the extraction pipeline, evidence
  verification, prompt-injection fixtures, accept/reject/conflict, retry,
  company isolation, and the full extraction-to-accepted-value lifecycle
  (see [Document extraction (FASE 5)](#document-extraction-fase-5)) —
  fixtures only, never a paid call to the real Claude API.
- `test_missing_information_service.py` / `test_follow_up_service.py` /
  `test_reminder_service.py` / `test_e2e_follow_up_flow.py` — the
  missing-information loop: every field state (available/missing/review-
  required/conflict), a follow-up containing only missing fields and never
  re-asking an available one, duplicate follow-ups blocked, a conflict or
  pending review blocking both follow-up and completion, an incomplete
  submit never marking `completed` while a fully-supplied one does,
  company/public-token isolation, ES/EN email content, automatic
  follow-up disabled by default and capped at
  `MAX_AUTOMATIC_FOLLOW_UP_ROUNDS`, the reminder/follow-up distinction,
  the audit trail, and the recovery-rate metric (see
  [Missing-information follow-up (FASE 6)](#missing-information-follow-up-fase-6)).

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

**FASE 4**, same setup, on top of a freshly sent request:

1. On the public portal, choosing a disallowed file (`.exe`) shows "Ese
   tipo de archivo no está permitido" inline — the request is rejected by
   the backend (400), nothing gets uploaded, and the documents list stays
   empty.
2. Choosing an allowed file (`.pdf`) uploads it immediately — no separate
   "confirm upload" step — and it appears in the documents list with its
   filename and size, plus an "Eliminar" button (since the request isn't
   submitted yet).
3. "Enviar solicitud" → the confirmation view, upload/delete controls
   gone, the document still listed (read-only) as proof it survived
   submission.
4. Back on the authenticated side, the request detail page now has a
   "Documentos recibidos" section with the same file, its size, and when
   it was uploaded, plus a "Descargar" button.
5. Clicking "Descargar" triggers a real browser download (via a
   fetched Blob + a synthetic anchor click, since the auth interceptor
   can't attach a bearer token to a plain link navigation) — the
   downloaded file's bytes were compared against the original fixture
   file and matched exactly.

**FASE 5**, same real-backend/real-Postgres/real-Chromium technique, on top
of a freshly submitted document (extracted fields seeded in exactly the
shape `ExtractionService` produces, to exercise the review UI without a
paid Claude API call — the extraction pipeline itself is already exercised
against fixtures in the automated suite, see [Document extraction
(FASE 5)](#document-extraction-fase-5)):

1. The company's documents table now shows Type (`Otro`), a Processing
   status badge (`Completado`, green), and a Fields column — `3` proposed,
   with a red `3` pending-review badge next to it.
2. "Ver información extraída" expands an evidence panel per field: value,
   a confidence badge (`Alta confianza`/`Confianza media`/`Baja confianza`),
   and the source line (`Fuente: sample.pdf · Página 7`, or `(cita no
   verificada automáticamente)` for the unverified low-confidence one).
3. Accepting the `packaging_reference` field (no existing value → no
   conflict) applies immediately and the badge changes to
   `Revisado: accepted`.
4. Accepting the `weight_grams` field (existing value `42`, extracted `47`)
   shows the exact conflict UI from the spec — "POSIBLE CONFLICTO / Valor
   actual: 42.0 / Valor extraído: 47" — with "Usar valor extraído"/
   "Mantener valor actual" buttons; choosing "Usar valor extraído" applies
   `47` and marks the field accepted.
5. Rejecting the `recycled_content_percentage` field (low confidence,
   unverified quote) marks it `Revisado: rejected` and leaves the
   component's existing value untouched.
6. The product detail page now shows `weight_grams = 47` (the accepted
   value) and `recycled_content_percentage` unchanged at `10` (the rejected
   proposal never applied) — status is green now that every proposal has
   been reviewed (no more pending-review row flipping it red).
7. Switching to `EN` translates the whole panel live — confidence labels,
   "Reviewed: accepted/rejected", evidence prefixes — without touching the
   underlying data, same pattern as every earlier phase's i18n.
8. Forcing `extraction_status=failed` on the document shows the red
   "Error" badge with the stored `processing_error` message and a
   "Reintentar" button; clicking it re-runs the pipeline, restores
   `Completado`, and **all three previously-reviewed fields are still
   there, still in their accepted/rejected state** — a retry never re-asks
   a question a human already answered, and never loses the original file.

**FASE 6**, same real-backend/real-Postgres/real-Chromium technique — a
bare packaging component (only `packaging_type` set at creation, so
1/5 fields start available, 4 missing) taken all the way to `COMPLETE`
through two rounds:

1. Company sends the request; detail page shows `1/5 campos disponibles`.
2. Supplier fills in `material` and `weight_grams` directly, uploads a
   spec document (which the fake extraction path proposes
   `packaging_reference` from), and submits. Confirmation copy reads
   "Gracias, tu información ha sido enviada" — not "todo completo."
3. Company reloads the request detail: Information Status now shows
   `3/5` available, `weight_grams`/`material`/`packaging_type` under
   Disponible, `packaging_reference` under Revisión requerida (linking to
   the pending proposal), `recycled_content_percentage` under Falta.
4. Company accepts the `packaging_reference` proposal (no conflict, since
   the component had no prior value there) → detail page updates to
   `4/5`, only `recycled_content_percentage` still missing.
5. Company clicks "Solicitar información faltante" → a `FollowUpRound`
   is created and its email sent; the button becomes disabled (nothing
   left ambiguous, but nothing new to ask either) until something changes.
6. Supplier opens the follow-up's link (a **freshly minted token** — the
   original link, opened again, now reads as invalid, confirming rotation
   actually happened) and sees the "Casi listo" scoped view: only
   `recycled_content_percentage` is editable, every other field renders
   already filled in, read-only. They fill it in and submit.
7. Company reloads the request: status is `Completada`, Information
   Status shows `5/5`, and the Recovery panel reads
   `Recuperación: 100% (2 campos recuperados tras seguimiento)` —
   matching `recovery_stats.available_after_first_submission = 3` and
   `follow_up_recovered = 2` exactly.
8. Toggling "Seguimiento automático" on the request flips
   `automatic_follow_up` (verified via the API response, since a
   completed request has nothing left to auto-send).
9. Switching to `EN` translates the whole Information Status panel,
   round history, and recovery copy live, same pattern as every earlier
   phase.

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

FASE 4:

- **`InMemoryStorageService` doesn't survive a restart or scale past one
  process.** Fine for local dev and the test suite (same tradeoff as
  `ConsoleEmailSender`); production always needs `SUPABASE_URL`/
  `SUPABASE_SERVICE_ROLE_KEY` set so `SupabaseStorageService` is used
  instead — see [Document uploads](#document-uploads-fase-4).
  `SupabaseStorageService` itself is exercised by unit-style validation
  tests and the real-Supabase-shaped path, but not by an integration test
  against a real Supabase Storage bucket — no such bucket exists in this
  environment.
- **`document_type` is classified by the real extraction pipeline as of
  FASE 5** (see [Document extraction (FASE 5)](#document-extraction-fase-5))
  — under the stub provider (the default; no `ANTHROPIC_API_KEY`) it's
  still always `other`, since the stub does no classification at all. There
  is still no manual type picker in the upload form.
- **Downloads are read in full into memory** (`StorageService.download`
  returns `bytes`, not a stream) before being returned. Acceptable at the
  `max_upload_size_mb` ceiling this MVP enforces (20MB default); would need
  to switch to a streaming response if that ceiling ever grows
  substantially.
- **No virus/malware scanning.** Validation is extension + declared MIME
  type + size only, exactly what the FASE 4 spec asked for ("validación
  MIME/extensión") — a real content-sniffing or antivirus pass is not
  attempted. **This is not optional debt** — it is an explicit, mandatory
  item on the [pre-production checklist](#pre-production-checklist) below,
  now that FASE 5 also feeds every uploaded file's bytes to an external
  LLM API.
- **The company side has no delete.** The spec's explicit bullet list says
  "listar y descargar documentos recibidos" for the company — deleting a
  supplier's upload is something only the supplier can do (and only before
  submit), matching a paper-trail mental model where the company shouldn't
  be able to make a received document disappear.

FASE 5:

- **Extraction runs synchronously, inline in the upload request** — no job
  queue (see [Document extraction (FASE 5)](#document-extraction-fase-5)
  for why, consistent with this codebase's existing no-scheduler/no-broker
  stance). This is the first phase where that tradeoff has a real latency
  cost (an LLM call, not a DB write) — the point to revisit it is if upload
  response times under real document volume become a problem, not before.
- **Single-component auto-link heuristic.** `ExtractedField.
  packaging_component_id` is only auto-resolved when a request covers
  exactly one `PackagingComponent`; a request covering several requires the
  reviewer to pick the target component explicitly at accept time (the
  frontend doesn't expose that picker yet — `packaging_component_id` would
  need to be sent in `AcceptExtractedFieldPayload`, which the API already
  supports). Fine for the common single-component first request; a
  multi-component UI is the natural next increment, not a redesign.
- **No cost dashboard.** `extraction_cost_usd` and friends are persisted
  per document specifically so "cost per 1,000 documents" is answerable
  with a `SELECT sum(...)`, but nothing in the UI surfaces it yet — the
  spec explicitly said a dashboard wasn't needed for this phase.
- **Confidence is a three-level ceiling, not a numeric score.** Deliberate,
  not a shortcut — see [Document extraction
  (FASE 5)](#document-extraction-fase-5) for why an invented percentage
  would be less honest than three auditable categories.
- **`ClaudeDocumentExtractionService` has no automated test that hits the
  real Anthropic API** (by design — see [Tests](#tests): the suite must
  never depend on a paid call). Its pure logic (prompt construction, quote
  verification, confidence resolution, schema validation) is fully unit
  tested; only the actual network call to Claude itself is unverified by
  the automated suite, and was instead verified manually — see [Manual
  flow](#manual-flow-verified-end-to-end).

FASE 6:

- **No "required documents" concept.** Completeness is defined purely in
  terms of the five `ExtractableFieldName` fields being
  `AVAILABLE`/`NOT_APPLICABLE` — a request can reach `COMPLETE` with zero
  documents ever uploaded, if every field was filled in directly. The
  spec's "required documents (if any) present" clause has nothing to hook
  into yet, since there is no per-request "this document type is
  mandatory" flag in the data model.
- **`NOT_APPLICABLE` is reserved, never produced.** `FieldInformationState`
  includes it for a future per-request "this field doesn't apply to this
  component" flag, but nothing in FASE 6 sets it — every field is either
  requested-and-trackable or not requested at all.
- **Single-component auto-link heuristic, inherited from FASE 5, still
  applies to follow-up.** A request covering several `PackagingComponent`s
  still needs the reviewer to pick the target component explicitly when
  accepting a proposal; `MissingInformationService` itself handles
  multi-component requests correctly (it evaluates every component), only
  the *accept* UI has the FASE 5 limitation.
- **No per-round token audit beyond the `FollowUpRound` row itself.**
  Sourcelya doesn't log "token X was minted at time Y for round Z"
  separately — the round's `created_at` plus the fact that the previous
  token's hash no longer resolves is the evidence trail, consistent with
  not building a general security-event log for this phase.
- **Reminder and follow-up email content overlap on purpose.** A reminder
  for a request currently `in_progress` after a follow-up resends
  essentially the same missing-fields list a follow-up email would — there
  is no separate "reminder about a follow-up" template; `ReminderService`
  reads current state and reuses the follow-up template builder rather
  than maintaining a third copy deck.
- **No dashboard beyond the Requests list/detail.** Recovery-rate,
  round counts, and information status are all viewable per request; there
  is no cross-request analytics view aggregating recovery rate across a
  company's whole request history — deliberately deferred, per the spec's
  explicit exclusion of a new analytics dashboard.
- **Automatic follow-up has no company-wide default.** The flag lives on
  `ComplianceRequest`, not `Company` — turning it on for one request
  doesn't turn it on for future ones. This matches the spec's "company
  must keep control during validation" intent literally (opt in per
  request) rather than assuming a company that likes automatic follow-up
  once wants it for everything.

### Pre-production checklist

Explicit, so it never quietly falls off a future phase's radar:

- [ ] Malware/antivirus scanning on every uploaded document, before it is
      stored or sent to any extraction provider (see above — FASE 4 debt,
      sharper now that FASE 5 forwards file bytes to an external API).
- [ ] A real job queue for extraction if inline latency becomes a problem
      at real volume (see FASE 5 debt above).
- [ ] A Supabase Storage bucket wired up and exercised by an integration
      test (today only `InMemoryStorageService` runs in CI/local dev).
- [ ] `SUPABASE_JWT_STRATEGY=jwks` configured against a real Supabase
      project (production must never run on `hs256`).

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
`audit_events`. `0003_supplier_documents.py` (FASE 4) adds
`supplier_documents`. `0004_extraction.py` (FASE 5) adds the extraction
bookkeeping columns to `supplier_documents` and creates `extracted_fields`.
`0005_follow_up.py` (FASE 6) adds `automatic_follow_up` and
`fields_available_after_first_submission` to `compliance_requests`,
removes the unused `review_required` value's implicit meaning (the column
stays `VARCHAR`, no data migration needed — see [PostgreSQL
enums](#postgresql-enums)), and creates `follow_up_rounds` — all applied
and verified against a real local PostgreSQL 16 instance, not just
SQLite.

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
    models/         # SQLAlchemy models (extracted_field.py: FASE 5 proposals;
                     # follow_up_round.py: FASE 6 round snapshots)
    domain/         # pure-Python domain enums (not DB-mapped) — includes
                     # Locale (es/en); FieldInformationState/InformationStatus
                     # (FASE 6, computed-only, never DB columns)
    schemas/        # Pydantic schemas (follow_up.py: FASE 6 read schemas)
    repositories/   # DB access, company-scoped by default
    services/       # business logic (DocumentService: upload validation;
                     # ExtractionService: FASE 5 pipeline orchestration;
                     # ExtractedFieldService: the only accept/reject writer;
                     # MissingInformationService: FASE 6 deterministic
                     # completeness engine; FollowUpService: FASE 6 round
                     # creation + reevaluate(); ReminderService: real
                     # implementation as of FASE 6)
    integrations/   # email / storage / extraction adapters behind interfaces
                     # (storage/: SupabaseStorageService + InMemoryStorageService;
                     # extraction/: StubDocumentExtractionService +
                     # ClaudeDocumentExtractionService, document_text.py,
                     # schema.py, pricing.py)
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
- **FASE 4 — done**: `SupplierDocument`; document uploads from the public
  portal (Supabase Storage in production, an in-memory fallback locally),
  extension/MIME/size validation, company-side listing and download — see
  [Document uploads](#document-uploads-fase-4) for the full flow, security
  model, and tests, and [Technical debt &
  simplifications](#technical-debt--simplifications) for what was
  deliberately kept simple. Still no OCR/LLM extraction, classification,
  or conflict detection at this point.
- **FASE 5 — done**: `ExtractedField` + a real `DocumentExtractionService`
  implementation (Anthropic Claude) behind the existing interface —
  document classification, evidence-backed field proposals, deterministic
  confidence, and the company-side review UI (accept/reject/conflict
  resolution) — see [Document extraction
  (FASE 5)](#document-extraction-fase-5) for the full design, cost
  rationale, security model, and tests, and [Technical debt &
  simplifications](#technical-debt--simplifications) /
  [Pre-production checklist](#pre-production-checklist) for what was
  deliberately kept simple or deferred. *(Note: an earlier sketch of this
  roadmap numbered the real dashboard/reminders/extraction work
  differently — this section reflects how the phases actually shipped.)*
- **FASE 6 — done**: closes Sourcelya's main operational loop — company
  asks → supplier responds (partially) → Sourcelya extracts → company
  reviews → `MissingInformationService` determines exactly what's still
  missing → the company (or, once opted in per request, Sourcelya itself)
  asks again for only that → supplier completes it → request reaches
  `COMPLETE`. New: `FollowUpRound`, the extended request state machine,
  a real `ReminderService` (reusing the existing internal-jobs shape,
  no new scheduler), ES/EN follow-up and thank-you emails, the
  Information Status UI, and a computable information-recovery-rate
  metric — see [Missing-information follow-up
  (FASE 6)](#missing-information-follow-up-fase-6) for the full design,
  the token-rotation decision, the automatic-follow-up safeguards, and
  tests, and [Technical debt &
  simplifications](#technical-debt--simplifications) for what was
  deliberately kept simple. Verified against the real backend, real
  Postgres, and a real Chromium browser end to end (see [Manual
  flow](#manual-flow-verified-end-to-end)) — the exact scenario "asked a
  supplier for 5 fields, they returned 3, Sourcelya automatically
  identified the other 2 were still missing, asked again for exactly
  those, and the request completed" runs and passes.

**Development is paused here by design.** FASE 6 was the last phase this
roadmap commits to; whether to proceed to further feature work or to
freeze the product as-is for a commercial demo/validation is a decision
to make with real usage feedback in hand, not one to pre-bake into the
roadmap. A tentative **FASE 7** (polish, broader test coverage, closing
the [pre-production checklist](#pre-production-checklist) — most notably
malware scanning) remains the natural next step *if* development
continues, but is not started.

Explicitly out of scope for the MVP (see the product brief): a PPWR/legal
rules engine or automated compliance scoring (see [Missing-information
follow-up (FASE 6)](#missing-information-follow-up-fase-6) for why
Sourcelya only ever reports information completeness, never legal
validity), Digital Product Passport, EUDR, full REACH, a supplier
marketplace/network, ERP or Shopify/WooCommerce/Amazon integrations,
multi-company-per-user, complex billing/Stripe/subscription plans,
enterprise RBAC, a chatbot/RAG/vector-DB/embeddings layer, any AI usage
beyond FASE 5's document extraction, an analytics dashboard, a generic
workflow builder, a generic notification system, and blockchain. The data
model doesn't block adding these later, but none of them are being built
now.
