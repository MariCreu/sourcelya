// Mirrors backend app/domain/enums.py ExtractionStatus — the FASE 5 state
// machine advanced only by ExtractionService (see that module's docstring).
export type ExtractionStatus = 'pending' | 'processing' | 'completed' | 'failed' | 'review_required';

// Mirrors backend app/domain/enums.py DocumentType.
export type DocumentType =
  | 'packaging_specification'
  | 'technical_datasheet'
  | 'certificate'
  | 'declaration'
  | 'invoice_commercial'
  | 'other';

export interface SupplierDocument {
  id: string;
  filename: string;
  content_type: string;
  size_bytes: number;
  document_type: DocumentType;
  extraction_status: ExtractionStatus;
  processing_error: string | null;
  extracted_field_count: number;
  pending_review_count: number;
  uploaded_at: string;
}

// The public portal's own view is a strict subset — no document_type/
// extraction_status/extraction results, which are internal/company-side
// concerns the supplier's browser has no reason to receive.
export interface PublicSupplierDocument {
  id: string;
  filename: string;
  content_type: string;
  size_bytes: number;
  uploaded_at: string;
}
