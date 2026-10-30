import type { Metadata } from "next";

import { DocumentsPage } from "@/features/documents/documents-page";

export const metadata: Metadata = {
  title: "DOCwise",
};

export default function DocumentsRoute() {
  return <DocumentsPage />;
}
