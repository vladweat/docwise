import { tClient } from "@/i18n/client-translate";

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

export function v1Path(path: string): string {
  const suffix = path.startsWith("/") ? path : `/${path}`;
  return `${API_V1}${suffix}`;
}

export function v1Url(path: string): string {
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

export async function authorizedFetch(path: string, options: RequestInit = {}): Promise<Response> {
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

export async function apiFetch<T>(path: string, options: RequestInit = {}): Promise<T> {
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

export async function fetchDocumentRaw(documentId: string): Promise<Blob> {
  const response = await authorizedFetch(`/documents/${documentId}/raw`);
  if (!response.ok) {
    if (response.status === 404) {
      throw new ApiRequestError(tClient("errors.documentUnavailable"), 404);
    }
    throw new ApiRequestError(await parseError(response), response.status);
  }
  return response.blob();
}
