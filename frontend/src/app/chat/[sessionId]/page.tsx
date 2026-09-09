"use client";

import { useParams } from "next/navigation";

import { ChatWorkspace } from "@/components/chat-workspace";

export default function ChatSessionPage() {
  const params = useParams<{ sessionId: string }>();
  const sessionId = typeof params.sessionId === "string" ? params.sessionId : "";
  return <ChatWorkspace sessionId={sessionId || undefined} />;
}
