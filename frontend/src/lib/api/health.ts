import type { HealthResponse } from "@/types/health";

import { ApiRequestError, apiUrl } from "./client";

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
