import { Injectable, signal } from '@angular/core';
import { Session } from '@supabase/supabase-js';
import { supabase } from './supabase-client';

/**
 * Thin wrapper around Supabase Auth. Sourcelya never implements its own
 * signup/login/password logic — Supabase owns that entirely, and the
 * backend only ever verifies the resulting access token (see
 * backend/app/core/security.py). This service exists so the rest of the
 * app never imports the Supabase SDK directly.
 */
@Injectable({ providedIn: 'root' })
export class AuthService {
  readonly session = signal<Session | null>(null);
  readonly initialized = signal(false);

  constructor() {
    supabase.auth.getSession().then(({ data }) => {
      this.session.set(data.session);
      this.initialized.set(true);
    });

    supabase.auth.onAuthStateChange((_event, session) => {
      this.session.set(session);
    });
  }

  async signUp(email: string, password: string) {
    const { error } = await supabase.auth.signUp({ email, password });
    if (error) throw error;
  }

  async signIn(email: string, password: string) {
    const { error } = await supabase.auth.signInWithPassword({ email, password });
    if (error) throw error;
  }

  async signOut() {
    await supabase.auth.signOut();
  }

  get accessToken(): string | null {
    return this.session()?.access_token ?? null;
  }

  get isAuthenticated(): boolean {
    return this.session() !== null;
  }
}
