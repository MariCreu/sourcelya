import { Injectable } from '@angular/core';

/**
 * Shared event taxonomy with the public site's analytics.js — keep the two
 * lists in sync. `landing_view`, `primary_cta_click` and
 * `secondary_cta_click` happen on the public site (web/), not here.
 *
 * Fired from this app today: `signup_started`, `signup_completed`,
 * `supplier_added`. The rest are reserved for features that don't exist
 * yet — `compliance_request_created`/`compliance_request_sent` need
 * `ComplianceRequest` (FASE 3); `supplier_request_opened`/
 * `supplier_request_submitted` need the public supplier portal (FASE 3/4).
 * Listed now so the full funnel is one type, not something rediscovered
 * and bolted on per phase.
 */
export type AnalyticsEvent =
  | 'signup_started'
  | 'signup_completed'
  | 'supplier_added'
  | 'compliance_request_created'
  | 'compliance_request_sent'
  | 'supplier_request_opened'
  | 'supplier_request_submitted';

interface AnalyticsPayload {
  event: AnalyticsEvent;
  properties: Record<string, unknown>;
  timestamp: string;
}

/**
 * No analytics provider (GA4, Plausible, PostHog, ...) is wired up yet, and
 * no cookies are set — deliberately, on both counts. What matters now is a
 * single call site with a fixed event taxonomy, so plugging in a real
 * provider later is a one-method change here instead of a hunt through
 * every component for ad-hoc tracking calls. Prefer a privacy-friendly/
 * cookieless provider when one is added, if it covers what's needed — that
 * keeps this MVP out of cookie-consent-banner territory for longer.
 */
@Injectable({ providedIn: 'root' })
export class AnalyticsService {
  private readonly queue: AnalyticsPayload[] = [];

  track(event: AnalyticsEvent, properties: Record<string, unknown> = {}): void {
    const payload: AnalyticsPayload = { event, properties, timestamp: new Date().toISOString() };
    this.queue.push(payload);
    // eslint-disable-next-line no-console
    console.debug('[sourcelya:analytics]', payload);
  }
}
