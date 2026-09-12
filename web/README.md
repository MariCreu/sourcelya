# sourcelya.com — public site

The public marketing/SEO site, deliberately separate from `frontend/`
(`app.sourcelya.com`, the authenticated Angular app) and `backend/`
(`api.sourcelya.com`). See the [Domains](../README.md#domains) section of the
root README for the full three-part split.

## i18n

Spain is the first go-to-market market, so **Spanish is the default
locale**; English exists from day one since Sourcelya is a European/
international product. URLs are `/es/` and `/en/`, the root `/` redirects
to `/es/`.

**Content is centralized, not duplicated per page.** `content/es.json` and
`content/en.json` hold every string on the page as one flat dictionary per
locale; `templates/page.html` is the single HTML structure both languages
render through. `build.js` (zero npm dependencies) flattens each JSON file
and substitutes `{{dot.path}}` tokens in the template, producing
`es/index.html` and `en/index.html`. There's no `if (locale === 'es')`
anywhere and no string is ever typed into two files — this is the same
centralization principle as `BRAND` (see `frontend/src/app/core/brand.ts`)
and `AnalyticsService`, applied to a static site instead of Angular.

Run after editing `content/*.json` or `templates/*.html`:

```bash
npm run build
```

Output (`es/index.html`, `en/index.html`, the root redirect `index.html`,
`sitemap.xml`) is committed to the repo, so the site works with zero build
step at deploy time — `npm run build` is a dev-time regeneration step, not
part of the deploy pipeline. If that stops being convenient once there's a
real CI/CD setup, running it as a build command is a one-line host config
change, not a rewrite.

**hreflang / canonical**: every page links `<link rel="alternate"
hreflang="es|en|x-default">` to both locales plus the default, and its own
`rel="canonical"` — the standard pattern for "these are language variants
of the same content," not duplicate-content signals. `sitemap.xml` lists
both URLs with the same hreflang alternates.

**Root redirect**: `index.html` at the site root is a static page with
`<meta http-equiv="refresh">` to `/es/` and a canonical pointing there —
works on literally any static host with zero configuration. `_redirects`
additionally gives Netlify a real 302 where that host is used; other hosts
(Vercel, Cloudflare Pages, S3+CloudFront) have their own equivalent
redirect-rule config to add once actually deploying, not needed now.

**Language switcher**: a small `ES | EN` pill in the header, linking to the
other locale's `/es/` or `/en/` — visible, not intrusive. No geolocation,
no cookie-based memory, per the brief.

## Why a plain static site, not Angular SSR

Angular does support prerendering/SSG (and full SSR via `@angular/ssr`),
and that would have been the other reasonable option here. Plain static
HTML (plus one tiny zero-dependency build script for i18n templating) won
out on all three stated priorities:

1. **Indexability** — a crawler gets fully-formed HTML with zero JavaScript
   execution required, in each language, at its own URL. No hydration
   mismatch risk, no "will the prerenderer actually run for this route"
   question.
2. **Performance** — no framework runtime, no hydration cost. Lighthouse:
   100/100/100/100 (Performance/Accessibility/Best Practices/SEO) on both
   `/es/` and `/en/` — see the root README's "Public landing site" section.
3. **Simplicity** — the only "build tooling" is a ~100-line script with no
   npm dependencies. Reaching for Next.js/Astro/Eleventy, or bundling this
   into the Angular app via SSR/SSG, would also blur the conceptual
   separation the domain split is meant to express: this site's release
   cadence, hosting, and tech stack have no reason to be coupled to the
   authenticated app's.

If this site's content outgrows a handful of hand-written pages (the
`/guides/...` section in particular could get there), the next step is a
real static site generator (e.g. Eleventy) for templating — not Angular,
and not a CMS, per the brief's explicit "no CMS yet."

## Running locally

```bash
npm run build   # generates es/, en/, index.html, sitemap.xml from content/
npm run dev     # build, then serve on http://localhost:5050
```

`npm run dev` just runs the build then `npx serve .` — no dependencies get
installed for either script. The two CTA buttons and the "Log in" link
point at `https://app.sourcelya.com/...`, which won't resolve locally (no
DNS is configured yet, on purpose) — expected, not a bug.

## Deploying

Fully static output: HTML, CSS, and one small JS file, no server runtime
required. Point any static host or CDN's document root at this directory:

- Netlify / Vercel / Cloudflare Pages: project root `web/`; build command
  `npm run build` if the host should regenerate on deploy, or none at all
  since the output is already committed.
- S3 + CloudFront, or an Nginx box: sync/copy this directory as-is.

Whichever host serves `sourcelya.com` should route to this directory;
`app.sourcelya.com` and `api.sourcelya.com` are separate deployments
(`frontend/` and `backend/` respectively) — see the root README.

## Adding future pages

The brief asks for the structure to support pages like `/es/ppwr`,
`/es/ppwr/importadores`, `/en/ppwr/importers`, `/es/guias/...`,
`/en/dpp/...` etc. **without building them now**. For this generator, a
new page is: a new key namespace in each `content/<locale>.json` (or a
dedicated `content/<locale>/ppwr.json` once there are enough pages that one
file per locale gets unwieldy), a template, and one more `fs.writeFileSync`
call in `build.js` per locale — the flatten/render functions are already
generic. On disk, a clean URL like `/es/ppwr` is just a directory with its
own `index.html`:

```
web/
  es/
    index.html          -> /es/
    ppwr/
      index.html        -> /es/ppwr
      importadores/
        index.html      -> /es/ppwr/importadores
  en/
    index.html          -> /en/
    ppwr/
      index.html        -> /en/ppwr
```

Every mainstream static host serves `/path/` from `path/index.html`
automatically. When a new page ships, add its `<loc>` + hreflang alternates
to `sitemap.xml` (or extend `build.js`'s `buildSitemap()` to include it
automatically, once there are enough pages that manual upkeep is a chore).

## SEO/technical checklist (this page)

- [x] Unique, descriptive `<title>` and meta description per locale
- [x] `rel=canonical` per locale
- [x] `hreflang` (es, en, x-default) on every page and in the sitemap
- [x] Open Graph (`og:title`, `og:description`, `og:type`, `og:url`,
      `og:site_name`, `og:locale`) — `og:image` intentionally omitted until
      a real 1200×630 image exists; a missing one is better than a broken
      one
- [x] Basic Twitter card tags
- [x] `robots.txt` (allow all, points at the sitemap)
- [x] `sitemap.xml` with both locales and hreflang alternates
- [x] Single `<h1>` per page, semantic landmarks (`header`/`nav`/`main`/
      `section`/`footer`), each section labelled via `aria-labelledby`
- [x] Skip-to-content link, visible `:focus-visible` outlines
- [x] Responsive down to ~360px width, no horizontal scroll
- [x] `Organization` JSON-LD block

## Analytics

`analytics.js` defines the event taxonomy and a `track()` function; no
provider is wired up, and no cookies are set — both deliberate, see that
file's header comment for the reasoning (short version: keeps this MVP out
of cookie-consent territory for longer, and a real provider is a
one-function swap whenever it's actually needed). It fires `landing_view`
on load and `primary_cta_click` / `secondary_cta_click` on the CTA buttons
(anything with a `data-analytics-event` attribute is tracked
automatically). The Angular app mirrors the same taxonomy in
`frontend/src/app/core/analytics.service.ts` for the events that happen
there instead (`signup_started`, `signup_completed`, `supplier_added` are
fired today; `compliance_request_created/sent` and
`supplier_request_opened/submitted` are reserved for FASE 3/4 features
that don't exist yet).
