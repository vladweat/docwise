export type DocumentContentFormat = "pdf" | "docx";

export interface DocumentResponse {
  id: string;
  title: string;
  content_format?: DocumentContentFormat;
  file_size_bytes: number;
  total_pages: number | null;
  access_roles: string[];
  status: string;
  last_error: string | null;
  preview_snippet: string | null;
  created_at: string;
}

export interface DocumentListResponse {
  items: DocumentResponse[];
  total: number;
  limit: number;
  offset: number;
}

export interface DocumentStatusResponse {
  id: string;
  status: string;
  last_error: string | null;
  stage: "parse" | "chunk" | "embed" | null;
}

export const INGESTION_STEPS = ["parse", "chunk", "embed"] as const;
export type IngestionStep = (typeof INGESTION_STEPS)[number];
