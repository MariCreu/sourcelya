/**
 * Minimal analytics abstraction for the public site.
 *
 * No provider is wired up yet, and no cookies are set — deliberately, on
 * both counts. What matters now is a single function every page calls,
 * with a fixed, shared event taxonomy, so plugging in a real provider
 * later is a one-function change here instead of a hunt through every
 * page for ad-hoc tracking calls. When a provider is added, prefer a
 * privacy-friendly/cookieless one (e.g. Plausible) if it covers what's
 * needed — that keeps this MVP out of cookie-consent-banner territory for
 * longer, not because of a regulatory reading, just because a CMP is real
 * scope this product doesn't need yet.
 *
 * The full funnel this taxonomy is meant to measure, split by where each
 * event actually fires:
 *   - here (this site): landing_view, primary_cta_click, secondary_cta_click
 *   - the Angular app (frontend/src/app/core/analytics.service.ts):
 *     signup_started, signup_completed, supplier_added
 *   - not fired anywhere yet — the features don't exist until FASE 3/4:
 *     compliance_request_created, compliance_request_sent,
 *     supplier_request_opened, supplier_request_submitted
 * Keep this list and the Angular one in sync.
 */
(function (window) {
  var EVENTS = {
    LANDING_VIEW: 'landing_view',
    PRIMARY_CTA_CLICK: 'primary_cta_click',
    SECONDARY_CTA_CLICK: 'secondary_cta_click'
  };

  function track(event, properties) {
    var payload = {
      event: event,
      properties: properties || {},
      timestamp: new Date().toISOString(),
      path: window.location.pathname
    };
    window.Sourcelya.analytics.queue.push(payload);
    // Structured console output stands in for a real provider for now.
    if (window.console && console.debug) {
      console.debug('[sourcelya:analytics]', payload);
    }
  }

  window.Sourcelya = window.Sourcelya || {};
  window.Sourcelya.analytics = {
    EVENTS: EVENTS,
    queue: [],
    track: track
  };

  document.addEventListener('DOMContentLoaded', function () {
    track(EVENTS.LANDING_VIEW);

    document.querySelectorAll('[data-analytics-event]').forEach(function (el) {
      el.addEventListener('click', function () {
        track(el.getAttribute('data-analytics-event'));
      });
    });
  });
})(window);
