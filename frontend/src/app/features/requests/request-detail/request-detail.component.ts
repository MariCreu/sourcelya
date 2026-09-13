import { DatePipe } from '@angular/common';
import { Component, inject, OnInit, signal } from '@angular/core';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { AnalyticsService } from '../../../core/analytics.service';
import { LocaleService } from '../../../core/i18n/locale.service';
import { BackendApiService } from '../../../core/services/backend-api.service';
import {
  ComplianceRequest,
  REQUEST_STATUS_BADGE_CLASSES,
  RequestStatus
} from '../../../core/services/compliance-request.models';
import { SupplierDocument } from '../../../core/services/supplier-document.models';
import { formatFileSize } from '../../../core/util/format-file-size';
import { TopNavComponent } from '../../../shared/top-nav/top-nav.component';

@Component({
  selector: 'app-request-detail',
  standalone: true,
  imports: [DatePipe, RouterLink, TopNavComponent],
  templateUrl: './request-detail.component.html',
  styleUrl: '../../../shared/list-page.scss'
})
export class RequestDetailComponent implements OnInit {
  private readonly route = inject(ActivatedRoute);
  private readonly api = inject(BackendApiService);
  private readonly analytics = inject(AnalyticsService);
  private readonly localeService = inject(LocaleService);

  readonly t = this.localeService.t;

  loading = signal(true);
  request = signal<ComplianceRequest | null>(null);
  errorMessage = signal<string | null>(null);
  actionError = signal<string | null>(null);

  sending = signal(false);
  revoking = signal(false);
  resending = signal(false);
  revealedUrl = signal<string | null>(null);
  copied = signal(false);

  private get requestId(): string {
    return this.route.snapshot.paramMap.get('requestId')!;
  }

  ngOnInit(): void {
    this.load();
  }

  private load(): void {
    this.loading.set(true);
    this.api.getRequest(this.requestId).subscribe({
      next: (request) => {
        this.request.set(request);
        this.loading.set(false);
      },
      error: () => {
        this.errorMessage.set(this.t().requests.detail.notFoundError);
        this.loading.set(false);
      }
    });
  }

  send(): void {
    this.sending.set(true);
    this.actionError.set(null);
    this.api.sendRequest(this.requestId).subscribe({
      next: (result) => {
        this.request.set(result.request);
        this.revealedUrl.set(result.request_url);
        this.analytics.track('compliance_request_sent', {
          request_id: result.request.id,
          language: result.request.language
        });
        this.sending.set(false);
      },
      error: () => {
        this.actionError.set(this.t().requests.detail.actionError);
        this.sending.set(false);
      }
    });
  }

  revoke(): void {
    if (!confirm(this.t().requests.detail.confirmRevoke)) {
      return;
    }
    this.revoking.set(true);
    this.actionError.set(null);
    this.api.revokeRequest(this.requestId).subscribe({
      next: (request) => {
        this.request.set(request);
        this.revealedUrl.set(null);
        this.revoking.set(false);
      },
      error: () => {
        this.actionError.set(this.t().requests.detail.actionError);
        this.revoking.set(false);
      }
    });
  }

  resend(): void {
    this.resending.set(true);
    this.actionError.set(null);
    this.api.resendRequest(this.requestId).subscribe({
      next: (result) => {
        this.request.set(result.request);
        this.revealedUrl.set(result.request_url);
        this.resending.set(false);
      },
      error: () => {
        this.actionError.set(this.t().requests.detail.actionError);
        this.resending.set(false);
      }
    });
  }

  statusBadgeClass(status: RequestStatus): string {
    return REQUEST_STATUS_BADGE_CLASSES[status];
  }

  copyLink(): void {
    const url = this.revealedUrl();
    if (!url) return;
    navigator.clipboard?.writeText(url).then(() => {
      this.copied.set(true);
      setTimeout(() => this.copied.set(false), 2000);
    });
  }

  formatFileSize(bytes: number): string {
    return formatFileSize(bytes);
  }

  downloadDocument(document: SupplierDocument): void {
    this.api.downloadDocument(document.id).subscribe({
      next: (blob) => {
        const url = URL.createObjectURL(blob);
        const link = window.document.createElement('a');
        link.href = url;
        link.download = document.filename;
        link.click();
        URL.revokeObjectURL(url);
      },
      error: () => this.actionError.set(this.t().requests.detail.actionError)
    });
  }
}
