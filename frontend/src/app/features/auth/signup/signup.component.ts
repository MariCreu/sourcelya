import { Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { AuthService } from '../../../core/auth/auth.service';

@Component({
  selector: 'app-signup',
  standalone: true,
  imports: [FormsModule, RouterLink],
  templateUrl: './signup.component.html',
  styleUrl: '../auth-form.scss'
})
export class SignupComponent {
  private readonly authService = inject(AuthService);

  email = '';
  password = '';
  loading = signal(false);
  errorMessage = signal<string | null>(null);
  submitted = signal(false);

  async onSubmit(): Promise<void> {
    this.errorMessage.set(null);
    this.loading.set(true);
    try {
      await this.authService.signUp(this.email, this.password);
      this.submitted.set(true);
    } catch (error) {
      this.errorMessage.set(error instanceof Error ? error.message : 'Could not sign up.');
    } finally {
      this.loading.set(false);
    }
  }
}
