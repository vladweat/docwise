import type { Metadata } from "next";

import { ChatWorkspace } from "@/features/chat/chat-workspace";

export const metadata: Metadata = {
  title: "DOCwise",
};

export default function ChatPage() {
  return <ChatWorkspace />;
}
