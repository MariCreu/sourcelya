import { Component, inject, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { BackendApiService } from '../../core/services/backend-api.service';
import { Product } from '../../core/services/product.models';
import { Supplier } from '../../core/services/supplier.models';
import { TopNavComponent } from '../../shared/top-nav/top-nav.component';

@Component({
  selector: 'app-products',
  standalone: true,
  imports: [FormsModule, RouterLink, TopNavComponent],
  templateUrl: './products.component.html',
  styleUrl: '../../shared/list-page.scss'
})
export class ProductsComponent implements OnInit {
  private readonly api = inject(BackendApiService);

  loading = signal(true);
  products = signal<Product[]>([]);
  suppliers = signal<Supplier[]>([]);
  errorMessage = signal<string | null>(null);
  creating = signal(false);
  showForm = signal(false);

  name = '';
  sku = '';
  description = '';
  supplierId = '';

  ngOnInit(): void {
    this.load();
  }

  private load(): void {
    this.loading.set(true);
    this.api.listProducts().subscribe({
      next: (products) => {
        this.products.set(products);
        this.loading.set(false);
      },
      error: () => {
        this.errorMessage.set('Could not load products.');
        this.loading.set(false);
      }
    });
    this.api.listSuppliers().subscribe({ next: (suppliers) => this.suppliers.set(suppliers) });
  }

  supplierName(supplierId: string | null): string {
    if (!supplierId) return '—';
    return this.suppliers().find((supplier) => supplier.id === supplierId)?.name ?? '—';
  }

  createProduct(): void {
    this.creating.set(true);
    this.errorMessage.set(null);
    this.api
      .createProduct({
        name: this.name,
        sku: this.sku || null,
        description: this.description || null,
        supplier_id: this.supplierId || null
      })
      .subscribe({
        next: (product) => {
          this.products.update((current) => [...current, product]);
          this.name = '';
          this.sku = '';
          this.description = '';
          this.supplierId = '';
          this.showForm.set(false);
          this.creating.set(false);
        },
        error: () => {
          this.errorMessage.set('Could not create the product. Check the fields and try again.');
          this.creating.set(false);
        }
      });
  }
}
