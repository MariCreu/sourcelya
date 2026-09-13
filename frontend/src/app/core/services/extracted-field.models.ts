// Mirrors backend app/domain/enums.py ConfidenceLevel/FieldReviewStatus —
// small closed categories, not a raw invented percentage. See
// app/integrations/extraction/claude_extraction.py for how a level is
// actually derived (a deterministic ceiling, never the model's raw claim).
export type ConfidenceLevel = 'high' | 'medium' | 'low';
export type FieldReviewStatus = 'pending' | 'accepted' | 'rejected';

// Mirrors app/domain/enums.py ExtractableFieldName — the only fields FASE 5
// ever proposes values for.
export type ExtractableFieldName =
  | 'packaging_type'
  | 'material'
  | 'weight_grams'
  | 'recycled_content_percentage'
  | 'packaging_reference';

export interface ExtractedField {
  id: string;
  document_id: string;
  packaging_component_id: string | null;
  field_name: ExtractableFieldName;
  extracted_value: string;
  confidence: ConfidenceLevel;
  source_page: number | null;
  source_quote: string | null;
  quote_verified: boolean;
  review_status: FieldReviewStatus;
  created_at: string;
}

export type ConflictResolution = 'use_extracted' | 'keep_current';

export interface AcceptExtractedFieldPayload {
  packaging_component_id?: string | null;
  conflict_resolution?: ConflictResolution | null;
}

export interface ExtractedFieldConflict {
  detail: 'POSSIBLE CONFLICT';
  field_name: string;
  current_value: string;
  extracted_value: string;
}
