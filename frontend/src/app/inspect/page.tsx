import type { Metadata } from "next";

import { InspectPage } from "@/features/inspect/inspect-page";

export const metadata: Metadata = {
  title: "Inspect — Docwise",
};

export default function InspectRoute() {
  return <InspectPage />;
}
