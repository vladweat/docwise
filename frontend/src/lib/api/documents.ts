import type {
  DocumentAccessOptions,
  DocumentListResponse,
  DocumentResponse,
  DocumentStatusResponse,
} from "@/types/document";

import { apiFetch } from "./client";

export async function fetchDocuments(
  limit = 50,
  offset = 0,
): Promise<DocumentListResponse> {
  return apiFetch<DocumentListResponse>(`/documents?limit=${limit}&offset=${offset}`);
}

export async function fetchDocumentStatus(documentId: string): Promise<DocumentStatusResponse> {
  return apiFetch<DocumentStatusResponse>(`/documents/${documentId}/status`);
}

export async function fetchDocumentAccessOptions(): Promise<DocumentAccessOptions> {
  return apiFetch<DocumentAccessOptions>("/documents/access-options");
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

export async function patchDocumentAccess(
  documentId: string,
  accessRoles: string[],
): Promise<DocumentResponse> {
  return apiFetch<DocumentResponse>(`/documents/${documentId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ access_roles: accessRoles }),
  });
}
