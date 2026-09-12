export interface Supplier {
  id: string;
  company_id: string;
  name: string;
  email: string;
  country: string | null;
  created_at: string;
}

export interface CreateSupplierPayload {
  name: string;
  email: string;
  country?: string | null;
}

export interface UpdateSupplierPayload {
  name?: string;
  email?: string;
  country?: string | null;
}
