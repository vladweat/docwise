import type { Metadata } from "next";

import { AuthPanel } from "@/features/auth/auth-panel";
import { GuestGate } from "@/features/auth/guest-gate";

export const metadata: Metadata = {
  title: "Вход — Docwise",
};

export default function LoginPage() {
  return (
    <GuestGate>
      <main className="w-full flex-1 overflow-y-auto px-4 py-8 sm:px-6 sm:py-10">
        <div className="mx-auto max-w-md">
          <AuthPanel />
        </div>
      </main>
    </GuestGate>
  );
}
