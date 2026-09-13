// Mirrors backend app/domain/enums.py RequestStatus — VARCHAR-backed on
// purpose there, so kept as a plain string union here rather than a
// generated enum.
export type RequestStatus =
  | 'draft'
  | 'sent'
  | 'opened'
  | 'in_progress'
  | 'submitted'
  | 'review_required'
  | 'completed';

export type RequestLanguage = 'es' | 'en';

export interface ComplianceRequestProductSummary {
  product_id: string;
  product_name: string;
  product_sku: string | null;
}

export interface ComplianceRequest {
  id: string;
  company_id: string;
  supplier_id: string;
  supplier_name: string;
  status: RequestStatus;
  language: RequestLanguage;
  created_at: string;
  sent_at: string | null;
  opened_at: string | null;
  submitted_at: string | null;
  completed_at: string | null;
  has_active_link: boolean;
  products: ComplianceRequestProductSummary[];
}

export interface CreateComplianceRequestPayload {
  supplier_id: string;
  product_ids: string[];
  language: RequestLanguage;
}

export interface ComplianceRequestSendResult {
  request: ComplianceRequest;
  // Only ever present in the direct response of send()/resend() — the
  // server keeps just the token's hash afterwards, so this is never
  // retrievable again (see ComplianceRequestRead.has_active_link instead).
  request_url: string;
}

// Reuses the existing green/orange/red compliance-status palette (see
// styles.scss .status-badge) instead of inventing a parallel color system
// just for request status.
export const REQUEST_STATUS_BADGE_CLASSES: Record<RequestStatus, string> = {
  draft: 'status-orange',
  sent: 'status-orange',
  opened: 'status-orange',
  in_progress: 'status-orange',
  submitted: 'status-green',
  review_required: 'status-red',
  completed: 'status-green'
};
