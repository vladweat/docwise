import type { Metadata } from "next";

import { DocumentsPage } from "@/features/documents/documents-page";

export const metadata: Metadata = {
  title: "Документы — Docwise",
};

export default function DocumentsRoute() {
  return <DocumentsPage />;
}
