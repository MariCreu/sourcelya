import { SupplierDocument } from './supplier-document.models';

// Mirrors backend app/domain/enums.py RequestStatus — VARCHAR-backed on
// purpose there, so kept as a plain string union here rather than a
// generated enum. FASE 6 removed the previously-unused `review_required`
// value — see that enum's own docstring: information-review-required is
// now a *computed* concept (InformationStatus below), never a stored
// workflow status.
export type RequestStatus = 'draft' | 'sent' | 'opened' | 'in_progress' | 'submitted' | 'completed';

export type RequestLanguage = 'es' | 'en';

// Mirrors app/domain/enums.py FieldInformationState/InformationStatus and
// app/services/missing_information_service.py — see MissingInformationService's
// module docstring for the exact deterministic rule behind each value.
export type FieldInformationState =
  | 'available'
  | 'missing'
  | 'review_required'
  | 'conflict'
  | 'not_applicable';

export type InformationStatus =
  | 'complete'
  | 'missing_information'
  | 'review_required'
  | 'conflict';

export interface FieldInformation {
  field_name: string;
  state: FieldInformationState;
  current_value: string | null;
  extracted_value: string | null;
  pending_field_id: string | null;
}

export interface ComponentInformation {
  component_id: string;
  component_name: string;
  fields: FieldInformation[];
}

export interface RequestInformationSummary {
  status: InformationStatus;
  total_requested: number;
  available_count: number;
  missing_count: number;
  review_required_count: number;
  conflict_count: number;
  unresolved_pending_count: number;
  components: ComponentInformation[];
}

export interface FollowUpRoundRef {
  packaging_component_id: string;
  field_name: string;
}

export interface FollowUpRound {
  id: string;
  round_number: number;
  requested_fields: FollowUpRoundRef[];
  trigger: 'manual' | 'automatic';
  available_count_before: number;
  missing_count_before: number;
  created_at: string;
}

export interface RecoveryStats {
  total_requested: number;
  available_after_first_submission: number | null;
  available_now: number;
  follow_up_recovered: number | null;
  recovery_rate: number | null;
}

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
  automatic_follow_up: boolean;
  products: ComplianceRequestProductSummary[];
  documents: SupplierDocument[];
  information_status: RequestInformationSummary | null;
  follow_up_rounds: FollowUpRound[];
  recovery_stats: RecoveryStats | null;
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
  submitted: 'status-orange',
  completed: 'status-green'
};

export interface EffectiveRequestBadge {
  // Key into the `requestStatusLabels` dictionary.
  labelKey: string;
  badgeClass: string;
}

// FASE 6: once a request has been submitted at least once, "submitted" by
// itself no longer says whether anything is actually done — defer to the
// live InformationStatus (see MissingInformationService) instead. Before
// that point (draft/sent/opened/in_progress) the raw workflow status is
// still the most useful thing to show — see the spec's section 19.
export function effectiveRequestBadge(request: ComplianceRequest): EffectiveRequestBadge {
  if (request.status === 'draft' || request.status === 'completed') {
    return { labelKey: request.status, badgeClass: REQUEST_STATUS_BADGE_CLASSES[request.status] };
  }
  const info = request.information_status?.status;
  if (request.status === 'submitted' && info) {
    switch (info) {
      case 'conflict':
        return { labelKey: 'conflict', badgeClass: 'status-red' };
      case 'review_required':
        return { labelKey: 'review_required', badgeClass: 'status-red' };
      case 'missing_information':
        return { labelKey: 'missing_information', badgeClass: 'status-orange' };
      case 'complete':
        return { labelKey: 'completed', badgeClass: 'status-green' };
    }
  }
  return { labelKey: request.status, badgeClass: REQUEST_STATUS_BADGE_CLASSES[request.status] };
}
