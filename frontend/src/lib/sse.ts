import type { ChatStreamEvent } from "@/types/chat";

export function parseSseBlock(block: string): ChatStreamEvent | null {
  const line = block.split("\n").find((part) => part.startsWith("data: "));
  if (!line) return null;
  const data = line.slice(6);
  if (data === "[DONE]") {
    return { type: "done" };
  }
  try {
    return JSON.parse(data) as ChatStreamEvent;
  } catch {
    return null;
  }
}

export function consumeSseBuffer(
  buffer: string,
  onEvent: (event: ChatStreamEvent) => void,
): string {
  const parts = buffer.split("\n\n");
  const rest = parts.pop() ?? "";
  for (const part of parts) {
    const event = parseSseBlock(part);
    if (event) onEvent(event);
  }
  return rest;
}
