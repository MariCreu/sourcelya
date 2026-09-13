import { DatePipe } from '@angular/common';
import { HttpErrorResponse } from '@angular/common/http';
import { Component, inject, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { AnalyticsService } from '../../../core/analytics.service';
import { LocaleService } from '../../../core/i18n/locale.service';
import { BackendApiService } from '../../../core/services/backend-api.service';
import {
  ComplianceRequest,
  REQUEST_STATUS_BADGE_CLASSES,
  RequestStatus
} from '../../../core/services/compliance-request.models';
import {
  ConfidenceLevel,
  ConflictResolution,
  ExtractedField,
  ExtractedFieldConflict
} from '../../../core/services/extracted-field.models';
import { ExtractionStatus, SupplierDocument } from '../../../core/services/supplier-document.models';
import { formatFileSize } from '../../../core/util/format-file-size';
import { TopNavComponent } from '../../../shared/top-nav/top-nav.component';

const EXTRACTION_STATUS_BADGE_CLASSES: Record<ExtractionStatus, string> = {
  pending: 'status-orange',
  processing: 'status-orange',
  completed: 'status-green',
  failed: 'status-red',
  review_required: 'status-red'
};

const CONFIDENCE_BADGE_CLASSES: Record<ConfidenceLevel, string> = {
  high: 'status-green',
  medium: 'status-orange',
  low: 'status-red'
};

@Component({
  selector: 'app-request-detail',
  standalone: true,
  imports: [DatePipe, FormsModule, RouterLink, TopNavComponent],
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

  expandedDocumentId = signal<string | null>(null);
  extractedFieldsByDocument = signal<Record<string, ExtractedField[]>>({});
  loadingFieldsDocumentId = signal<string | null>(null);
  retryingDocumentId = signal<string | null>(null);
  reviewingFieldId = signal<string | null>(null);
  conflictByFieldId = signal<Record<string, ExtractedFieldConflict>>({});

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

  extractionStatusBadgeClass(status: ExtractionStatus): string {
    return EXTRACTION_STATUS_BADGE_CLASSES[status];
  }

  confidenceBadgeClass(confidence: ConfidenceLevel): string {
    return CONFIDENCE_BADGE_CLASSES[confidence];
  }

  fieldLabel(fieldName: string): string {
    const labels = this.t().requests.detail.fieldLabels as Record<string, string>;
    return labels[fieldName] ?? fieldName;
  }

  isExpanded(document: SupplierDocument): boolean {
    return this.expandedDocumentId() === document.id;
  }

  extractedFieldsFor(document: SupplierDocument): ExtractedField[] {
    return this.extractedFieldsByDocument()[document.id] ?? [];
  }

  toggleFields(document: SupplierDocument): void {
    if (this.isExpanded(document)) {
      this.expandedDocumentId.set(null);
      return;
    }
    this.expandedDocumentId.set(document.id);
    if (this.extractedFieldsByDocument()[document.id]) {
      return;
    }
    this.loadingFieldsDocumentId.set(document.id);
    this.api.listExtractedFields(document.id).subscribe({
      next: (fields) => {
        this.extractedFieldsByDocument.update((current) => ({ ...current, [document.id]: fields }));
        this.loadingFieldsDocumentId.set(null);
      },
      error: () => {
        this.actionError.set(this.t().requests.detail.actionError);
        this.loadingFieldsDocumentId.set(null);
      }
    });
  }

  retryExtraction(document: SupplierDocument): void {
    this.retryingDocumentId.set(document.id);
    this.actionError.set(null);
    this.api.retryExtraction(document.id).subscribe({
      next: () => {
        this.retryingDocumentId.set(null);
        this.extractedFieldsByDocument.update((current) => {
          const next = { ...current };
          delete next[document.id];
          return next;
        });
        this.load();
      },
      error: () => {
        this.actionError.set(this.t().requests.detail.actionError);
        this.retryingDocumentId.set(null);
      }
    });
  }

  private replaceField(documentId: string, updated: ExtractedField): void {
    this.extractedFieldsByDocument.update((current) => ({
      ...current,
      [documentId]: (current[documentId] ?? []).map((field) =>
        field.id === updated.id ? updated : field
      )
    }));
  }

  accept(document: SupplierDocument, field: ExtractedField, resolution?: ConflictResolution): void {
    this.reviewingFieldId.set(field.id);
    this.actionError.set(null);
    this.api
      .acceptExtractedField(document.id, field.id, { conflict_resolution: resolution ?? null })
      .subscribe({
        next: (updated) => {
          this.replaceField(document.id, updated);
          this.conflictByFieldId.update((current) => {
            const next = { ...current };
            delete next[field.id];
            return next;
          });
          this.reviewingFieldId.set(null);
          this.load();
        },
        error: (err: HttpErrorResponse) => {
          this.reviewingFieldId.set(null);
          if (err.status === 409 && err.error?.detail?.detail === 'POSSIBLE CONFLICT') {
            this.conflictByFieldId.update((current) => ({
              ...current,
              [field.id]: err.error.detail as ExtractedFieldConflict
            }));
          } else {
            this.actionError.set(this.t().requests.detail.actionError);
          }
        }
      });
  }

  reject(document: SupplierDocument, field: ExtractedField): void {
    this.reviewingFieldId.set(field.id);
    this.actionError.set(null);
    this.api.rejectExtractedField(document.id, field.id).subscribe({
      next: (updated) => {
        this.replaceField(document.id, updated);
        this.reviewingFieldId.set(null);
        this.load();
      },
      error: () => {
        this.actionError.set(this.t().requests.detail.actionError);
        this.reviewingFieldId.set(null);
      }
    });
  }

  conflictFor(field: ExtractedField): ExtractedFieldConflict | null {
    return this.conflictByFieldId()[field.id] ?? null;
  }
}
