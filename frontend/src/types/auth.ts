export interface UserResponse {
  id: string;
  email: string;
  role: string;
  departments: string[];
  is_active: boolean;
  created_at: string;
}

export interface RegisterRequest {
  email: string;
  password: string;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface ApiError {
  detail: string | { msg: string; type: string }[];
}
