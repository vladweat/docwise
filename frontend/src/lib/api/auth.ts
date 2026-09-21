import type {
  InviteCreateResponse,
  LoginRequest,
  MemberListResponse,
  RegisterRequest,
  UserResponse,
} from "@/types/auth";
import type { DevSsoAssertion } from "@/types/sso";

import { apiFetch, v1Url } from "./client";

export async function register(data: RegisterRequest): Promise<UserResponse> {
  return apiFetch<UserResponse>("/auth/register", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function login(data: LoginRequest): Promise<UserResponse> {
  return apiFetch<UserResponse>("/auth/login", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function fetchMe(): Promise<UserResponse> {
  return apiFetch<UserResponse>("/auth/me");
}

export async function logout(): Promise<void> {
  try {
    await apiFetch<undefined>("/auth/logout", { method: "POST" });
  } catch {
    // cookie is cleared server-side when possible
  }
}

export async function loginWithGoogle(
  idToken: string,
  extras: { organization_name?: string; invite_token?: string } = {},
): Promise<UserResponse> {
  return apiFetch<UserResponse>("/auth/google", {
    method: "POST",
    body: JSON.stringify({
      id_token: idToken,
      organization_name: extras.organization_name,
      invite_token: extras.invite_token,
    }),
  });
}

export async function switchOrganization(organizationId: string): Promise<UserResponse> {
  return apiFetch<UserResponse>("/auth/switch-organization", {
    method: "POST",
    body: JSON.stringify({ organization_id: organizationId }),
  });
}

export async function fetchOrganizationMembers(): Promise<MemberListResponse> {
  return apiFetch<MemberListResponse>("/organizations/members");
}

export async function createOrganizationInvite(payload: {
  email: string;
  role: string;
  departments: string[];
}): Promise<InviteCreateResponse> {
  return apiFetch<InviteCreateResponse>("/organizations/invites", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function loginWithSso(slug: string, assertion: DevSsoAssertion): Promise<UserResponse> {
  return apiFetch<UserResponse>(`/auth/sso/${encodeURIComponent(slug)}/acs`, {
    method: "POST",
    body: JSON.stringify(assertion),
  });
}

export function ssoLoginUrl(slug: string): string {
  return v1Url(`/auth/sso/${encodeURIComponent(slug)}/login`);
}
