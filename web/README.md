# sourcelya.com — public site

The public marketing/SEO site, deliberately separate from `frontend/`
(`app.sourcelya.com`, the authenticated Angular app) and `backend/`
(`api.sourcelya.com`). See the [Domains](../README.md#domains) section of the
root README for the full three-part split.

## Why a plain static site, not Angular SSR

Angular does support prerendering/SSG (and full SSR via `@angular/ssr`), and
that would have been the other reasonable option here. Plain static HTML
won out for this task on all three stated priorities:

1. **Indexability** — a crawler gets fully-formed HTML with zero JavaScript
   execution required. There's no hydration mismatch risk, no "will the
   prerenderer actually run for this route" question — the file on disk *is*
   the page.
2. **Performance** — no framework runtime, no hydration cost, no Node SSR
   server to keep warm. Lighthouse scores 100/100/100/100 (Performance /
   Accessibility / Best Practices / SEO) locally — see the root README's
   [FASE: public landing site](../README.md) section for the full run.
3. **Simplicity** — zero build step. Bundling this page into the `frontend`
   Angular project (even just for SSG) would also blur the conceptual
   separation the domain split is meant to express: this site's release
   cadence, hosting, and tech stack have no reason to be coupled to the
   authenticated app's.

If this site's content outgrows a handful of hand-written pages (the
`/guides/...` section in particular could get there), the next step is a
lightweight static site generator (e.g. Eleventy) for templating — not
Angular, and not a CMS, per the brief's explicit "no CMS yet."

## Running locally

No build step, no dependencies. Any static file server works:

```bash
npx serve web            # or: python3 -m http.server --directory web 5050
```

Then open the printed URL. The two CTA buttons and the "Log in" link point
at `https://app.sourcelya.com/...`, which won't resolve locally (no DNS is
configured yet, on purpose — see the brief) — that's expected, not a bug.

## Deploying

This is a fully static site: HTML, CSS, and one small JS file, no server
runtime required. Point any static host or CDN's document root at this
directory:

- Netlify / Vercel / Cloudflare Pages: set the project root to `web/`, no
  build command.
- S3 + CloudFront, or an Nginx box: sync/copy this directory as-is.

Whichever host serves `sourcelya.com` should route to this directory;
`app.sourcelya.com` and `api.sourcelya.com` are separate deployments
(`frontend/` and `backend/` respectively) — see the root README.

## Adding future pages

The brief asks for the structure to support pages like `/ppwr`,
`/ppwr/importers`, `/ppwr/suppliers`, `/ppwr/checker`, `/guides/...`,
`/dpp/...` **without building them now**. For a static site, a clean URL
like `/ppwr` is just a directory with its own `index.html`:

```
web/
  index.html          -> /
  ppwr/
    index.html        -> /ppwr
    importers/
      index.html      -> /ppwr/importers
  guides/
    index.html        -> /guides
```

Every mainstream static host (Netlify, Vercel, Cloudflare Pages, S3+CloudFront
with the right config, GitHub Pages) serves `/path/` from `path/index.html`
automatically — no routing config to write. When a new page ships, also add
its `<loc>` to `sitemap.xml`.

## SEO/technical checklist (this page)

- [x] Unique, descriptive `<title>` and meta description
- [x] `rel=canonical`
- [x] Open Graph (`og:title`, `og:description`, `og:type`, `og:url`,
      `og:site_name`) — `og:image` intentionally omitted until a real
      1200×630 image exists; a missing one is better than a broken one
- [x] Basic Twitter card tags
- [x] `robots.txt` (allow all, points at the sitemap)
- [x] `sitemap.xml`
- [x] Single `<h1>`, semantic landmarks (`header`/`nav`/`main`/`section`/
      `footer`), each section labelled via `aria-labelledby`
- [x] Skip-to-content link, visible `:focus-visible` outlines
- [x] Responsive down to ~360px width, no horizontal scroll
- [x] `Organization` JSON-LD block

## Analytics

`analytics.js` defines the event taxonomy and a `track()` function; no
provider (GA4, Plausible, PostHog, ...) is wired up yet, on purpose — see
that file's header comment. It fires `landing_view` on load and
`primary_cta_click` / `secondary_cta_click` on the CTA buttons (anything
with a `data-analytics-event` attribute is tracked automatically). The
Angular app mirrors the same taxonomy in
`frontend/src/app/core/analytics.service.ts` for the events that happen
there instead (`signup_started`, `signup_completed`, `supplier_added`,
`compliance_request_sent` — the last one not fired yet since compliance
requests don't exist until FASE 3).
