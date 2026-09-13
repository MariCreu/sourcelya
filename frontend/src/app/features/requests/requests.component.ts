import { DatePipe } from '@angular/common';
import { Component, inject, OnInit, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { LocaleService } from '../../core/i18n/locale.service';
import { BackendApiService } from '../../core/services/backend-api.service';
import {
  ComplianceRequest,
  REQUEST_STATUS_BADGE_CLASSES,
  RequestStatus
} from '../../core/services/compliance-request.models';
import { TopNavComponent } from '../../shared/top-nav/top-nav.component';

@Component({
  selector: 'app-requests',
  standalone: true,
  imports: [DatePipe, RouterLink, TopNavComponent],
  templateUrl: './requests.component.html',
  styleUrl: '../../shared/list-page.scss'
})
export class RequestsComponent implements OnInit {
  private readonly api = inject(BackendApiService);
  private readonly localeService = inject(LocaleService);

  readonly t = this.localeService.t;

  loading = signal(true);
  requests = signal<ComplianceRequest[]>([]);
  errorMessage = signal<string | null>(null);

  ngOnInit(): void {
    this.loading.set(true);
    this.api.listRequests().subscribe({
      next: (requests) => {
        this.requests.set(requests);
        this.loading.set(false);
      },
      error: () => {
        this.errorMessage.set(this.t().requests.loadError);
        this.loading.set(false);
      }
    });
  }

  productSummary(request: ComplianceRequest): string {
    return request.products.map((product) => product.product_name).join(', ');
  }

  languageLabel(request: ComplianceRequest): string {
    return this.t().requests.languageLabels[request.language] ?? request.language;
  }

  lastActivity(request: ComplianceRequest): string | null {
    return (
      request.submitted_at ?? request.opened_at ?? request.sent_at ?? request.created_at ?? null
    );
  }

  statusBadgeClass(status: RequestStatus): string {
    return REQUEST_STATUS_BADGE_CLASSES[status];
  }
}
