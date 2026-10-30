import type { Metadata } from "next";

import { InspectPage } from "@/features/inspect/inspect-page";

export const metadata: Metadata = {
  title: "DOCwise",
};

export default function InspectRoute() {
  return <InspectPage />;
}
