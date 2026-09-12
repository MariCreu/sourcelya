import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';
import { Company, CreateCompanyPayload, CurrentUser } from './company.models';

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
}
