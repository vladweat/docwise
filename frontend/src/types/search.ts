export interface InspectHit {
  chunk_id: string;
  document_id: string;
  page: number;
  score: number;
  snippet: string;
}

export interface SearchInspectResponse {
  dense: InspectHit[];
  sparse: InspectHit[];
  rrf: InspectHit[];
  reranked: InspectHit[];
}

export const INSPECT_STAGES = ["dense", "sparse", "rrf", "reranked"] as const;

export type InspectStage = (typeof INSPECT_STAGES)[number];
