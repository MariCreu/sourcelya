import { Component, inject, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { LocaleService } from '../../../core/i18n/locale.service';
import { BackendApiService } from '../../../core/services/backend-api.service';
import { PACKAGING_TYPES, PackagingType } from '../../../core/services/packaging-component.models';
import { ProductDetail } from '../../../core/services/product.models';
import { TopNavComponent } from '../../../shared/top-nav/top-nav.component';

@Component({
  selector: 'app-product-detail',
  standalone: true,
  imports: [FormsModule, RouterLink, TopNavComponent],
  templateUrl: './product-detail.component.html',
  styleUrl: '../../../shared/list-page.scss'
})
export class ProductDetailComponent implements OnInit {
  private readonly route = inject(ActivatedRoute);
  private readonly api = inject(BackendApiService);
  private readonly localeService = inject(LocaleService);

  readonly t = this.localeService.t;
  readonly packagingTypes = PACKAGING_TYPES;

  loading = signal(true);
  product = signal<ProductDetail | null>(null);
  errorMessage = signal<string | null>(null);
  creating = signal(false);
  showForm = signal(false);

  name = '';
  packagingType: PackagingType = 'box';
  material = '';
  weightGrams: number | null = null;
  recycledContentPercentage: number | null = null;

  private get productId(): string {
    return this.route.snapshot.paramMap.get('productId')!;
  }

  packagingTypeLabel(value: string): string {
    const labels = this.t().packagingTypes as Record<string, string>;
    return labels[value] ?? value;
  }

  formatMissingFields(fields: string[]): string {
    const labels: Record<string, string> = {
      packaging_type: this.t().productDetail.form.packagingTypeLabel,
      material: this.t().productDetail.form.materialLabel,
      weight_grams: this.t().productDetail.form.weightLabel,
      recycled_content_percentage: this.t().productDetail.form.recycledLabel
    };
    return fields.map((field) => labels[field] ?? field).join(', ');
  }

  ngOnInit(): void {
    this.load();
  }

  private load(): void {
    this.loading.set(true);
    this.api.getProduct(this.productId).subscribe({
      next: (product) => {
        this.product.set(product);
        this.loading.set(false);
      },
      error: () => {
        this.errorMessage.set(this.t().productDetail.notFoundError);
        this.loading.set(false);
      }
    });
  }

  addComponent(): void {
    this.creating.set(true);
    this.errorMessage.set(null);
    this.api
      .createPackagingComponent(this.productId, {
        name: this.name,
        packaging_type: this.packagingType,
        material: this.material || null,
        weight_grams: this.weightGrams,
        recycled_content_percentage: this.recycledContentPercentage
      })
      .subscribe({
        next: () => {
          this.name = '';
          this.material = '';
          this.weightGrams = null;
          this.recycledContentPercentage = null;
          this.showForm.set(false);
          this.creating.set(false);
          this.load(); // refresh so the product's overall status recomputes
        },
        error: () => {
          this.errorMessage.set(this.t().productDetail.form.genericError);
          this.creating.set(false);
        }
      });
  }
}
