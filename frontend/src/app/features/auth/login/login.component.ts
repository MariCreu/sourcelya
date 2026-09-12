import { Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { AuthService } from '../../../core/auth/auth.service';

@Component({
  selector: 'app-login',
  standalone: true,
  imports: [FormsModule, RouterLink],
  templateUrl: './login.component.html',
  styleUrl: '../auth-form.scss'
})
export class LoginComponent {
  private readonly authService = inject(AuthService);
  private readonly router = inject(Router);

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
      this.errorMessage.set(error instanceof Error ? error.message : 'Could not log in.');
    } finally {
      this.loading.set(false);
    }
  }
}
