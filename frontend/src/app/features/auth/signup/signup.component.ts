import { Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { AnalyticsService } from '../../../core/analytics.service';
import { AuthService } from '../../../core/auth/auth.service';
import { LocaleSwitchComponent } from '../../../core/i18n/locale-switch/locale-switch.component';
import { LocaleService } from '../../../core/i18n/locale.service';

@Component({
  selector: 'app-signup',
  standalone: true,
  imports: [FormsModule, RouterLink, LocaleSwitchComponent],
  templateUrl: './signup.component.html',
  styleUrl: '../auth-form.scss'
})
export class SignupComponent {
  private readonly authService = inject(AuthService);
  private readonly analytics = inject(AnalyticsService);
  private readonly localeService = inject(LocaleService);

  readonly t = this.localeService.t;

  email = '';
  password = '';
  loading = signal(false);
  errorMessage = signal<string | null>(null);
  submitted = signal(false);

  async onSubmit(): Promise<void> {
    this.errorMessage.set(null);
    this.loading.set(true);
    this.analytics.track('signup_started');
    try {
      await this.authService.signUp(this.email, this.password);
      this.submitted.set(true);
      this.analytics.track('signup_completed');
    } catch (error) {
      // Supabase's own error message is shown as-is when present — see the
      // same note in login.component.ts.
      this.errorMessage.set(
        error instanceof Error ? error.message : this.t().auth.signup.genericError
      );
    } finally {
      this.loading.set(false);
    }
  }
}
