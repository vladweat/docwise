import { Suspense } from "react";

import { AuthPanel } from "@/components/auth-panel";
import { GuestGate } from "@/components/guest-gate";

export default function LoginPage() {
  return (
    <GuestGate>
      <main className="w-full flex-1 overflow-y-auto px-4 py-8 sm:px-6 sm:py-10">
        <div className="mx-auto max-w-md">
          <Suspense fallback={<p className="text-sm text-slate-400">Загрузка…</p>}>
            <AuthPanel />
          </Suspense>
        </div>
      </main>
    </GuestGate>
  );
}
