import { Component, computed, inject, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { AnalyticsService } from '../../../core/analytics.service';
import { LocaleService } from '../../../core/i18n/locale.service';
import { BackendApiService } from '../../../core/services/backend-api.service';
import { RequestLanguage } from '../../../core/services/compliance-request.models';
import { Product } from '../../../core/services/product.models';
import { Supplier } from '../../../core/services/supplier.models';
import { TopNavComponent } from '../../../shared/top-nav/top-nav.component';

@Component({
  selector: 'app-new-request',
  standalone: true,
  imports: [FormsModule, RouterLink, TopNavComponent],
  templateUrl: './new-request.component.html',
  styleUrl: '../../../shared/list-page.scss'
})
export class NewRequestComponent implements OnInit {
  private readonly api = inject(BackendApiService);
  private readonly analytics = inject(AnalyticsService);
  private readonly localeService = inject(LocaleService);
  private readonly router = inject(Router);

  readonly t = this.localeService.t;

  loading = signal(true);
  suppliers = signal<Supplier[]>([]);
  products = signal<Product[]>([]);
  errorMessage = signal<string | null>(null);
  submitting = signal(false);

  supplierId = '';
  language: RequestLanguage = 'es';
  selectedProductIds = signal<Set<string>>(new Set());

  readonly productsForSupplier = computed(() =>
    this.products().filter((product) => product.supplier_id === this.supplierId)
  );

  ngOnInit(): void {
    this.loading.set(true);
    this.api.listSuppliers().subscribe({ next: (suppliers) => this.suppliers.set(suppliers) });
    this.api.listProducts().subscribe({
      next: (products) => {
        this.products.set(products);
        this.loading.set(false);
      },
      error: () => this.loading.set(false)
    });
  }

  onSupplierChange(): void {
    this.selectedProductIds.set(new Set());
  }

  isProductSelected(productId: string): boolean {
    return this.selectedProductIds().has(productId);
  }

  toggleProduct(productId: string, checked: boolean): void {
    this.selectedProductIds.update((current) => {
      const next = new Set(current);
      if (checked) {
        next.add(productId);
      } else {
        next.delete(productId);
      }
      return next;
    });
  }

  createRequest(): void {
    const productIds = Array.from(this.selectedProductIds());
    if (productIds.length === 0) {
      this.errorMessage.set(this.t().requests.new.needsAtLeastOneProduct);
      return;
    }

    this.submitting.set(true);
    this.errorMessage.set(null);
    this.api
      .createRequest({ supplier_id: this.supplierId, product_ids: productIds, language: this.language })
      .subscribe({
        next: (request) => {
          this.analytics.track('compliance_request_created', {
            supplier_id: request.supplier_id,
            product_count: request.products.length
          });
          this.submitting.set(false);
          this.router.navigate(['/requests', request.id]);
        },
        error: () => {
          this.errorMessage.set(this.t().requests.new.genericError);
          this.submitting.set(false);
        }
      });
  }
}
