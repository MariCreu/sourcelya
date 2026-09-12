#!/usr/bin/env node
'use strict';

/**
 * Zero-dependency static site generator for the public landing page.
 *
 * Why this exists instead of hand-writing es/index.html and en/index.html
 * separately: the brief is explicit that translations must be centralized,
 * not duplicated per page. The alternative to a tiny build script here
 * would be a real framework (Next.js, Astro, Eleventy...) — overkill for
 * one page in two languages, and exactly the "don't introduce a framework
 * just because" the brief warns against. This script is ~100 lines, has no
 * npm dependencies, and its only job is: read content/<locale>.json, fill
 * in templates/page.html, write <locale>/index.html. Output is committed
 * to the repo (see README) so the site works with zero build step at
 * deploy time; re-run this after editing content or the template.
 */

const fs = require('fs');
const path = require('path');

const ROOT = __dirname;
const SITE_URL = 'https://sourcelya.com';
const LOCALES = ['es', 'en'];
const DEFAULT_LOCALE = 'es'; // Spain-first go-to-market — see brief.
const OG_LOCALES = { es: 'es_ES', en: 'en_US' };
const LAST_MOD = '2026-09-12';

// The one place the app's URL is configured — every CTA/login link in the
// template reads from here instead of a hardcoded string, so pointing this
// site at a different app environment (or, later, a real PPWR checker
// instead of straight to signup) is a one-line change here.
const APP_BASE_URL = 'https://app.sourcelya.com';
const APP_SIGNUP_URL = `${APP_BASE_URL}/signup`;
const APP_LOGIN_URL = `${APP_BASE_URL}/login`;

function flatten(value, prefix, out) {
  if (Array.isArray(value)) {
    value.forEach((item, index) => flatten(item, `${prefix}.${index}`, out));
  } else if (value && typeof value === 'object') {
    for (const [key, nested] of Object.entries(value)) {
      flatten(nested, prefix ? `${prefix}.${key}` : key, out);
    }
  } else {
    out[prefix] = String(value);
  }
  return out;
}

function render(template, data) {
  return template.replace(/{{\s*([\w.]+)\s*}}/g, (match, key) => {
    if (!(key in data)) {
      throw new Error(`Missing translation key "${key}" (looked for it while rendering)`);
    }
    return data[key];
  });
}

function buildPages() {
  const template = fs.readFileSync(path.join(ROOT, 'templates', 'page.html'), 'utf8');

  for (const locale of LOCALES) {
    const contentPath = path.join(ROOT, 'content', `${locale}.json`);
    const content = JSON.parse(fs.readFileSync(contentPath, 'utf8'));
    const data = flatten(content, '', {});

    data.canonicalUrl = `${SITE_URL}/${locale}/`;
    data.alternateEs = `${SITE_URL}/es/`;
    data.alternateEn = `${SITE_URL}/en/`;
    data.alternateDefault = `${SITE_URL}/${DEFAULT_LOCALE}/`;
    data.ogLocale = OG_LOCALES[locale];
    data.appSignupUrl = APP_SIGNUP_URL;
    data.appLoginUrl = APP_LOGIN_URL;

    const html = render(template, data);
    const outDir = path.join(ROOT, locale);
    fs.mkdirSync(outDir, { recursive: true });
    fs.writeFileSync(path.join(outDir, 'index.html'), html);
    console.log(`built ${locale}/index.html`);
  }
}

function buildRootRedirect() {
  const template = fs.readFileSync(path.join(ROOT, 'templates', 'redirect.html'), 'utf8');
  const html = template.replace(/{{DEFAULT_LOCALE}}/g, DEFAULT_LOCALE);
  fs.writeFileSync(path.join(ROOT, 'index.html'), html);
  console.log(`built index.html (redirects to /${DEFAULT_LOCALE}/)`);
}

function buildSitemap() {
  const urls = LOCALES.map(
    (locale) => `  <url>
    <loc>${SITE_URL}/${locale}/</loc>
    <xhtml:link rel="alternate" hreflang="es" href="${SITE_URL}/es/" />
    <xhtml:link rel="alternate" hreflang="en" href="${SITE_URL}/en/" />
    <xhtml:link rel="alternate" hreflang="x-default" href="${SITE_URL}/${DEFAULT_LOCALE}/" />
    <lastmod>${LAST_MOD}</lastmod>
    <changefreq>weekly</changefreq>
    <priority>1.0</priority>
  </url>`
  ).join('\n');

  const sitemap = `<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:xhtml="http://www.w3.org/1999/xhtml">
${urls}
</urlset>
`;
  fs.writeFileSync(path.join(ROOT, 'sitemap.xml'), sitemap);
  console.log('built sitemap.xml');
}

buildPages();
buildRootRedirect();
buildSitemap();
