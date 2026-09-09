export interface DocumentResponse {
  id: string;
  title: string;
  file_size_bytes: number;
  total_pages: number | null;
  access_roles: string[];
  status: string;
  created_at: string;
}

export interface DocumentListResponse {
  items: DocumentResponse[];
  total: number;
  limit: number;
  offset: number;
}
