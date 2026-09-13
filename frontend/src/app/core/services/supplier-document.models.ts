// Mirrors backend app/domain/enums.py ExtractionStatus — a single value
// today (FASE 7 adds real states once a DocumentExtractionService exists).
export type ExtractionStatus = 'pending';

export interface SupplierDocument {
  id: string;
  filename: string;
  content_type: string;
  size_bytes: number;
  document_type: string;
  extraction_status: ExtractionStatus;
  uploaded_at: string;
}

// The public portal's own view is a strict subset — no document_type/
// extraction_status, which are internal/company-side concerns the
// supplier's browser has no reason to receive.
export interface PublicSupplierDocument {
  id: string;
  filename: string;
  content_type: string;
  size_bytes: number;
  uploaded_at: string;
}
