import type { Metadata } from "next";

import { SettingsPage } from "@/features/settings/settings-page";

export const metadata: Metadata = {
  title: "Настройки — Docwise",
};

export default function SettingsRoute() {
  return <SettingsPage />;
}
