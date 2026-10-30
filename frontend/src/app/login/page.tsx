import type { Metadata } from "next";

import { AuthPanel } from "@/features/auth/auth-panel";
import { GuestGate } from "@/features/auth/guest-gate";

export const metadata: Metadata = {
  title: "DOCwise",
};

export default function LoginPage() {
  return (
    <GuestGate>
      <main className="w-full flex-1 overflow-y-auto px-4 py-10 sm:px-6 sm:py-14">
        <div className="mx-auto max-w-sm">
          <AuthPanel />
        </div>
      </main>
    </GuestGate>
  );
}
