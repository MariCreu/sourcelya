import { Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { AnalyticsService } from '../../../core/analytics.service';
import { AuthService } from '../../../core/auth/auth.service';
import { BRAND } from '../../../core/brand';

@Component({
  selector: 'app-signup',
  standalone: true,
  imports: [FormsModule, RouterLink],
  templateUrl: './signup.component.html',
  styleUrl: '../auth-form.scss'
})
export class SignupComponent {
  private readonly authService = inject(AuthService);
  private readonly analytics = inject(AnalyticsService);

  readonly brand = BRAND;

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
      this.errorMessage.set(error instanceof Error ? error.message : 'Could not sign up.');
    } finally {
      this.loading.set(false);
    }
  }
}
