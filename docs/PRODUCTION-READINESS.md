# Sourcelya — Production & Demo Readiness (FASE 6.5)

This is not a feature roadmap. It tracks the work needed to run the
already-built FASE 1–6 product against a real domain, real Supabase
project, real email, and real Anthropic API — safely enough for 2–5 pilot
companies — and nothing beyond that.

Status legend: **DONE** (already true today, verified in code) · **NEEDS
USER ACTION** (an external account/config decision only the account owner
can make) · **BLOCKED** (needs a decision or a small implementation
change before pilots can start) · **POST-PILOT** (deliberately deferred).

This document is built incrementally, block by block, per the working
agreement in this phase — it is not all filled in yet. Section 1
(Architecture), Section 2 (Cost), and the audit (A–G) are the Block 1
deliverable. Everything else starts as a placeholder and gets resolved,
verified, and checked off one external action at a time.

## How to read the rest of this repo's docs

This file is the production checklist. The **why** behind existing
design decisions (token security, no-scheduler policy, extraction
evidence model, etc.) stays in the root `README.md` — this file only
adds what's new for going to production and doesn't repeat it.

---

## A–G Audit

### A. Already production-ready (no action needed)

- **JWT verification** (`app/core/security.py`): real JWKS verification
  against a Supabase project is implemented and defaults on
  (`SUPABASE_JWT_STRATEGY=jwks`); algorithm allowlist explicitly excludes
  `none`; `hs256` is dev/test-only and never the default.
