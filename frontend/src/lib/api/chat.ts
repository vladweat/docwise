import type { ChatSessionDetail, ChatSessionListResponse, ChatStreamEvent } from "@/types/chat";
import { consumeSseBuffer, parseSseBlock } from "@/lib/sse";

import { ApiRequestError, apiFetch, authorizedFetch, parseApiError } from "./client";

export async function fetchChatSessions(
  limit = 20,
  offset = 0,
): Promise<ChatSessionListResponse> {
  return apiFetch<ChatSessionListResponse>(
    `/chat/sessions?limit=${limit}&offset=${offset}`,
  );
}

export async function fetchChatSession(sessionId: string): Promise<ChatSessionDetail> {
  return apiFetch<ChatSessionDetail>(`/chat/sessions/${sessionId}`);
}

export async function deleteChatSession(sessionId: string): Promise<void> {
  await apiFetch<undefined>(`/chat/sessions/${sessionId}`, { method: "DELETE" });
}

export async function sendChatFeedback(
  messageId: string,
  rating: 1 | -1,
  comment?: string,
): Promise<void> {
  await apiFetch<undefined>("/chat/feedback", {
    method: "POST",
    body: JSON.stringify({ message_id: messageId, rating, comment }),
  });
}

export async function streamChat(
  query: string,
  onEvent: (event: ChatStreamEvent) => void,
  options: { sessionId?: string | null; signal?: AbortSignal } = {},
): Promise<void> {
  const response = await authorizedFetch("/chat/stream", {
    method: "POST",
    body: JSON.stringify({
      query,
      session_id: options.sessionId ?? null,
    }),
    signal: options.signal,
  });

  if (!response.ok) {
    throw new ApiRequestError(await parseApiError(response), response.status);
  }
  if (!response.body) {
    throw new ApiRequestError("Empty chat stream", response.status);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let completed = false;
  let failed = false;

  const dispatch = (event: ChatStreamEvent) => {
    if (event.type === "done") completed = true;
    if (event.type === "error") failed = true;
    onEvent(event);
  };

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    buffer = consumeSseBuffer(buffer, dispatch);
  }
  if (buffer.trim()) {
    const event = parseSseBlock(buffer);
    if (event) dispatch(event);
  }
  if (!completed && !failed) {
    throw new ApiRequestError("Chat stream ended before completion", response.status);
  }
}
