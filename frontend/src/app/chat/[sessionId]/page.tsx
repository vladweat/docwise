import type { Metadata } from "next";

import { ChatWorkspace } from "@/features/chat/chat-workspace";

export const metadata: Metadata = {
  title: "Чат — Docwise",
};

export default async function ChatSessionPage({
  params,
}: {
  params: Promise<{ sessionId: string }>;
}) {
  const { sessionId } = await params;
  return <ChatWorkspace sessionId={sessionId} />;
}
