export interface Citation {
  doc_id: string;
  doc_title: string;
  page: number;
  snippet: string;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  sources: Citation[];
  created_at: string;
}

export interface ChatSessionSummary {
  id: string;
  title: string | null;
  created_at: string;
  updated_at: string;
}

export interface ChatSessionListResponse {
  items: ChatSessionSummary[];
  total: number;
  limit: number;
  offset: number;
}

export interface ChatSessionDetail extends ChatSessionSummary {
  messages: ChatMessage[];
}

export type ChatStreamEvent =
  | { type: "token"; content: string }
  | { type: "citations"; citations: Citation[] }
  | {
      type: "meta";
      cached: boolean;
      tokens_used: number | null;
      cost_usd: number | null;
      session_id?: string | null;
      message_id?: string | null;
    }
  | { type: "error"; content: string }
  | { type: "done" };
