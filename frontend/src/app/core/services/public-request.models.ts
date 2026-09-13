import { RequestLanguage, RequestStatus } from './compliance-request.models';
import { PublicSupplierDocument } from './supplier-document.models';

export interface PublicPackagingComponent {
  id: string;
  name: string;
  packaging_type: string;
  material: string | null;
  weight_grams: number | null;
  recycled_content_percentage: number | null;
  packaging_reference: string | null;
  notes: string | null;
}

export interface PublicProduct {
  id: string;
  name: string;
  sku: string | null;
  packaging_components: PublicPackagingComponent[];
}

export interface PublicMissingFieldRef {
  packaging_component_id: string;
  field_name: string;
}

export interface PublicComplianceRequest {
  // Deliberately no company_id/supplier_id: the public API never sends
  // them (see backend PublicComplianceRequestRead) so a supplier's browser
  // never even receives the internal ids, not just doesn't display them.
  status: RequestStatus;
  language: RequestLanguage;
  company_name: string;
  supplier_name: string;
  submitted_at: string | null;
  products: PublicProduct[];
  documents: PublicSupplierDocument[];
  // FASE 6: non-empty once the supplier has submitted before and
  // something is still outstanding — drives the "ALMOST THERE" scoped
  // view (see PublicRequestComponent).
  missing_fields: PublicMissingFieldRef[];
}

export interface PublicPackagingComponentUpdate {
  id: string;
  material?: string | null;
  weight_grams?: number | null;
  recycled_content_percentage?: number | null;
  packaging_reference?: string | null;
  notes?: string | null;
}

export interface SavePublicRequestPayload {
  components: PublicPackagingComponentUpdate[];
}
