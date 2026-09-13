import { Injectable, computed, signal } from '@angular/core';
import { DICTIONARIES } from './dictionaries';
import type { Dictionary } from './dictionaries';

export type AppLocale = 'es' | 'en';

const STORAGE_KEY = 'sourcelya:locale';

/**
 * Single source of truth for the app's current language and its
 * translations. Spanish is the default — Sourcelya's first commercial
 * validation is in Spain (see backend app/domain/enums.py Locale) — with
 * English available from day one since the product is European/
 * international.
 *
 * Deliberately not `@angular/localize`: that needs a separate build per
 * locale, which doesn't fit a runtime switcher and adds real build
 * complexity for an app this early. A signal holding the active
 * dictionary is enough — components read `i18n.t()` in templates and
 * re-render automatically when the locale changes, same as any other
 * signal.
 *
 * Only the minimal existing journey (nav, login, signup, onboarding) plus
 * FASE 2's new screens (suppliers, products) are translated — see the
 * root README's i18n section for what's deliberately still English-only
 * and why.
 */
@Injectable({ providedIn: 'root' })
export class LocaleService {
  readonly locale = signal<AppLocale>(this.readInitialLocale());
  readonly t = computed<Dictionary>(() => DICTIONARIES[this.locale()]);

  setLocale(locale: AppLocale): void {
    this.locale.set(locale);
    try {
      localStorage.setItem(STORAGE_KEY, locale);
    } catch {
      // Private browsing / storage disabled — the choice just won't persist.
    }
  }

  private readInitialLocale(): AppLocale {
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      if (stored === 'es' || stored === 'en') {
        return stored;
      }
    } catch {
      // Fall through to the default.
    }
    return 'es';
  }
}
