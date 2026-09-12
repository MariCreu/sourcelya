/**
 * Single source of truth for product naming/marketing copy. Nothing else in
 * the app should hardcode the product name or tagline — import this instead,
 * so a wording change (these texts are explicitly not final) or a future
 * rebrand touches one file.
 */
export const BRAND = {
  name: 'Sourcelya',
  domain: 'sourcelya.com',
  tagline: 'Supplier compliance, without the chasing.',
  explanation:
    "Collect supplier documentation, extract the data you need and instantly see what's missing.",
} as const;
