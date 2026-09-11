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
import type { OrganizationDomain } from "@/types/domain";
import type { DevSsoAssertion, SsoConnection, SsoUpsertRequest } from "@/types/sso";
import { consumeSseBuffer, parseSseBlock } from "@/lib/sse";

const CONFIGURED_API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8001";
const GENERIC_API_HOSTS = new Set(["localhost", "127.0.0.1"]);
export const API_V1 = "/api/v1";

/** Same hostname as the page on `{slug}.localhost` / verified CNAME so host-only cookies stick. */
export function apiUrl(hostname?: string): string {
  if (typeof window === "undefined" && hostname == null) return CONFIGURED_API_URL;
  const host = hostname ?? (typeof window === "undefined" ? "" : window.location.hostname);
  if (!host || GENERIC_API_HOSTS.has(host)) return CONFIGURED_API_URL;
  try {
    const url = new URL(CONFIGURED_API_URL);
    url.hostname = host;
    return url.origin;
  } catch {
    return CONFIGURED_API_URL;
  }
}

function v1Path(path: string): string {
  const suffix = path.startsWith("/") ? path : `/${path}`;
  return `${API_V1}${suffix}`;
}

function v1Url(path: string): string {
  return `${apiUrl()}${v1Path(path)}`;
}

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

const NO_REFRESH_PATHS = new Set([
  "/auth/login",
  "/auth/register",
  "/auth/google",
  "/auth/refresh",
  "/auth/logout",
]);

let refreshInFlight: Promise<boolean> | null = null;

export function shouldRefreshOn401(path: string): boolean {
  const suffix = path.startsWith("/") ? path : `/${path}`;
  if (NO_REFRESH_PATHS.has(suffix)) return false;
  if (suffix.startsWith("/auth/sso/")) return false;
  return true;
}

async function refreshSession(): Promise<boolean> {
  if (refreshInFlight) return refreshInFlight;
  refreshInFlight = (async () => {
    const response = await fetch(v1Url("/auth/refresh"), {
      method: "POST",
      cache: "no-store",
      credentials: "include",
      headers: { "X-Requested-With": "Docwise" },
    });
    return response.ok;
  })().finally(() => {
    refreshInFlight = null;
  });
  return refreshInFlight;
}

async function authorizedFetch(path: string, options: RequestInit = {}): Promise<Response> {
  const headers = new Headers(options.headers);
  const isFormData = options.body instanceof FormData;
  if (!headers.has("Content-Type") && options.body && !isFormData) {
    headers.set("Content-Type", "application/json");
  }
  headers.set("X-Requested-With", "Docwise");
  const init: RequestInit = {
    ...options,
    headers,
    cache: "no-store",
    credentials: "include",
  };
  let response = await fetch(v1Url(path), init);
  if (response.status === 401 && shouldRefreshOn401(path) && (await refreshSession())) {
    response = await fetch(v1Url(path), init);
  }
  return response;
}

export async function apiFetch<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const response = await authorizedFetch(path, options);

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
  const response = await fetch(`${apiUrl()}/ready`, {
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

export async function fetchBillingSubscription(): Promise<BillingSubscription> {
  return apiFetch<BillingSubscription>("/billing/subscription");
}

export async function fetchBillingUsage(): Promise<BillingUsage> {
  return apiFetch<BillingUsage>("/billing/usage");
}

export async function changeBillingPlan(plan: PlanName): Promise<ChangePlanResponse> {
  return apiFetch<ChangePlanResponse>("/billing/plan", {
    method: "POST",
    body: JSON.stringify({ plan }),
  });
}

export async function simulateDevBilling(
  action: DevSimulateAction,
  plan?: PlanName,
): Promise<BillingSubscription> {
  return apiFetch<BillingSubscription>("/billing/dev/simulate", {
    method: "POST",
    body: JSON.stringify(plan ? { action, plan } : { action }),
  });
}

export async function fetchOrganizationSso(): Promise<SsoConnection> {
  return apiFetch<SsoConnection>("/organizations/sso");
}

export async function upsertOrganizationSso(payload: SsoUpsertRequest): Promise<SsoConnection> {
  return apiFetch<SsoConnection>("/organizations/sso", {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}

export async function fetchOrganizationDomain(): Promise<OrganizationDomain> {
  return apiFetch<OrganizationDomain>("/organizations/domain");
}

export async function upsertOrganizationDomain(hostname: string | null): Promise<OrganizationDomain> {
  return apiFetch<OrganizationDomain>("/organizations/domain", {
    method: "PUT",
    body: JSON.stringify({ hostname }),
  });
}

export async function verifyOrganizationDomain(token: string): Promise<OrganizationDomain> {
  return apiFetch<OrganizationDomain>("/organizations/domain/verify", {
    method: "POST",
    body: JSON.stringify({ token }),
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

export async function fetchChatSessions(
  limit = 20,
  offset = 0,
): Promise<ChatSessionListResponse> {
  return apiFetch<ChatSessionListResponse>(
    `/chat/sessions?limit=${limit}&offset=${offset}`,
  );
}

export async function fetchChatSession(sessionId: string): Promise<ChatSessionDetail> {
  return apiFetch<ChatSessionDetail>(`/chat/sessions/${sessionId}`);
}

export async function deleteChatSession(sessionId: string): Promise<void> {
  await apiFetch<undefined>(`/chat/sessions/${sessionId}`, { method: "DELETE" });
}

export async function sendChatFeedback(
  messageId: string,
  rating: 1 | -1,
  comment?: string,
): Promise<void> {
  await apiFetch<undefined>("/chat/feedback", {
    method: "POST",
    body: JSON.stringify({ message_id: messageId, rating, comment }),
  });
}

export async function streamChat(
  query: string,
  onEvent: (event: ChatStreamEvent) => void,
  options: { sessionId?: string | null; signal?: AbortSignal } = {},
): Promise<void> {
  const response = await authorizedFetch("/chat/stream", {
    method: "POST",
    body: JSON.stringify({
      query,
      session_id: options.sessionId ?? null,
    }),
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

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    buffer = consumeSseBuffer(buffer, onEvent);
  }
  if (buffer.trim()) {
    const event = parseSseBlock(buffer);
    if (event) onEvent(event);
  }
}

export async function fetchDocuments(
  limit = 50,
  offset = 0,
): Promise<DocumentListResponse> {
  return apiFetch<DocumentListResponse>(`/documents?limit=${limit}&offset=${offset}`);
}

export async function fetchDocumentStatus(documentId: string): Promise<DocumentStatusResponse> {
  return apiFetch<DocumentStatusResponse>(`/documents/${documentId}/status`);
}

export async function uploadDocument(file: File, accessRoles: string[]): Promise<DocumentResponse> {
  const body = new FormData();
  body.append("file", file);
  for (const role of accessRoles) {
    body.append("access_roles", role);
  }
  return apiFetch<DocumentResponse>("/documents/upload", { method: "POST", body });
}

export async function deleteDocument(documentId: string): Promise<void> {
  await apiFetch<undefined>(`/documents/${documentId}`, { method: "DELETE" });
}

export async function fetchDocumentPdf(documentId: string): Promise<Blob> {
  const response = await authorizedFetch(`/documents/${documentId}/raw`);
  if (!response.ok) {
    throw new ApiRequestError(await parseError(response), response.status);
  }
  return response.blob();
}
