export type ComplianceStatus = 'green' | 'orange' | 'red';

// Mirrors backend app/domain/enums.py PackagingType — kept as a plain
// VARCHAR + validated list on both ends rather than a native enum, since
// it's expected to grow while the product is being validated.
export const PACKAGING_TYPES = [
  'box',
  'bag',
  'label',
  'filler',
  'outer_envelope',
  'other'
] as const;

export type PackagingType = (typeof PACKAGING_TYPES)[number];

export interface PackagingComponent {
  id: string;
  product_id: string;
  name: string;
  packaging_type: string;
  material: string | null;
  weight_grams: number | null;
  recycled_content_percentage: number | null;
  manufacturer: string | null;
  packaging_reference: string | null;
  country_of_manufacture: string | null;
  notes: string | null;
  created_at: string;
  status: ComplianceStatus;
  missing_fields: string[];
}

export interface CreatePackagingComponentPayload {
  name: string;
  packaging_type: PackagingType;
  material?: string | null;
  weight_grams?: number | null;
  recycled_content_percentage?: number | null;
  manufacturer?: string | null;
  packaging_reference?: string | null;
  country_of_manufacture?: string | null;
  notes?: string | null;
}

export type UpdatePackagingComponentPayload = Partial<CreatePackagingComponentPayload>;
