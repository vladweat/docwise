import type {
  InviteCreateResponse,
  LoginRequest,
  MemberListResponse,
  RegisterRequest,
  UserResponse,
} from "@/types/auth";
import type { ChatSessionDetail, ChatSessionListResponse, ChatStreamEvent } from "@/types/chat";
import type { DocumentListResponse, DocumentResponse, DocumentStatusResponse } from "@/types/document";
import type {
  BillingSubscription,
  BillingUsage,
  ChangePlanResponse,
  DevSimulateAction,
  PlanName,
} from "@/types/billing";
import type { HealthResponse } from "@/types/health";
import type { DevSsoAssertion, SsoConnection, SsoUpsertRequest } from "@/types/sso";

import { clearLegacyAuth } from "./auth-storage";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8001";

export class ApiRequestError extends Error {
  constructor(
    message: string,
    public status: number,
  ) {
    super(message);
    this.name = "ApiRequestError";
  }
}

async function parseError(response: Response): Promise<string> {
  try {
    const body = await response.json();
    if (typeof body.detail === "string") return body.detail;
    if (Array.isArray(body.detail)) {
      return body.detail.map((item: { msg: string }) => item.msg).join(", ");
    }
  } catch {
    // ignore parse errors
  }
  return `API error: ${response.status}`;
}

export async function apiFetch<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const headers = new Headers(options.headers);
  const isFormData = options.body instanceof FormData;
  if (!headers.has("Content-Type") && options.body && !isFormData) {
    headers.set("Content-Type", "application/json");
  }
  headers.set("X-Requested-With", "Docwise");

  const response = await fetch(`${API_URL}${path}`, {
    ...options,
    headers,
    cache: "no-store",
    credentials: "include",
  });

  if (!response.ok) {
    const message = await parseError(response);
    if (response.status === 429) {
      const retry = response.headers.get("Retry-After");
      const suffix = retry ? `. Retry in ${retry}s` : "";
      throw new ApiRequestError(`${message}${suffix}`, response.status);
    }
    throw new ApiRequestError(message, response.status);
  }

  if (response.status === 204) return undefined as T;
  return response.json();
}

export async function fetchHealth(): Promise<HealthResponse> {
  const response = await fetch(`${API_URL}/ready`, {
    cache: "no-store",
    credentials: "include",
    headers: { "X-Requested-With": "Docwise" },
  });
  try {
    const body = (await response.json()) as HealthResponse;
    if (response.ok || response.status === 503) {
      return body;
    }
    throw new ApiRequestError(body.status || `API error: ${response.status}`, response.status);
  } catch (err) {
    if (err instanceof ApiRequestError) throw err;
    throw new ApiRequestError(`API error: ${response.status}`, response.status);
  }
}

