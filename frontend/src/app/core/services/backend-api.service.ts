import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';
import { Company, CreateCompanyPayload, CurrentUser } from './company.models';
import {
  ComplianceRequest,
  ComplianceRequestSendResult,
  CreateComplianceRequestPayload
} from './compliance-request.models';
import {
  CreatePackagingComponentPayload,
  PackagingComponent,
  UpdatePackagingComponentPayload
} from './packaging-component.models';
import { CreateProductPayload, Product, ProductDetail, UpdateProductPayload } from './product.models';
import { PublicComplianceRequest, SavePublicRequestPayload } from './public-request.models';
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

  listRequests(): Observable<ComplianceRequest[]> {
    return this.http.get<ComplianceRequest[]>(`${this.baseUrl}/requests`);
  }

  getRequest(requestId: string): Observable<ComplianceRequest> {
    return this.http.get<ComplianceRequest>(`${this.baseUrl}/requests/${requestId}`);
  }

  createRequest(payload: CreateComplianceRequestPayload): Observable<ComplianceRequest> {
    return this.http.post<ComplianceRequest>(`${this.baseUrl}/requests`, payload);
  }

  sendRequest(requestId: string): Observable<ComplianceRequestSendResult> {
    return this.http.post<ComplianceRequestSendResult>(
      `${this.baseUrl}/requests/${requestId}/send`,
      {}
    );
  }

  revokeRequest(requestId: string): Observable<ComplianceRequest> {
    return this.http.post<ComplianceRequest>(`${this.baseUrl}/requests/${requestId}/revoke`, {});
  }

  resendRequest(requestId: string): Observable<ComplianceRequestSendResult> {
    return this.http.post<ComplianceRequestSendResult>(
      `${this.baseUrl}/requests/${requestId}/resend`,
      {}
    );
  }

  // --- Public supplier portal: no auth, no company scoping — the token
  // itself is the only credential (see backend PublicRequestService). ---

  getPublicRequest(token: string): Observable<PublicComplianceRequest> {
    return this.http.get<PublicComplianceRequest>(`${this.baseUrl}/public/requests/${token}`);
  }

  savePublicRequest(
    token: string,
    payload: SavePublicRequestPayload
  ): Observable<PublicComplianceRequest> {
    return this.http.patch<PublicComplianceRequest>(
      `${this.baseUrl}/public/requests/${token}`,
      payload
    );
  }

  submitPublicRequest(token: string): Observable<PublicComplianceRequest> {
    return this.http.post<PublicComplianceRequest>(
      `${this.baseUrl}/public/requests/${token}/submit`,
      {}
    );
  }
}
