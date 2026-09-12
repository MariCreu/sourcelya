/**
 * Minimal analytics abstraction for the public site.
 *
 * No provider (GA4, Plausible, PostHog, ...) is wired up yet — that's a
 * deliberate FASE-later decision, not an oversight. What matters now is a
 * single function every page calls, with a fixed, shared event taxonomy, so
 * plugging in a real provider later is a one-function change here instead of
 * a hunt through every page for ad-hoc tracking calls.
 *
 * The same taxonomy is mirrored in the Angular app
 * (frontend/src/app/core/analytics.service.ts) for the events that happen
 * there instead of on this site (signup_started, signup_completed,
 * supplier_added, compliance_request_sent). Keep the two lists in sync.
 */
(function (window) {
  var EVENTS = {
    LANDING_VIEW: 'landing_view',
    PRIMARY_CTA_CLICK: 'primary_cta_click',
    SECONDARY_CTA_CLICK: 'secondary_cta_click'
    // Fired from the Angular app, not this site — listed here so the full
    // taxonomy lives in one place conceptually:
    //   signup_started, signup_completed, supplier_added,
    //   compliance_request_sent
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
