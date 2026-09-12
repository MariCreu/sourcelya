export interface Company {
  id: string;
  name: string;
  country: string;
  owner_user_id: string;
  created_at: string;
}

export interface AppUser {
  id: string;
  email: string;
  name: string | null;
  company_id: string | null;
  created_at: string;
}

export interface CurrentUser {
  user: AppUser;
  company: Company | null;
}

export interface CreateCompanyPayload {
  name: string;
  country: string;
}
