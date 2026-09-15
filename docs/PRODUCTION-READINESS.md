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

## Decision: Option C, Pro plan

**Confirmed** (correcting the earlier draft of Option C, which assumed a
second Free project would be available): Supabase currently caps an
account at **2 active Free projects total across every organization**
where that account is Owner/Admin, not 2 per organization. Luna y Papel
and InfanApp already occupy both. A new organization for Sourcelya
therefore cannot also be Free — it goes straight to **Pro** (~$25/month
fixed), specifically to avoid rewriting Auth/Storage (Option B2) and to
avoid the Free tier's auto-pause behavior. Luna y Papel and InfanApp are
untouched. Sourcelya's Supabase organization, billing, and (initially)
lone project are fully separate from both.

## Supabase setup — step by step (Block 2, in progress)

Nothing here has been done yet. Steps 1–5 are manual actions in the
Supabase dashboard — stop after each numbered step and wait for
confirmation before doing the next one; nothing downstream (Render,
Cloudflare, email, Anthropic, malware scanning) starts until this whole
block is done and verified.

### 1. Create the organization

- Go to the Supabase dashboard's organization switcher (top-left) →
  **New organization**.
- Name it **Sourcelya** (or "Sourcelya SL" if that's the registered
  legal entity — purely a label, no technical effect).
- Type: Personal or Business, whichever matches how the Anthropic/
  Resend/hosting accounts are also being registered — doesn't affect
  billing mechanics.
- This creates the org on the Free plan by default — that's fine, Pro
  gets selected next, before creating the project.

### 2. Upgrade the organization to Pro — before creating the project

- Inside the new org: **Organization Settings → Billing** (sometimes
  labeled "Subscription" or "Plans").
- Select **Pro** ($25/month base).
- Supabase will ask for a payment method at this point — that's between
  you and Supabase's checkout page, not something to route through me.
- Doing this **before** creating the project avoids any transitional
  "project created on Free, needs upgrading" step.

### 3. Create the Sourcelya project

- Inside the now-Pro org: **New project**.
- Project name: anything stable, e.g. `sourcelya` or
  `sourcelya-production` — **this name has zero technical effect**: the
  actual project URL uses an auto-generated random reference
  (`https://<random-ref>.supabase.co`), never the name you type here.
