import type { Metadata } from "next";

import { ChatWorkspace } from "@/features/chat/chat-workspace";

export const metadata: Metadata = {
  title: "Чат — Docwise",
};

export default function HomePage() {
  return <ChatWorkspace />;
}
