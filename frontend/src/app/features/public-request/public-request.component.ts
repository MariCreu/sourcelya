import { HttpErrorResponse } from '@angular/common/http';
import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute } from '@angular/router';
import { AnalyticsService } from '../../core/analytics.service';
import { DICTIONARIES } from '../../core/i18n/dictionaries';
import { BackendApiService } from '../../core/services/backend-api.service';
import {
  PublicComplianceRequest,
  PublicPackagingComponentUpdate
} from '../../core/services/public-request.models';
import { formatFileSize } from '../../core/util/format-file-size';

type LoadError = 'invalid' | 'expired' | 'revoked' | 'generic';

/**
 * The supplier's public portal — reachable only by knowing the token in the
 * URL, no login, ever (see backend PublicRequestService). Deliberately its
 * own standalone page: no <app-top-nav>, no app shell, no shared
 * list-page.scss — a supplier who has never heard of Sourcelya should see
 * a plain, mobile-friendly form, not the authenticated product's UI.
 *
 * Language follows `ComplianceRequest.language` (chosen by the company when
 * the request was created), never the visiting browser's own preference —
 * so this reads directly from DICTIONARIES by that field instead of using
 * LocaleService/the locale switcher, which are for the authenticated app.
 */
@Component({
  selector: 'app-public-request',
  standalone: true,
  imports: [FormsModule],
  templateUrl: './public-request.component.html',
  styleUrl: './public-request.component.scss'
})
export class PublicRequestComponent implements OnInit {
  private readonly route = inject(ActivatedRoute);
  private readonly api = inject(BackendApiService);
  private readonly analytics = inject(AnalyticsService);

  loading = signal(true);
  loadError = signal<LoadError | null>(null);
  request = signal<PublicComplianceRequest | null>(null);
  formValues = signal<Partial<Record<string, PublicPackagingComponentUpdate>>>({});

  saving = signal(false);
  submitting = signal(false);
  saveMessage = signal<string | null>(null);
  actionError = signal<string | null>(null);

  uploading = signal(false);
  deletingDocumentId = signal<string | null>(null);
  uploadError = signal<string | null>(null);

  readonly pt = computed(
    () => DICTIONARIES[this.request()?.language ?? 'es'].publicRequest
  );

  // FASE 6: only COMPLETED is truly final — SUBMITTED-but-incomplete stays
  // editable so the supplier can keep going without a company action
  // being required first (a follow-up round just narrows *what's shown as
  // needed*, via isFollowUpMode/isFieldEditable below).
  readonly isFinal = computed(() => this.request()?.status === 'completed');

  // True once the supplier has submitted at least once and something is
  // still outstanding — drives the "ALMOST THERE" scoped view instead of
  // the full first-time form.
  readonly isFollowUpMode = computed(
    () => this.request()?.submitted_at != null && !this.isFinal()
  );

  readonly missingFieldKeys = computed(() => {
    const keys = new Set<string>();
    for (const ref of this.request()?.missing_fields ?? []) {
      keys.add(`${ref.packaging_component_id}:${ref.field_name}`);
    }
    return keys;
  });

  private get token(): string {
    return this.route.snapshot.paramMap.get('token')!;
  }

  ngOnInit(): void {
    this.load();
  }

  private load(): void {
    this.loading.set(true);
    this.loadError.set(null);
    this.api.getPublicRequest(this.token).subscribe({
      next: (request) => {
        this.request.set(request);
        this.formValues.set(this.buildFormValues(request));
        this.loading.set(false);
        // Fired on every successful view, not only the very first one: the
        // public read response doesn't tell the frontend whether this was
        // the request's first-ever open (only the backend's REQUEST_OPENED
        // audit event is that precise) — see the FASE 3 report's
        // simplifications section.
        this.analytics.track('supplier_request_opened');
      },
      error: (err: HttpErrorResponse) => {
        this.loadError.set(this.classifyError(err));
        this.loading.set(false);
      }
    });
  }