- Database password: use Supabase's **Generate a password** button
  (don't type your own). Save it immediately in a password manager. It
  never needs to be typed anywhere else by hand — the connection string
  that embeds it gets copied once, later, straight into the hosting
  provider's environment variables (a future block), never through this
  chat.

### 4. Region

- Choose **Central EU (Frankfurt)** if it's offered — best fit for
  Spain/EU customers on both latency and data-residency grounds, and a
  common default for EU-based companies for exactly that reason.
  **Ireland (West EU)** is a reasonable fallback if Frankfurt isn't
  available or you prefer it — both are genuinely in the EU.
- This choice is **permanent** — Supabase doesn't support migrating a
  project to a different region later without recreating it — so pick
  deliberately now rather than defaulting without looking.

### 5. Database settings — what to leave alone

- Nothing else needs configuring at creation time. Leave Postgres
  version, extensions, and everything else at their defaults — the
  schema itself is entirely handled by this repo's own Alembic
  migrations (see [Migrations](../README.md#migrations)) once the
  backend is wired up, not by anything set up manually in the dashboard.
- Optional, not blocking: Supabase's connection string comes in two
  forms — direct (port 5432) and pooled via PgBouncer (port 6543,
  "Transaction" mode recommended by Supabase). At 2–5 pilots' worth of
  concurrent connections either works fine; which one we use is a
  one-line decision when `DATABASE_URL` actually gets set in a later
  block, not something to decide now.

### 6. Values we'll need later (don't send them yet — just note where they live)

All under **Project Settings** once the project exists:

| Value | Where to find it | Needed for |
| --- | --- | --- |
| Project URL (`https://<ref>.supabase.co`) | Settings → API | `SUPABASE_URL` |
| `anon` public key | Settings → API | Frontend `supabaseAnonKey` |
| `service_role` key | Settings → API | Backend `SUPABASE_SERVICE_ROLE_KEY` |
| Database connection string | Settings → Database | `DATABASE_URL` |
| Database password | Wherever you saved it in step 3 | Embedded in the connection string above |

Nothing here gets created or configured in this block — this table is
just so you know where to look when we actually wire up the backend
hosting in a later block. The bucket for document storage doesn't exist
yet either — that's a small, separate step once this block is confirmed
done, still within "Supabase," not the next one.

### 7. Secret vs. public

| Value | Classification | Why |
| --- | --- | --- |
| Project URL | Public | Meant to be visible — it's just a hostname |
| `anon` public key | Public by design | Supabase explicitly designs this key to be embedded in frontend code; it grants no more access than Supabase's access rules allow |
| `service_role` key | **Secret, highest sensitivity** | Bypasses all access rules — full read/write to everything. Server-side only, in the backend's environment variables, never in frontend code, never in git |
| Database password | **Secret** | Full database access if leaked |
| Full database connection string | **Secret** | It's the password above, embedded in a URL |

**Confirmed done**: organization created (Pro), project created
(`pqvaqsvcfapiuhgfwlon.supabase.co`, region `eu-west-1` / West EU
Ireland), single project in the org as intended. Project name is still
the Supabase default ("MariCreu's Project") — purely cosmetic, optional
rename later, no functional effect.

**Note on tooling**: this session has a Supabase MCP connection
available, but `list_projects` shows it's scoped to the **existing**
organization (Luna y Papel + InfanApp only) — it does not see the new
Sourcelya project at all. That's actually a good sign for the isolation
goal (Sourcelya's org genuinely isn't reachable through whatever
connected that integration), but it also means I can't verify or
configure Sourcelya's Supabase project through tools — everything stays
manual, through the dashboard, exactly as you asked. I won't use that
MCP connection for anything Sourcelya-related.

### 8. What never to paste into this chat

To be explicit, since you asked: **nothing from step 7's "Secret" row,
ever** — not the `service_role` key, not the database password, not the
full connection string. When we reach the block where these actually get
used, they go directly from the Supabase dashboard into the hosting
provider's environment-variable UI (Render's dashboard, in the
architecture already agreed) — never typed into this conversation. If I
ever need to confirm something about a secret value, I'll ask you to
confirm its *shape* (e.g., "does the connection string start with
`postgresql://postgres.`") or confirm you've set it in the hosting
provider, never to paste the value itself.

The Project URL and the region chosen are the only two things from this
block worth telling me directly, once done — both are public/non-
sensitive and let me sanity-check we're aligned before moving on.

### 9. Storage bucket (next manual step)

- In the Sourcelya project: left sidebar → **Storage** → **New bucket**.
- Name it exactly **`sourcelya-documents`** — that's the default the
  backend already expects (`SUPABASE_STORAGE_BUCKET` in
  `backend/app/core/config.py`), so using this exact name means no extra
  environment variable override is needed later.
- **Public bucket: leave this OFF (private).** Confirmed by reading
  `SupabaseStorageService` just now — every request it makes (upload,
  download, delete, signed URL) authenticates with the `service_role`
  key, which bypasses bucket privacy/RLS entirely. There is never a
  reason for a document to be reachable by a plain public URL; the
  backend is always the one fetching it, then serving it to an
  authenticated company user.
- **No storage policies (RLS) need to be created.** Same reason: the
  backend only ever talks to Storage as `service_role`, which ignores
  bucket policies by design. Supabase may prompt you to add a policy
  when the bucket is private and empty — you can skip that prompt.
- Optional, not required: Supabase lets you set a bucket-level max file
  size and allowed MIME types at creation. The backend already enforces
  20MB / `pdf,xlsx,csv,docx,png,jpg,jpeg` on every upload
  (`MAX_UPLOAD_SIZE_MB`, `ALLOWED_UPLOAD_EXTENSIONS`), so this would only
  be a defense-in-depth duplicate, not a gap — skip it for now unless you
  want the extra belt-and-braces layer.

**Confirmed done**: `sourcelya-documents` bucket created, private.

## Supabase block — done

Everything Supabase needs for now exists: organization ("Sourcelya",
Pro), project (`pqvaqsvcfapiuhgfwlon`, `eu-west-1`), storage bucket
(`sourcelya-documents`, private, no RLS needed). The remaining values
(anon key, service_role key, connection string — step 6's table) aren't
created, they're just *read* from Settings → API / Settings → Database
when we actually configure the backend hosting — nothing more to do in
the Supabase dashboard itself until then.

## Repo cleanup (started, not finished)

Also done in this block, at your request: the GitHub repo was renamed
`prueba-tecnica` → **`sourcelya`** (GitHub auto-redirects the old URL,
all history preserved). Found in the process: the repo had a leftover
`master` branch from the *original* technical-test exercise (an
unrelated Java/Spring Boot car-pricing API) — genuinely irrelevant to
Sourcelya, safe to delete. I can't delete it myself (this session's auto
mode blocks destructive git operations, and there's no GitHub API tool
for branch deletion either) — **still pending**: delete `master` via
`github.com/MariCreu/sourcelya/branches`. The `main` branch (the repo's
default) is untouched — it only has a placeholder README; real code
still lives on `claude/packproof-saas-mvp-acqbew`, and reconciling that
is deliberately deferred to the deployment block, not done ad hoc here.

---

## Next block

Supabase is done. Waiting on your call for what's next: Render (backend
hosting), Cloudflare Pages (frontend/landing), email (Resend + DNS),
Anthropic (API key + the Sonnet 5 vs. Opus 5 decision), or malware
scanning — whichever order you'd like to tackle them in. My suggested
order (from the original audit's dependency chain) is Render next, since
the backend needs somewhere to run before email/Anthropic/malware
scanning configuration can actually be exercised end to end — but happy
to take them in whatever order you prefer.

## Render setup — step by step (Block 3, in progress)

**One real finding before the steps**: reading `backend/Dockerfile`
just now — its `CMD` is bare `uvicorn app.main:app ...`, with **no
`alembic upgrade head`** baked in. Locally, `docker-compose.yml`
supplies that via a command override; a plain Render deploy of this
same Dockerfile would start the API immediately with **no tables
created**, and every DB-touching request would fail while looking like
a "successful" deploy (container up, health check green). This gets
fixed with a Render-side start-command override in step 3 below — no
Dockerfile changes needed, same image, same local behavior.

### 1. Account + connect the repo

- Sign up at render.com — GitHub OAuth is the simplest path.
- When it asks for repository access: choose **"Only select
  repositories"** and pick just `sourcelya` — not "All repositories."
  Same least-privilege principle as everything else in this phase.

### 2. New Web Service

- Dashboard → **New → Web Service** → select the `sourcelya` repo.
- **Branch**: `claude/packproof-saas-mvp-acqbew` for now — `main` is
  still just a placeholder README (see the Repo cleanup note above), so
  it has no code to deploy. Revisit which branch is "production" before
  real pilots start; not decided here.
- **Root Directory**: `backend` — so Render finds `backend/Dockerfile`
  and uses `backend/` as the build context (mirrors
  `docker-compose.yml`'s `build: ./backend`).
- **Runtime**: Docker (should auto-detect once Root Directory is set).
- **Region**: Frankfurt — closest Render region to the Supabase project
  (Ireland) and to Spain/EU.
- **Instance type**: the smallest **paid** tier ("Starter" or
  equivalent) — **not Free**. Render's free tier sleeps after
  inactivity, which means the first supplier who opens a link after a
  quiet period would hit a cold start; not acceptable for a pilot-facing
  link. Exact current pricing: check at signup, not asserted here.

### 3. Start command override (the fix for the finding above)

Render lets you override the Dockerfile's `CMD` with a custom start
command — look for a field named **"Docker Command"** or **"Start
Command"** in the service's settings. Set it to:

```
sh -c "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"
```

This is exactly what `docker-compose.yml` already does locally — same
behavior, no Dockerfile change, migrations run automatically on every
deploy.

### 4. Environment variables — what to set now vs. later

Render's environment variable UI is where every secret below goes —
**never into this chat**. Set these now:

| Variable | Value | Notes |
| --- | --- | --- |
| `ENVIRONMENT` | `production` | |
| `DEBUG` | `false` | |
| `DATABASE_URL` | Supabase's connection string | Settings → Database → Connection string (URI). **Secret.** |
| `SUPABASE_URL` | `https://pqvaqsvcfapiuhgfwlon.supabase.co` | Public, already known |
| `SUPABASE_SERVICE_ROLE_KEY` | from Settings → API | **Secret.** |
| `SUPABASE_STORAGE_BUCKET` | `sourcelya-documents` | Matches the bucket already created — set explicitly rather than relying on the code default, so a future default change can't silently redirect production |
| `SUPABASE_JWT_STRATEGY` | `jwks` | Same reasoning — pin it explicitly rather than relying on the default |
| `INTERNAL_JOBS_SECRET` | a random value | Render has a "Generate" option for env vars — use it instead of typing one |

Leave these **unset for now** — their blocks haven't happened yet, and
leaving them unset just keeps the app in its current safe local-fallback
behavior (no real email sent, no real extraction) until we get there:
`RESEND_API_KEY`, `ANTHROPIC_API_KEY`, `DOCUMENT_EXTRACTION_PROVIDER`,
`FRONTEND_BASE_URL` (no frontend exists yet to set CORS for).

### 5. Verify

Once deployed, Render gives it a default URL like
`https://sourcelya-api.onrender.com` (or similar) before any custom
domain is attached. Check `https://<that-url>/api/health` returns
`200` — that's the point where we know both the container **and** the
migrations actually ran, not just that uvicorn started.

---

## Render block — done, with real findings along the way

The service (`sourcelya`, `srv-dakjrr95efls73e93680`) is live at
`https://sourcelya.onrender.com`, connected to the real Sourcelya
Supabase Postgres, with all five migrations applied
(`0001`–`0005`). Confirmed in the deploy logs: all five
`alembic.runtime.migration` upgrade steps, then a clean
`Uvicorn running` / `Application startup complete`, then Render's own
"Your service is live 🎉".

Once the Render MCP connector became available mid-block, configuration
moved from "give exact dashboard steps" to doing it directly — but three
real, non-obvious problems came up getting there, all now fixed:

1. **Render's "Docker Command" field doesn't parse `sh -c "cmd1 && cmd2"`
   shell syntax** — it treated the entire configured string as one
   literal (non-existent) command name and failed with "not found".
   Fixed by committing `backend/start.sh` (runs `alembic upgrade head`
   then `exec uvicorn ...`) and pointing the Docker Command at that one
   file instead — sidesteps whatever exact tokenization the platform
   field does, since there's nothing left to mis-parse.
2. **Alembic crashed on a percent-encoded character in the password**
   (`%40` for `@`) — `alembic/env.py` handed the URL straight to
   `Config.set_main_option()`, which stores it on a `ConfigParser` that
   treats a bare `%` as the start of a `%(name)s` interpolation
   reference. Fixed by escaping `%` → `%%` in that one call only (see
   the commit for why this is scoped correctly — nothing else reads
   `settings.database_url` through `ConfigParser`).
3. **Supabase's "Direct connection" string resolves to an IPv6-only
   address**, which Render's network can't reach ("Network is
   unreachable"). Fixed by switching to Supabase's connection dialog →
   Transaction pooler → **"Use IPv4 connection"** toggle ON, which gives
   a `postgres.<ref>@aws-<n>-<region>.pooler.supabase.com:6543` host
   instead. Document this for the next time a connection string is
   needed (email service, any future direct-DB tooling): always the
   IPv4 pooler form, never the bare `db.<ref>.supabase.co` direct-connect
   host.

**Also found**: the GitHub→Render auto-deploy webhook did not fire on at
least two consecutive pushes (deploys kept redeploying a stale commit
until manually triggered via `trigger_deploy`) — worth watching; if it
keeps happening, check the GitHub App's webhook delivery log on the
`sourcelya` repo.

**Still outstanding from this block**:
- [x] **Plan is Free, not Starter — deliberately, no keep-alive either.**
      A keep-alive ping was considered (every 5 or 10 min, via GitHub
      Actions or an external monitor) but rejected after checking real
      Render account mechanics: `lunasypapel-web` and `sourcelya` are
      both on the Free plan and **share the same account-wide 750
      free-instance-hours/month pool**. Instance-hours are billed by
      wall-clock uptime, not by ping frequency — any keep-alive frequent
      enough to prevent the ~15-min sleep timeout keeps the instance
      running ~730h/month regardless of interval. `lunasypapel-web`
      already likely consumes most/all of that pool by itself if kept
      awake; adding a second always-on free service risks exceeding the
      shared quota and Render suspending a service mid-month — possibly
      the one that's actually in production use. No MCP tool exists to
      read the account's actual usage-to-date (`get_metrics` returned no
      data for `lunasypapel-web`); the user should confirm current
      consumption in the Render dashboard (Workspace Settings → Billing
      → Usage) if concerned.
      **Decision: leave Sourcelya on Free with no keep-alive.** Cold
      starts (~30-50s on the first request after sleep) are an accepted
      trade-off for a 2-5 company pilot. If a demo ever needs zero
      latency, the clean fix is upgrading *only* Sourcelya to Starter
      ($7/mo) — that removes it from the shared free pool entirely
      without touching `lunasypapel-web`'s quota. Revisit if/when that
      need comes up.
- [ ] **`healthCheckPath` is empty on both `sourcelya` and
      `lunasypapel-web`** (confirmed via `get_service`). No tool in this
      Render MCP sets it (only `create_web_service`/
      `update_environment_variables`); needs the dashboard — Settings →
      Health Checks → Health Check Path → `/api/health` for Sourcelya.
      Render uses this during deploys to avoid routing traffic to a new
      instance before it's actually ready.
- [ ] **Rotate the database password.** It was pasted into this chat
      twice while debugging the connection string above — treat it as
      compromised regardless of channel privacy. This requires the user
      to do it in Supabase (Database → Reset database password) — no
      Supabase access is available from this session to do it directly.
      Once rotated, `DATABASE_URL` needs updating in Render to match.
- [x] `SUPABASE_SERVICE_ROLE_KEY` set in Render (2026-09-15). Value was
      pasted into chat — same compromised-by-channel caveat as the DB
      password; rotate later via Supabase Settings → API if full key
      hygiene is wanted, and update Render again if so.
- [x] `https://sourcelya.onrender.com/api/health` confirmed returning
      `200`/`{"status":"ok"}` from a real browser.

## Cloudflare block (frontend + landing)

No Cloudflare MCP/API access exists in this session, so this entire block
is manual clicks by the user — verified here by auditing the repo first,
not by assuming Cloudflare Pages' defaults would just work.

**Audited before instructing anything**:
- `frontend/` uses Angular's new `application` builder
  (`@angular-devkit/build-angular:application`, confirmed in
  `angular.json`). This builder **always nests browser output under a
  `browser/` subfolder** — `npm run build` was actually run here and
  confirmed output lands at `dist/frontend/browser/`, not `dist/frontend/`.
  This is the single most common Cloudflare Pages + Angular misconfig
  (pointing the build output directory at the parent folder serves the
  raw folder listing instead of the app) — called out explicitly below.
- Angular app has client-side routing (`app.routes.ts`) and no
  `_redirects` file existed yet, so a direct load/refresh of e.g.
  `/dashboard` or `/request/:token` would 404 on any static host. Added
  `frontend/public/_redirects` (`/* /index.html 200`) — Angular's asset
  pipeline copies `public/**` into the build output, confirmed present at
  `dist/frontend/browser/_redirects` after a real build.
- `web/` (the landing) already had a working `_redirects` (`/ /es/ 302`)
  from FASE 1.5 — Cloudflare Pages supports the same Netlify-style
  `_redirects` format natively, so nothing to change there.
- `frontend/src/environments/environment.production.ts` already pointed
  `apiBaseUrl` at `https://api.sourcelya.com/api` (set during the
  rebrand). `supabaseUrl` was still the `your-project.supabase.co`
  placeholder — filled in now with the real project
  (`https://pqvaqsvcfapiuhgfwlon.supabase.co`, known from the Supabase
  block). `supabaseAnonKey` is still a placeholder — needs the real
  value, which is safe to paste in chat (it's the public anon key,
  meant to ship in client code, gated by RLS — unlike the service_role
  key or DB password).
- `backend/app/main.py` builds CORS from a **single** origin
  (`allow_origins=[settings.frontend_base_url]`), and the same
  `FRONTEND_BASE_URL` setting is also what gets embedded in the
  supplier-facing `/request/:token` links sent by email
  (`compliance_request_service.py`, `follow_up_service.py`). So once
  `app.sourcelya.com` exists, `FRONTEND_BASE_URL` in Render needs
  updating to `https://app.sourcelya.com` — both CORS and supplier email
  links break otherwise. This is a Render env var (I can set it myself
  via MCP once the Cloudflare Pages custom domain step below is done),
  not a Cloudflare step.

**Real deploy attempts hit three more issues, in order** (no Cloudflare
MCP exists in this session — every fix here is either a repo change or a
manual dashboard instruction, never a direct API call):
1. The user's Cloudflare project used the newer git-connected **Workers**
   deploy flow (`npx wrangler deploy`), not classic Pages'
   build-output-directory config — failed with "Could not detect a
   directory containing static files" (for the landing) since no
   Wrangler config existed anywhere in the repo telling it which
   directory to upload. Fixed by adding `web/wrangler.jsonc` (assets
   directory `./`) and, pre-emptively, `frontend/wrangler.jsonc` (assets
   directory `./dist/frontend/browser`, `not_found_handling:
   single-page-application` for Angular's client-side router).
2. The frontend project's build then failed on
   `npm error enoent ... /opt/buildhome/repo/package.json` — the build
   command was running at the repo root, which has no `package.json`
   (each of `backend/`, `frontend/`, `web/` has its own). Root cause:
   the project's **Root directory** setting wasn't set to `frontend`.
3. After setting Root directory, deploy failed with **"root directory
   not found"** — because this repo's `main` branch is nearly empty
   (confirmed via `git ls-tree -r origin/main`: one file, `README.md`
   — all real work lives on `claude/packproof-saas-mvp-acqbew`), and the
   Cloudflare project's **Production branch** was still `main`, which
   has no `frontend/` (or `web/`) directory at all. This surfaces a
   decision that was already flagged as pending in this doc: which
   branch is actually "production." Not resolved here — for now the
   Cloudflare projects' Production branch is being pointed at
   `claude/packproof-saas-mvp-acqbew` to unblock the deploy; merging to
   `main` (or renaming what "production" means) is still open.
   "Retry deployment" on an already-failed run appears to replay that
   run's original frozen settings rather than the project's current
   config — a fresh commit (forcing a new webhook-triggered build) was
   used instead to pick up the corrected branch/root-directory settings.

**Still outstanding from this block** (all manual — see chat for the
exact click-by-click):
- [ ] Cloudflare Pages project #1: `web/` → `sourcelya.com` + `www.`
      (in progress — debugging wrangler/root-directory/branch config)
- [ ] Cloudflare Pages project #2: `frontend/` → `app.sourcelya.com`
      (not started yet — same wrangler.jsonc fix pre-applied)
- [ ] DNS: root + `www` + `app` records in Cloudflare
- [ ] `api.sourcelya.com` CNAME → the existing Render service
- [ ] Supabase anon key → fill into `environment.production.ts` and
      redeploy
- [ ] Update `FRONTEND_BASE_URL` in Render to `https://app.sourcelya.com`
      once the app subdomain resolves (I can do this part once the user
      confirms the domain is live)
- [ ] Decide the real production branch (`main` is empty; everything is
      currently deployed from the feature branch) — separate from this
      block, previously flagged, still open

## Next block

Email (Resend) or the Anthropic API key — whichever the user picks next.
