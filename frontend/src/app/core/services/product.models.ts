import { ComplianceStatus, PackagingComponent } from './packaging-component.models';

export interface Product {
  id: string;
  company_id: string;
  supplier_id: string | null;
  name: string;
  sku: string | null;
  description: string | null;
  created_at: string;
  status: ComplianceStatus;
  packaging_component_count: number;
}

export interface ProductDetail extends Product {
  packaging_components: PackagingComponent[];
}

export interface CreateProductPayload {
  name: string;
  sku?: string | null;
  description?: string | null;
  supplier_id?: string | null;
}

export type UpdateProductPayload = Partial<CreateProductPayload>;
