import { Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { AuthService } from '../../../core/auth/auth.service';
import { LocaleSwitchComponent } from '../../../core/i18n/locale-switch/locale-switch.component';
import { LocaleService } from '../../../core/i18n/locale.service';

@Component({
  selector: 'app-login',
  standalone: true,
  imports: [FormsModule, RouterLink, LocaleSwitchComponent],
  templateUrl: './login.component.html',
  styleUrl: '../auth-form.scss'
})
export class LoginComponent {
  private readonly authService = inject(AuthService);
  private readonly router = inject(Router);
  private readonly localeService = inject(LocaleService);

  readonly t = this.localeService.t;

  email = '';
  password = '';
  loading = signal(false);
  errorMessage = signal<string | null>(null);

  async onSubmit(): Promise<void> {
    this.errorMessage.set(null);
    this.loading.set(true);
    try {
      await this.authService.signIn(this.email, this.password);
      await this.router.navigateByUrl('/dashboard');
    } catch (error) {
      // Supabase's own error message (e.g. "Invalid login credentials") is
      // shown as-is when present — we don't fabricate a translation for
      // text a third party controls. Our own copy is what's localized.
      this.errorMessage.set(error instanceof Error ? error.message : this.t().auth.login.genericError);
    } finally {
      this.loading.set(false);
    }
  }
}
