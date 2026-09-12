import { Component, computed, inject, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { BackendApiService } from '../../core/services/backend-api.service';
import { Company } from '../../core/services/company.models';
import { Product } from '../../core/services/product.models';
import { TopNavComponent } from '../../shared/top-nav/top-nav.component';

@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [FormsModule, RouterLink, TopNavComponent],
  templateUrl: './dashboard.component.html',
  styleUrl: './dashboard.component.scss'
})
export class DashboardComponent implements OnInit {
  private readonly api = inject(BackendApiService);

  loading = signal(true);
  company = signal<Company | null>(null);
  products = signal<Product[]>([]);
  errorMessage = signal<string | null>(null);

  companyName = '';
  companyCountry = '';
  onboarding = signal(false);

  readonly greenCount = computed(
    () => this.products().filter((product) => product.status === 'green').length
  );
  readonly orangeCount = computed(
    () => this.products().filter((product) => product.status === 'orange').length
  );
  readonly redCount = computed(
    () => this.products().filter((product) => product.status === 'red').length
  );

  ngOnInit(): void {
    this.loadCurrentUser();
  }

  private loadCurrentUser(): void {
    this.loading.set(true);
    this.api.getCurrentUser().subscribe({
      next: (result) => {
        this.company.set(result.company);
        this.loading.set(false);
        if (result.company) {
          this.loadProducts();
        }
      },
      error: () => {
        this.errorMessage.set('Could not load your account.');
        this.loading.set(false);
      }
    });
  }

  private loadProducts(): void {
    this.api.listProducts().subscribe({
      next: (products) => this.products.set(products),
      error: () => this.errorMessage.set('Could not load products.')
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
}