  private buildFormValues(
    request: PublicComplianceRequest
  ): Record<string, PublicPackagingComponentUpdate> {
    const values: Record<string, PublicPackagingComponentUpdate> = {};
    for (const product of request.products) {
      for (const component of product.packaging_components) {
        values[component.id] = {
          id: component.id,
          material: component.material,
          weight_grams: component.weight_grams,
          recycled_content_percentage: component.recycled_content_percentage,
          packaging_reference: component.packaging_reference,
          notes: component.notes
        };
      }
    }
    return values;
  }

  isFieldEditable(componentId: string, fieldName: string): boolean {
    if (this.isFinal()) return false;
    if (fieldName === 'notes') return true; // never a "requested" field — always safe to add/edit
    if (!this.isFollowUpMode()) return true;
    return this.missingFieldKeys().has(`${componentId}:${fieldName}`);
  }

  fieldLabel(fieldName: string): string {
    const labels = this.pt().almostThereFieldLabels as Record<string, string>;
    return labels[fieldName] ?? fieldName;
  }

  private classifyError(err: HttpErrorResponse): LoadError {
    if (err.status === 404) return 'invalid';
    if (err.status === 410) return 'expired';
    if (err.status === 403) return 'revoked';
    return 'generic';
  }

  updateField(
    componentId: string,
    field: Exclude<keyof PublicPackagingComponentUpdate, 'id'>,
    value: unknown
  ): void {
    this.formValues.update((current) => ({
      ...current,
      [componentId]: {
        ...current[componentId],
        id: componentId,
        [field]: value === '' ? null : value
      }
    }));
  }

  save(): void {
    this.saving.set(true);
    this.actionError.set(null);
    this.saveMessage.set(null);
    const components = Object.values(this.formValues()).filter(
      (value): value is PublicPackagingComponentUpdate => value !== undefined
    );
    this.api.savePublicRequest(this.token, { components }).subscribe({
      next: (request) => {
        this.request.set(request);
        this.formValues.set(this.buildFormValues(request));
        this.saveMessage.set(this.pt().saveSuccess);
        this.saving.set(false);
      },
      error: () => {
        this.actionError.set(this.pt().genericError);
        this.saving.set(false);
      }
    });
  }

  submit(): void {
    if (!confirm(this.pt().submitConfirm)) {
      return;
    }
    this.submitting.set(true);
    this.actionError.set(null);
    this.api.submitPublicRequest(this.token).subscribe({
      next: (request) => {
        this.request.set(request);
        this.submitting.set(false);
        this.analytics.track('supplier_request_submitted');
      },
      error: () => {
        this.actionError.set(this.pt().genericError);
        this.submitting.set(false);
      }
    });
  }

  formatFileSize(bytes: number): string {
    return formatFileSize(bytes);
  }

  onFileSelected(event: Event): void {
    const input = event.target as HTMLInputElement;
    const file = input.files?.[0];
    input.value = ''; // allow re-selecting the same file later
    if (!file) return;

    this.uploading.set(true);
    this.uploadError.set(null);
    this.api.uploadPublicDocument(this.token, file).subscribe({
      next: (request) => {
        this.request.set(request);
        this.uploading.set(false);
      },
      error: (err: HttpErrorResponse) => {
        if (err.status === 400) {
          this.uploadError.set(this.pt().uploadErrorUnsupportedType);
        } else if (err.status === 413) {
          this.uploadError.set(this.pt().uploadErrorTooLarge);
        } else {
          this.uploadError.set(this.pt().genericError);
        }
        this.uploading.set(false);
      }
    });
  }

  deleteDocument(documentId: string): void {
    if (!confirm(this.pt().confirmDelete)) {
      return;
    }
    this.deletingDocumentId.set(documentId);
    this.uploadError.set(null);
    this.api.deletePublicDocument(this.token, documentId).subscribe({
      next: (request) => {
        this.request.set(request);
        this.deletingDocumentId.set(null);
      },
      error: () => {
        this.uploadError.set(this.pt().genericError);
        this.deletingDocumentId.set(null);
      }
    });
  }
}
