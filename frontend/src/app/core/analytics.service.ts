import { Injectable } from '@angular/core';

/**
 * Shared event taxonomy with the public site's analytics.js — keep the two
 * lists in sync. `landing_view`, `primary_cta_click` and
 * `secondary_cta_click` happen on the public site (web/), not here; they're
 * listed for reference so the full picture lives in one place conceptually.
 */
export type AnalyticsEvent =
  | 'signup_started'
  | 'signup_completed'
  | 'supplier_added'
  | 'compliance_request_sent'; // not fired yet — FASE 3 adds compliance requests

interface AnalyticsPayload {
  event: AnalyticsEvent;
  properties: Record<string, unknown>;
  timestamp: string;
}

/**
 * No analytics provider (GA4, Plausible, PostHog, ...) is wired up yet —
 * deliberately. What matters now is a single call site with a fixed event
 * taxonomy, so plugging in a real provider later is a one-method change
 * here instead of a hunt through every component for ad-hoc tracking calls.
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
