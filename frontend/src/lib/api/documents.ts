import type { DocumentListResponse, DocumentResponse, DocumentStatusResponse } from "@/types/document";

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