- **Public token security**: 256-bit (`supplier_token_bytes=32`,
  URL-safe) tokens, SHA-256 hash-only storage, expiry, revocation, and
  forced rotation on every resend/follow-up/reminder (see README's
  [Missing-information follow-up](../README.md#missing-information-follow-up-fase-6)
  for the rotation rationale). No raw token is ever persisted or logged.
- **Tenant isolation**: `CompanyScopedRepository` plus dedicated
  cross-tenant tests across suppliers/products/requests/documents/
  extracted fields (see README Tests section) — this is exercised by
  both the fast SQLite suite and the real-Postgres integration suite.
- **Document extraction anti-hallucination design**: evidence
  quote+verification, `Literal`-typed/`extra="forbid"` schema, document
  content confined to `user`-role messages, dedicated prompt-injection
  fixtures. Nothing here needs to change for production.
- **Never-silently-overwrite rule**: `ExtractedFieldService.accept()` is
  still the only write path into `PackagingComponent`, with an explicit
  409 conflict instead of a silent merge.
- **Structured JSON logging** (`app/core/logging.py`, `structlog`):
  already outputs JSON to stdout, which every mainstream host (Render,
  Fly, Railway) captures and makes searchable without extra setup.
- **`GET /api/health`**: exists today, returns a static payload, no
  secrets.
- **Alembic migrations**: five migrations (`0001`–`0005`), applied and
  verified against a real local PostgreSQL 16 instance repeatedly across
  FASE 1–6. Ordering is linear, no branches.
- **CORS**: restricted to a single configured origin
  (`frontend_base_url`), not `*` — already correct in shape, just needs
  the production origin(s) as the configured value (see Section 23,
  pending).
- **`.env` is git-ignored**; `.env.example` contains only placeholders,
  no real secrets ever committed.
- **Landing site messaging** (`web/content/en.json` / `es.json`):
  already reads "Stop chasing suppliers for compliance documents" as the
  H1, frames PPWR as "first focus" rather than the whole product, and
  includes a legal disclaimer on the regulatory section. This already
  matches Section 17's ask — no rewrite needed, only a possible copy
  addition (see Section 17, pending) once we get there.

### B. Works only locally today

- **`FRONTEND_BASE_URL`, `frontend/src/environments/environment.production.ts`,
  `web/` deploy target**: all reference `sourcelya.com`/`app.sourcelya.com`/
  `api.sourcelya.com` as placeholders — no actual deployment exists yet.
- **CI**: no `.github/workflows/` — tests only run when someone runs
  `pytest`/`npm test` locally.
- **`docker-compose.yml`**: a local dev convenience only (`--reload`,
  bind-mounted source); not a production deployment artifact as-is.

### C. Uses a fallback/mock/stub today

- **`ConsoleEmailSender`** — active whenever `RESEND_API_KEY` is empty
  (the current default). No real email is ever sent.
- **`InMemoryStorageService`** — active whenever
  `SUPABASE_URL`/`SUPABASE_SERVICE_ROLE_KEY` are empty (the current
  default). Documents vanish on process restart, and don't survive
  multiple backend instances.
- **`StubDocumentExtractionService`** — active whenever
  `DOCUMENT_EXTRACTION_PROVIDER` is left at its default (`stub`). Returns
  zero field suggestions; the extraction pipeline runs but finds nothing.
- **`SUPABASE_JWT_STRATEGY=hs256`** — not itself a stub, but a
  weaker-verification path that must never be the value used in
  production; today it's what makes local dev/tests possible without a
  live Supabase project.
- **No malware scanner** — anything provider-agnostic; there is no
  "stub" to swap out because nothing was ever built here (see F below).

**The important finding**: all three fallbacks above (email, storage,
extraction) activate **silently** — a missing env var in production
today would not error, it would just quietly run the local-dev
behavior. This is exactly the failure mode Section 30 of the brief calls
out, and it's real: nothing currently stops a misconfigured production
deploy from "working" while never actually sending an email, storing a
document, or extracting anything. This needs a startup-time
configuration validator (`environment=production` requires all three to
resolve to their real implementation, or the app refuses to start) —
small, contained, no new dependency. Flagged as a blocker below, to be
implemented in its own block rather than bundled here.

### D. Needs external credentials/configuration

In the order the rest of this phase will actually need them:

1. A Supabase project (URL, anon key, service role key, JWT settings) —
   Section 3, next block.
2. A production database URL (Supabase's own Postgres connection
   string — no separate DB host needed).
3. A Resend account + API key + a verified sending domain
   (`sourcelya.com`) with DNS records.
4. An Anthropic API key with billing enabled (server-side only).
5. A backend hosting account (Render/Fly/Railway — decision pending in
   Section 1) and a static hosting account for the frontend/landing
   (Cloudflare Pages, since Cloudflare already manages the domain).
6. Cloudflare DNS access, to point the four subdomains at their
   deployed targets once those exist, and to add the email provider's
   SPF/DKIM/DMARC records.

None of these are created yet. Nothing below assumes a specific project
ID, key, or bucket name — those get filled in as we do each block.

### E. Security risks in the current state

Ranked by how much they matter for a public-internet pilot, not by how
hard they are to fix:

1. **No rate limiting anywhere**, especially on the public,
   no-auth-required portal endpoints
   (`GET/PATCH /api/public/requests/{token}`, the document upload
   endpoint, which triggers a real (billed) extraction call inline).
   A single leaked or guessed-at token, or just a scripted retry loop,
   can currently drive unbounded Anthropic spend and unbounded storage
   writes. **This is the single biggest cost-risk in the whole
   codebase** (Section 11/13's concern is justified).
2. **No per-request/per-document upload ceilings** beyond file size
   (20MB) and extension allowlist: no cap on documents per request, no
   PDF page cap, no extraction retry cap (retry is behind auth, so lower
   risk, but still uncapped).
3. **No malware/content scanning** on anything a supplier uploads,
   before that file is (a) stored and (b) sent to Anthropic's API. This
   is explicitly called out as a hard blocker in the brief and I agree
   with that framing — see F.
4. **Missing security headers**: no HSTS, no `X-Content-Type-Options`,
   no `Referrer-Policy`, no frame protection, no CSP. FastAPI adds none
   of these by default and nothing in this codebase adds them today.
5. **Silent-fallback risk** (see C above) is a security issue as much as
   a functional one: a production deploy that silently keeps
   `SUPABASE_JWT_STRATEGY=hs256` (forgotten env var) would run the
   entire API on a shared-secret HMAC scheme instead of Supabase's real
   asymmetric verification — lower blast radius than the email/storage/
   extraction fallbacks, but still wrong for production.
6. **No structured request logging with correlation IDs** yet — logs
   exist and are JSON, but there's no per-request ID threading through a
   failed upload → failed extraction → failed email chain, which will
   matter the first time a pilot reports "it didn't work" and we need to
   find the one relevant log line among many.

None of these are new design flaws — they're exactly the things a local
MVP correctly doesn't need and a public pilot does.

### F. Blocking before a real demo/pilot

1. **Malware scanning** — explicitly a hard blocker per the brief, and I
   agree: uploads come from suppliers we have no prior relationship with,
   through a link that requires no login. This has to exist before the
   public upload endpoint is reachable from the internet.
2. **Real storage + real email + real extraction, provably wired up** —
   not just "configured," but startup-validated so a misconfiguration
   fails loudly instead of silently degrading (see C).
3. **Rate limiting on the public portal**, at minimum on the upload
   endpoint (which is the one that costs money per call).
4. **Upload/extraction cost guards** — max documents per request, a page
   cap, some retry ceiling.
5. **HTTPS + real domains** for the three subdomains, obviously — there
   is no pilot without this.
6. **CORS locked to the real production origins** (currently a
   placeholder localhost value).
7. **The startup-configuration-fails-loud validator** described in C.
8. **A real end-to-end smoke test executed once against the deployed
   production stack** (Section 32 of the brief) — not just "the fast
   suite passes."

Everything in this list becomes its own block later in this phase; this
is the ordered list of what actually gates "safe to send a pilot company
a real link."

### G. Can wait until after pilot validation

- Sentry/external error monitoring (hosting provider logs are enough at
  this scale — see the architecture section's reasoning).
- A real job queue for extraction (still fine synchronous at this
  volume — unchanged conclusion from FASE 5).
- A Supabase Storage integration test against a real bucket (nice to
  have, not blocking — the real bucket itself gets used in production
  either way; the gap is only in the automated test suite).
- CI/CD sophistication beyond "run the two test suites and build the
  frontend before allowing a deploy."
- Any UI/dashboard polish, cost dashboards, or analytics beyond what
  FASE 6 already computes.
- Repo/branch renaming (`claude/packproof-saas-mvp-acqbew`, repo name
  `prueba-tecnica`) — cosmetic, no functional or security impact, and
  renaming now risks breaking the harness mid-phase. Documented as a
  pre-launch cleanup item, not touched now (see Section 26, pending
  block, for exactly how to do it safely when the time comes).
- GDPR/privacy policy legal drafting beyond an initial checklist —
  needed before piloting with EU companies handling supplier PII, but
  it's a content/legal task, not an infrastructure blocker, and can run
  in parallel with the technical blocks.

---

## 1. Production architecture

**Proposal: keep the three-subdomain split as originally conceived —
challenged, and it holds up.**

I looked for a simpler shape (single domain, path-based routing instead
of subdomains, merging the landing and the app build) and concluded the
three-subdomain split is already the least work, not more:

- The landing (`web/`) and the app (`frontend/`) are **already two
  separate build pipelines** with nothing in common (one is a
  zero-dependency static-site generator, the other an Angular CLI build)
  — merging them into one deployable would be new integration work, not
  a simplification.
- `frontend/src/environments/environment.production.ts` **already**
  hardcodes `apiBaseUrl: 'https://api.sourcelya.com/api'` — the
  subdomain split isn't a future decision, it's already baked into the
  code from FASE 1.
- A path-based alternative (`sourcelya.com/api/...`) would need a
  reverse proxy in front of both the static site and the API, which is
  an extra moving part this stack doesn't have today — subdomains let
  each piece be served directly by the platform best suited to it, no
  proxy required.

**Concrete recommendation:**

| Subdomain | What | Where |
| --- | --- | --- |
| `sourcelya.com` (+ `www.` redirecting to it) | `web/` static landing | **Cloudflare Pages** |
| `app.sourcelya.com` | `frontend/` Angular build | **Cloudflare Pages** (second project) |
| `api.sourcelya.com` | `backend/` FastAPI | A small always-on container host — see below |

**Why Cloudflare Pages for both static sites**: Cloudflare already
manages this domain's DNS (per the brief), so no second DNS relationship
is introduced; the free tier has no bandwidth limit and supports custom
domains, HTTPS, and preview deploys on every push out of the box;
`web/README.md` already anticipated exactly this ("Netlify / Vercel /
Cloudflare Pages" as the deploy target) before this phase started. This
is a genuinely free, low-maintenance choice for both static properties —
not a compromise.

**Backend hosting — this is the one real decision to make.** FastAPI
needs a process that stays running (not a static host), but doesn't need
its own database or file storage (both are Supabase). Three reasonable
options, in order of recommendation:

1. **Render.com** (recommended default) — connects directly to the
   GitHub repo, builds the existing `backend/Dockerfile`
   (`alembic upgrade head && uvicorn ...` is already the container's
   command), free HTTPS + custom domain, environment variables managed
   in a dashboard (not in git). Smallest always-on paid tier is
   inexpensive (see cost section) and avoids the "cold start" problem of
   free-tier serverless hosts, which matters because a supplier opening
   a public link should never see a 30-second delay.
2. **Fly.io** — comparable price/simplicity, CLI-driven instead of
   dashboard-driven; a fine alternative if we later want the backend and
   a self-hosted malware scanner to share one always-on machine (see
   Section 7, pending — this is the one place where Fly's
   full-VM model might beat Render's).
3. **Railway** — also comparable; mentioned for completeness, no
   strong reason to prefer it over Render for this codebase.

No new stack, no code changes needed to deploy to any of the three — the
existing `backend/Dockerfile` is already host-agnostic. This is a
hosting-account decision, not an engineering one; I'd default to Render
unless there's a reason to prefer one of the alternatives once we reach
Section 7 (malware scanning) and see whether a self-hosted scanner
pushes us toward Fly's fuller VM model instead.

**Domains** (Section 22, previewed here since it's part of the same
decision): `sourcelya.com` canonical, `www.sourcelya.com` → 301 redirect
to it (a one-line Cloudflare Page Rule / Redirect Rule), `app.` and
`api.` as separate CNAME/A records pointed at whatever Cloudflare Pages
and the chosen backend host each provide once they exist. HTTPS is
automatic and mandatory on all three with Cloudflare in front — no
manual certificate work.

## 2. Cost estimate — 0–5 pilot companies, 100–500 documents/month

| Item | Type | Estimate | Notes |
| --- | --- | --- | --- |
| Domain (`sourcelya.com`) | FIXED | ~$10–15/**year** (already owned) | Not a new monthly cost |
| DNS (Cloudflare) | FREE | $0 | Free plan covers DNS + Pages |
| Landing hosting (Cloudflare Pages) | FREE | $0 | No bandwidth cap on the free tier |
| App hosting (Cloudflare Pages) | FREE | $0 | Same free tier, second project |
| Backend hosting (Render or equivalent) | FIXED | ~$7–25/month | $7/mo tier is likely enough for 5 pilots; upsizing to fit a self-hosted malware scanner (Section 7) could push this to ~$20–25/mo — real decision pending that block |
| Database (Supabase Postgres) | FREE or FIXED | $0–25/month | Free tier plausibly enough for this volume, **but** free Supabase projects pause after a week of inactivity — a real risk for a pilot-facing link. Pro ($25/mo) removes that risk. Flagged for a decision in the Supabase block, not picked here |
| Storage (Supabase Storage) | Included / USAGE BASED | ~$0 at this volume | 100–500 documents/month at typical PDF sizes is a few GB at most — well inside any Supabase plan's included storage |
| Auth (Supabase Auth) | Included | $0 | No separate cost |
| Email (Resend) | FREE or USAGE BASED | ~$0 | Resend's free tier (thousands of emails/month) comfortably covers 5 pilot companies' worth of request/follow-up/reminder emails |
| Anthropic extraction | USAGE BASED | ~$2–40/month | At Opus 5 pricing and this doc's own README estimate ($0.02–$0.08/doc); see Section 9 for a cheaper-model option that could roughly halve this — not decided yet |
| Malware scanning | FREE (self-hosted) or USAGE BASED (API) | $0 direct, or folded into backend hosting tier | See Section 7 (pending) — leaning self-hosted ClamAV for the confidentiality requirement, which shows up as a hosting-tier cost, not a line item |
| Monitoring/logging | FREE | $0 | Hosting provider's own log viewer is enough at this scale — no Sentry needed yet (see G) |
| CI (GitHub Actions) | FREE | $0 | Free-tier minutes comfortably cover this repo's test suite size |

**Realistic total: roughly $10–50/month**, with the range driven by
exactly two decisions we haven't made yet: the Supabase plan (free vs.
$25/mo Pro) and how big the backend instance needs to be once malware
scanning is added. Nothing here requires spending anything before we
choose to.

---

## Full checklist (Section 35 of the brief)

Filled in as each block below actually gets done and verified — nothing
is checked off from a plan alone.

- [x] production architecture — decided above (Cloudflare Pages ×2 + a
      small always-on container host for the API)
- [x] cost estimate — see above
- [ ] domain — NEEDS USER ACTION (Cloudflare access to add records, once
      hosting targets exist)
- [ ] HTTPS — BLOCKED on domain/hosting
- [ ] landing — mostly DONE already; possible copy touch-up only
- [ ] frontend — NEEDS USER ACTION (Cloudflare Pages project)
- [ ] backend — NEEDS USER ACTION (Render/Fly/Railway account)
- [ ] database — NEEDS USER ACTION (Supabase project)
- [ ] migrations — DONE locally; NEEDS USER ACTION to run against the
      real production database once it exists
- [ ] auth — NEEDS USER ACTION (Supabase project) + verification pass
- [ ] storage — NEEDS USER ACTION (Supabase bucket) + verification pass
- [ ] email — NEEDS USER ACTION (Resend account + domain verification)
- [ ] SPF/DKIM/DMARC — BLOCKED on email account existing
- [ ] Anthropic — NEEDS USER ACTION (API key) + model decision (Section 9)
- [ ] real extraction — BLOCKED on the above
- [ ] malware scanning — BLOCKED (needs its own design block)
- [ ] rate limiting — BLOCKED (implementation, no external dependency)
- [ ] upload limits — BLOCKED (implementation, no external dependency)
- [ ] token security — DONE (audited above, A)
- [ ] CORS — BLOCKED on knowing the real frontend origins
- [ ] security headers — BLOCKED (implementation, no external dependency)
- [ ] secrets — DONE in shape (env-var based, git-ignored); NEEDS USER
      ACTION to actually populate production secrets in the hosting
      provider once chosen
- [ ] logging — mostly DONE; correlation IDs are a small pending add
- [ ] backups — BLOCKED on Supabase plan decision (their backup policy
      differs by plan)
- [ ] privacy/GDPR checklist — POST-PILOT-adjacent but should start in
      parallel; not begun
- [ ] delete procedure — not begun
- [ ] demo company — not begun
- [ ] demo documents — not begun
- [ ] E2E (already done for FASE 1–6 against local Postgres) — NEEDS
      re-run against the deployed stack once it exists
- [ ] production smoke test — BLOCKED on deployment existing

---

## Infra decision: where does Sourcelya's backend live? (A vs. B vs. C)

Before touching Supabase, the account/org question needs deciding first
— it changes what the Supabase block below actually does. Comparing
three options, optimized for **2–5 pilots, 100–500 documents/month,
minimum fixed cost, minimum risk** — not for scale.

**One fact I don't have and won't assume**: whether the existing
Luna y Papel / InfanApp Supabase organization is *currently* on the
Free or Pro plan, and how many projects already live in it. That
changes Option A's real marginal cost by up to $25/month, so Option A
below is given as two branches instead of one number. Everything else
here doesn't depend on that fact.

**What doesn't change across any of the three options**: this
codebase's `SupabaseStorageService` and `security.py` (JWKS
verification) call the Supabase SDK/API directly — there is no generic
S3/OAuth abstraction layer today. That's an existing FASE 1–4 design
choice, not something this decision reopens. It matters here because it
means *Postgres* is the only one of the three pieces (Postgres/Auth/
Storage) that's actually swappable for a different vendor without
touching code — `DATABASE_URL` is just a SQLAlchemy connection string.
Swapping Auth or Storage to a non-Supabase vendor means rewriting real,
already-tested, already-secure code before the first pilot — that's the
central tension in Option B below.

### A) Add Sourcelya as a third project in the existing Pro org

| | |
| --- | --- |
| **Monthly cost** | **If the org is already Pro**: ~$0–10/month marginal (Sourcelya's own project compute add-on only — the $25/mo org base is already sunk cost, shared with the other two products). **If the org is still Free today**: ~$25+/month, because Option A means upgrading that org to Pro, and that $25 base is then a cost *this decision* introduces, not one Sourcelya alone would otherwise need at pilot scale. |
| **Includes** | No auto-pause, daily backups (typically ~7-day retention on Pro), higher storage/egress/MAU quotas, all shared at the org level. |
| **Doesn't include** | Isolation from the other two products' outages, quota pressure, or billing changes — a spike in *any* of the three projects' usage shows up on the same invoice and same org dashboard. |
| **Complexity** | Lowest to set up (a few clicks in an org you already administer). |
| **Security** | Each project still gets its own isolated Postgres/Auth/Storage instance under Supabase's model — no data mixing between products at the database level. The real exposure isn't data mixing, it's **operational coupling**: the same org owner/billing contact, the same org-level settings, and (per the audit's own top risk) if Sourcelya's public portal is ever hit by a runaway-cost scenario before rate limiting ships, it's on the same invoice as two live consumer products. |
| **Backups** | Whatever the org's Pro plan already provides, for free (marginal cost is genuinely ~$0 for this specific line item if already Pro). |
| **Auth** | Zero code changes — same Supabase Auth integration this codebase already has. |
| **Storage** | Zero code changes — same `SupabaseStorageService`, new bucket in the new project. |
| **Migration effort from today** | Lowest of the three: create a project, point `.env`/hosting secrets at it, done. |
| **Lock-in** | Same Supabase lock-in the codebase already has (see above) — Option A doesn't add any *new* lock-in, it just also couples Sourcelya's continuity to two unrelated products' continuity. |
| **Recommendation** | Only makes sense if the org is **already** Pro *and* you're comfortable with that operational coupling. Given Sourcelya is a distinct product for a distinct (B2B, compliance-adjacent) audience from two consumer apps, I'd still lean away from this even at $0 marginal cost — see C. |

### B) Keep Luna y Papel / InfanApp as-is; give Sourcelya its own cheap stack

This splits into two real sub-options, because "a cheap combination of
Postgres/Auth/Storage" means very different things depending on whether
Supabase itself stays in the mix:

**B1 — a separate Supabase project (Free tier), just not in the same org as the other two.** This is functionally identical to Option C below (same vendor, same zero-code-change property, same isolation) — the only distinction from C is *which org* holds it. See C for the full comparison; there's no reason to prefer "a second free project crammed into the existing org" over "a clean second org" once you're already creating a new project, and free-tier orgs are commonly capped at 2 active free projects — if Luna y Papel + InfanApp already occupy both slots, B1 may not even be available without upgrading or pausing one of them. **Effectively: B1 collapses into C.**

**B2 — genuinely different vendors** (e.g., Neon or Railway for Postgres, Auth0/Clerk/a self-rolled auth for Auth, Cloudflare R2/Backblaze B2 for Storage):

| | |
| --- | --- |
| **Monthly cost** | Likely the cheapest on paper — most of these have generous free tiers too (Neon free Postgres, Cloudflare R2's free egress, etc.) — plausibly $0–10/month. |
| **Includes** | Whatever each vendor's free/cheapest tier includes — varies per vendor, needs its own research pass if chosen. |
| **Doesn't include** | Any of it talks to any of the others — three separate dashboards, three separate credential sets to rotate, three separate incident surfaces instead of one. |
| **Complexity** | **Highest of the three options.** Not because any single vendor is hard, but because "Postgres here, Auth there, Storage somewhere else" is more moving parts to operate than one platform, right at the moment (first pilots) when operational simplicity matters most. |
| **Security** | Each vendor's own model — nothing wrong with any of them individually, but it means re-doing the JWT verification threat-modeling work this codebase already did for Supabase JWKS (see README's security section) for a new provider, from scratch, before the first pilot. |
| **Backups** | Vendor-dependent, needs its own research per vendor. |
| **Auth** | **Requires rewriting `app/core/security.py` and the frontend's Supabase Auth client integration** — not a config change, a real engineering task with its own tests, done under time pressure before a pilot, which directly conflicts with "mínimo riesgo." |
| **Storage** | **Requires rewriting `SupabaseStorageService`** — same category of real work as Auth above. |
| **Migration effort from today** | **Highest of the three** — this is the one option that's genuinely new code, not a config/account decision. |
| **Lock-in** | Trades Supabase lock-in for a different vendor's lock-in on each piece — not actually less lock-in overall, just different, at the cost of real engineering time to get there. |
| **Recommendation** | **Not recommended before the first pilot.** The cost savings versus B1/C (a free Supabase project) are close to zero at this volume, while the engineering risk and time cost are real and immediate. This is worth revisiting later purely on its own merits (e.g., if a specific vendor's Auth product is genuinely better for Sourcelya's needs) — not as a cost-driven decision now. |

### C) Sourcelya in its own, separate Supabase organization

| | |
| --- | --- |
| **Monthly cost** | **$0/month to start** (a fresh org's Free tier), with the option to upgrade *this org specifically* to Pro ($25/month) later, purely when Sourcelya's own usage or reliability needs justify it — not coupled to the other two products' plans. |
| **Includes** | Everything the Free tier includes today (see the Section 2 cost table above): ~500MB DB, ~1GB storage, Auth included, no cost while validating pilots. |
| **Doesn't include** | No auto-scaling protection against the free tier's own limits (500MB DB, 1GB storage) — very unlikely to matter at 100–500 documents/month early on, but worth watching. **No paid-tier backups** — free-tier Supabase projects don't get the daily-backup feature Pro does; this is a real gap the audit already flagged and it applies identically whether this project sits alone or alongside the other two, so it doesn't change the A-vs-C comparison, only whether it's fixed via upgrading *this* org later. **Free-tier project pause after ~1 week of inactivity** — same caveat as in the original cost table; a `curl` against `/api/health` on a schedule, or just enough pilot activity, avoids it in practice. |
| **Complexity** | Same as A: a few clicks, this time in a brand-new org. Marginally more account-management overhead (a separate login/billing contact to track) — trivial at this scale. |
| **Security** | **Best isolation of the three options** — Sourcelya's pilot companies' supplier data, documents, and auth users never share an organization, a billing account, or an admin surface with two unrelated consumer products. This also directly helps the GDPR/privacy checklist item already in this doc: a data-processing/subprocessor disclosure for Sourcelya's pilots is simpler to write and reason about when Sourcelya's infrastructure footprint doesn't also encompass unrelated consumer-app data. |
| **Backups** | Same free-tier gap as everywhere else at $0/month; identical upgrade path to Pro, scoped only to Sourcelya, whenever it's justified. |
| **Auth** | Zero code changes. |
| **Storage** | Zero code changes. |
| **Migration effort from today** | Same as A — lowest of the three, a project-creation task, not an engineering task. |
| **Lock-in** | Same pre-existing Supabase lock-in as every option that keeps Supabase (A, B1, C) — no better or worse than A on this axis. |
| **Contractual reasonableness** | Running a second, independent Supabase organization for a genuinely separate product under the same person/company is standard SaaS practice, not a workaround — this isn't "tricking" a per-account free-tier limit, it's the normal shape of "one org per product line." The one thing worth a two-minute check before creating it: Supabase's current Terms of Service / free-tier policy on multiple organizations per billing identity, since free-tier limits are exactly the kind of detail providers adjust over time — I'd rather you glance at supabase.com's current pricing/terms page yourself than have me assert certainty about a contract I can't verify live. |
| **Recommendation** | **This is my recommendation.** Zero engineering risk (same integrations, same code), zero coupling to Luna y Papel/InfanApp's reliability or billing, $0/month to start, and it keeps the door open to upgrade Sourcelya to Pro on its own timeline — purely driven by Sourcelya's own pilot traction, not shared with unrelated products. |

### Summary

| | A (shared Pro org) | B2 (multi-vendor) | C (separate org, recommended) |
| --- | --- | --- | --- |
| Cost at pilot scale | $0–10/mo *if already Pro*, $25+/mo if not | ~$0–10/mo | $0/mo |
| Code changes needed | None | Auth + Storage rewrite | None |
| Isolation from other products | Low | N/A (not applicable) | High |
| Risk before first pilot | Low (but coupled) | High (new untested integrations) | Lowest |
| Recommendation | Only if already Pro and coupling is acceptable | Not now | **Yes** |

*(B1 is omitted from this table because it's the same thing as C, just
in the existing org instead of a new one — see B1's note above.)*

---

## Next block

Stopping here per your instruction — no Supabase or provider account has
been touched. Once you confirm which of A/B/C to go with (and, if A,
confirm whether that org is currently Free or Pro so I can pin the exact
number), the next block is **Section 3 (Supabase)**: exact click-by-click
instructions for what to create, which value to copy where, and never
more secrets than the specific step needs.
