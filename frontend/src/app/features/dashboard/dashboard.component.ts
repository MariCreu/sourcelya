import { Component, inject, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { AuthService } from '../../core/auth/auth.service';
import { BRAND } from '../../core/brand';
import { BackendApiService } from '../../core/services/backend-api.service';
import { Company } from '../../core/services/company.models';

@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [FormsModule],
  templateUrl: './dashboard.component.html',
  styleUrl: './dashboard.component.scss'
})
export class DashboardComponent implements OnInit {
  private readonly authService = inject(AuthService);
  private readonly api = inject(BackendApiService);
  private readonly router = inject(Router);

  readonly brand = BRAND;

  loading = signal(true);
  company = signal<Company | null>(null);
  errorMessage = signal<string | null>(null);

  companyName = '';
  companyCountry = '';
  onboarding = signal(false);

  ngOnInit(): void {
    this.loadCurrentUser();
  }

  private loadCurrentUser(): void {
    this.loading.set(true);
    this.api.getCurrentUser().subscribe({
      next: (result) => {
        this.company.set(result.company);
        this.loading.set(false);
      },
      error: () => {
        this.errorMessage.set('Could not load your account.');
        this.loading.set(false);
      }
    });
  }

  createCompany(): void {
    this.onboarding.set(true);
    this.errorMessage.set(null);
    this.api
      .createCompany({ name: this.companyName, country: this.companyCountry.toUpperCase() })
      .subscribe({
        next: (company) => {
          this.company.set(company);
          this.onboarding.set(false);
        },
        error: () => {
          this.errorMessage.set('Could not create the company. Check the fields and try again.');
          this.onboarding.set(false);
        }
      });
  }

  async logout(): Promise<void> {
    await this.authService.signOut();
    await this.router.navigateByUrl('/login');
  }
}
