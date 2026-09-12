import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';
import { Company, CreateCompanyPayload, CurrentUser } from './company.models';
import {
  CreatePackagingComponentPayload,
  PackagingComponent,
  UpdatePackagingComponentPayload
} from './packaging-component.models';
import { CreateProductPayload, Product, ProductDetail, UpdateProductPayload } from './product.models';
import { CreateSupplierPayload, Supplier, UpdateSupplierPayload } from './supplier.models';

@Injectable({ providedIn: 'root' })
export class BackendApiService {
  private readonly http = inject(HttpClient);
  private readonly baseUrl = environment.apiBaseUrl;

  getCurrentUser(): Observable<CurrentUser> {
    return this.http.get<CurrentUser>(`${this.baseUrl}/auth/me`);
  }

  createCompany(payload: CreateCompanyPayload): Observable<Company> {
    return this.http.post<Company>(`${this.baseUrl}/companies`, payload);
  }

  listSuppliers(): Observable<Supplier[]> {
    return this.http.get<Supplier[]>(`${this.baseUrl}/suppliers`);
  }

  createSupplier(payload: CreateSupplierPayload): Observable<Supplier> {
    return this.http.post<Supplier>(`${this.baseUrl}/suppliers`, payload);
  }

  updateSupplier(supplierId: string, payload: UpdateSupplierPayload): Observable<Supplier> {
    return this.http.patch<Supplier>(`${this.baseUrl}/suppliers/${supplierId}`, payload);
  }

  listProducts(): Observable<Product[]> {
    return this.http.get<Product[]>(`${this.baseUrl}/products`);
  }

  getProduct(productId: string): Observable<ProductDetail> {
    return this.http.get<ProductDetail>(`${this.baseUrl}/products/${productId}`);
  }

  createProduct(payload: CreateProductPayload): Observable<Product> {
    return this.http.post<Product>(`${this.baseUrl}/products`, payload);
  }

  updateProduct(productId: string, payload: UpdateProductPayload): Observable<Product> {
    return this.http.patch<Product>(`${this.baseUrl}/products/${productId}`, payload);
  }

  createPackagingComponent(
    productId: string,
    payload: CreatePackagingComponentPayload
  ): Observable<PackagingComponent> {
    return this.http.post<PackagingComponent>(
      `${this.baseUrl}/products/${productId}/packaging-components`,
      payload
    );
  }

  updatePackagingComponent(
    productId: string,
    componentId: string,
    payload: UpdatePackagingComponentPayload
  ): Observable<PackagingComponent> {
    return this.http.patch<PackagingComponent>(
      `${this.baseUrl}/products/${productId}/packaging-components/${componentId}`,
      payload
    );
  }
}
