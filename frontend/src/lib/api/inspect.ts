import type { SearchInspectResponse } from "@/types/search";

import { apiFetch } from "./client";

export async function inspectSearch(query: string, limit = 15): Promise<SearchInspectResponse> {
  return apiFetch<SearchInspectResponse>("/search/inspect", {
    method: "POST",
    body: JSON.stringify({ query, limit }),
  });
}