export async function register(data: RegisterRequest): Promise<UserResponse> {
  return apiFetch<UserResponse>("/api/v1/auth/register", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function login(data: LoginRequest): Promise<UserResponse> {
  return apiFetch<UserResponse>("/api/v1/auth/login", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function fetchMe(): Promise<UserResponse> {
  return apiFetch<UserResponse>("/api/v1/auth/me");
}

export async function logout(): Promise<void> {
  clearLegacyAuth();
  try {
    await apiFetch<undefined>("/api/v1/auth/logout", { method: "POST" });
  } catch {
    // cookie is cleared server-side when possible
  }
}

export async function loginWithGoogle(
  idToken: string,
  extras: { organization_name?: string; invite_token?: string } = {},
): Promise<UserResponse> {
  return apiFetch<UserResponse>("/api/v1/auth/google", {
    method: "POST",
    body: JSON.stringify({
      id_token: idToken,
      organization_name: extras.organization_name,
      invite_token: extras.invite_token,
    }),
  });
}

export async function switchOrganization(organizationId: string): Promise<UserResponse> {
  return apiFetch<UserResponse>("/api/v1/auth/switch-organization", {
    method: "POST",
    body: JSON.stringify({ organization_id: organizationId }),
  });
}

export async function fetchOrganizationMembers(): Promise<MemberListResponse> {
  return apiFetch<MemberListResponse>("/api/v1/organizations/members");
}

export async function createOrganizationInvite(payload: {
  email: string;
  role: string;
  departments: string[];
}): Promise<InviteCreateResponse> {
  return apiFetch<InviteCreateResponse>("/api/v1/organizations/invites", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function fetchBillingSubscription(): Promise<BillingSubscription> {
  return apiFetch<BillingSubscription>("/api/v1/billing/subscription");
}

export async function fetchBillingUsage(): Promise<BillingUsage> {
  return apiFetch<BillingUsage>("/api/v1/billing/usage");
}

export async function changeBillingPlan(plan: PlanName): Promise<ChangePlanResponse> {
  return apiFetch<ChangePlanResponse>("/api/v1/billing/plan", {
    method: "POST",
    body: JSON.stringify({ plan }),
  });
}

export async function simulateDevBilling(
  action: DevSimulateAction,
  plan?: PlanName,
): Promise<BillingSubscription> {
  return apiFetch<BillingSubscription>("/api/v1/billing/dev/simulate", {
    method: "POST",
    body: JSON.stringify(plan ? { action, plan } : { action }),
  });
}

export async function fetchOrganizationSso(): Promise<SsoConnection> {
  return apiFetch<SsoConnection>("/api/v1/organizations/sso");
}

export async function upsertOrganizationSso(payload: SsoUpsertRequest): Promise<SsoConnection> {
  return apiFetch<SsoConnection>("/api/v1/organizations/sso", {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}

export async function loginWithSso(slug: string, assertion: DevSsoAssertion): Promise<UserResponse> {
  return apiFetch<UserResponse>(`/api/v1/auth/sso/${encodeURIComponent(slug)}/acs`, {
    method: "POST",
    body: JSON.stringify(assertion),
  });
}

export function ssoLoginUrl(slug: string): string {
  return `${API_URL}/api/v1/auth/sso/${encodeURIComponent(slug)}/login`;
}

export async function fetchChatSessions(
  limit = 20,
  offset = 0,
): Promise<ChatSessionListResponse> {
  return apiFetch<ChatSessionListResponse>(
    `/api/v1/chat/sessions?limit=${limit}&offset=${offset}`,
  );
}

export async function fetchChatSession(sessionId: string): Promise<ChatSessionDetail> {
  return apiFetch<ChatSessionDetail>(`/api/v1/chat/sessions/${sessionId}`);
}

export async function sendChatFeedback(
  messageId: string,
  rating: 1 | -1,
  comment?: string,
): Promise<void> {
  await apiFetch<undefined>("/api/v1/chat/feedback", {
    method: "POST",
    body: JSON.stringify({ message_id: messageId, rating, comment }),
  });
}

export async function streamChat(
  query: string,
  onEvent: (event: ChatStreamEvent) => void,
  options: { sessionId?: string | null; signal?: AbortSignal } = {},
): Promise<void> {
  const headers = new Headers({
    "Content-Type": "application/json",
    "X-Requested-With": "Docwise",
  });
  const response = await fetch(`${API_URL}/api/v1/chat/stream`, {
    method: "POST",
    headers,
    body: JSON.stringify({
      query,
      session_id: options.sessionId ?? null,
    }),
    cache: "no-store",
    credentials: "include",
    signal: options.signal,
  });

  if (!response.ok) {
    throw new ApiRequestError(await parseError(response), response.status);
  }
  if (!response.body) {
    throw new ApiRequestError("Empty chat stream", response.status);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  const handleBlock = (block: string) => {
    const line = block.split("\n").find((part) => part.startsWith("data: "));
    if (!line) return;
    const data = line.slice(6);
    if (data === "[DONE]") {
      onEvent({ type: "done" });
      return;
    }
    try {
      const parsed = JSON.parse(data) as ChatStreamEvent;
      onEvent(parsed);
    } catch {
      // ignore malformed SSE chunks
    }
  };

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const parts = buffer.split("\n\n");
    buffer = parts.pop() ?? "";
    for (const part of parts) handleBlock(part);
  }
  if (buffer.trim()) handleBlock(buffer);
}

export async function fetchDocuments(
  limit = 50,
  offset = 0,
): Promise<DocumentListResponse> {
  return apiFetch<DocumentListResponse>(`/api/v1/documents?limit=${limit}&offset=${offset}`);
}

export async function fetchDocumentStatus(documentId: string): Promise<DocumentStatusResponse> {
  return apiFetch<DocumentStatusResponse>(`/api/v1/documents/${documentId}/status`);
}

export async function uploadDocument(file: File, accessRoles: string[]): Promise<DocumentResponse> {
  const body = new FormData();
  body.append("file", file);
  for (const role of accessRoles) {
    body.append("access_roles", role);
  }
  return apiFetch<DocumentResponse>("/api/v1/documents/upload", { method: "POST", body });
}

export async function deleteDocument(documentId: string): Promise<void> {
  await apiFetch<undefined>(`/api/v1/documents/${documentId}`, { method: "DELETE" });
}

export async function fetchDocumentPdf(documentId: string): Promise<Blob> {
  const headers = new Headers({ "X-Requested-With": "Docwise" });
  const response = await fetch(`${API_URL}/api/v1/documents/${documentId}/raw`, {
    cache: "no-store",
    credentials: "include",
    headers,
  });
  if (!response.ok) {
    throw new ApiRequestError(await parseError(response), response.status);
  }
  return response.blob();
}

export { API_URL };
