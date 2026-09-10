export interface OrganizationSummary {
  id: string;
  name: string;
  role: string;
  departments: string[];
}

export interface UserResponse {
  id: string;
  email: string;
  role: string;
  departments: string[];
  is_active: boolean;
  created_at: string;
  organization_id: string;
  organization_name: string;
  organizations: OrganizationSummary[];
}

export interface RegisterRequest {
  email: string;
  password: string;
  organization_name?: string;
  invite_token?: string;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface InviteCreateResponse {
  email: string;
  role: string;
  departments: string[];
  status: "added" | "invited" | string;
  invite_token: string | null;
}

export interface MemberResponse {
  user_id: string;
  email: string;
  role: string;
  departments: string[];
  created_at: string;
}

export interface MemberListResponse {
  items: MemberResponse[];
  total: number;
}

export interface ApiError {
  detail: string | { msg: string; type: string }[];
}
