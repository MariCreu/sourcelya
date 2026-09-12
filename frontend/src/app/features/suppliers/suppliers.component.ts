import { Component, inject, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { BackendApiService } from '../../core/services/backend-api.service';
import { Supplier } from '../../core/services/supplier.models';
import { TopNavComponent } from '../../shared/top-nav/top-nav.component';

@Component({
  selector: 'app-suppliers',
  standalone: true,
  imports: [FormsModule, TopNavComponent],
  templateUrl: './suppliers.component.html',
  styleUrl: '../../shared/list-page.scss'
})
export class SuppliersComponent implements OnInit {
  private readonly api = inject(BackendApiService);

  loading = signal(true);
  suppliers = signal<Supplier[]>([]);
  errorMessage = signal<string | null>(null);
  creating = signal(false);
  showForm = signal(false);

  name = '';
  email = '';
  country = '';

  ngOnInit(): void {
    this.load();
  }

  private load(): void {
    this.loading.set(true);
    this.api.listSuppliers().subscribe({
      next: (suppliers) => {
        this.suppliers.set(suppliers);
        this.loading.set(false);
      },
      error: () => {
        this.errorMessage.set('Could not load suppliers.');
        this.loading.set(false);
      }
    });
  }

  createSupplier(): void {
    this.creating.set(true);
    this.errorMessage.set(null);
    this.api
      .createSupplier({
        name: this.name,
        email: this.email,
        country: this.country ? this.country.toUpperCase() : null
      })
      .subscribe({
        next: (supplier) => {
          this.suppliers.update((current) => [...current, supplier]);
          this.name = '';
          this.email = '';
          this.country = '';
          this.showForm.set(false);
          this.creating.set(false);
        },
        error: () => {
          this.errorMessage.set('Could not create the supplier. Check the fields and try again.');
          this.creating.set(false);
        }
      });
  }
}
