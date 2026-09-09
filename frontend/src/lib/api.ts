import type { LoginRequest, RegisterRequest, UserResponse } from "@/types/auth";
import type { HealthResponse } from "@/types/health";

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

export async function loginWithGoogle(idToken: string): Promise<UserResponse> {
  return apiFetch<UserResponse>("/api/v1/auth/google", {
    method: "POST",
    body: JSON.stringify({ id_token: idToken }),
  });
}

export { API_URL };
