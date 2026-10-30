import type { Metadata } from "next";
import { cookies, headers } from "next/headers";

import { HomePage } from "@/features/home/home-page";
import { demoLoginsAvailable } from "@/features/auth/demo-accounts";

export const metadata: Metadata = {
  title: "DOCwise",
  description:
    "Корпоративный поиск по PDF и DOCX с разграничением доступа, ответами со ссылками на источники и проверяемым retrieval.",
  openGraph: {
    title: "DOCwise",
    description:
      "Найдите ответ в корпоративных документах, учитывая права доступа, и сразу проверьте источник.",
    type: "website",
  },
};

export default async function Page() {
  const [cookieStore, requestHeaders] = await Promise.all([cookies(), headers()]);
  const host = requestHeaders.get("host")?.replace(/:\\d+$/, "") ?? null;
  const hasSessionCookie = cookieStore.has("dw_access") || cookieStore.has("dw_refresh");
  const demoAvailable = demoLoginsAvailable({
    flag: process.env.NEXT_PUBLIC_SHOW_DEMO_LOGINS,
    hostname: host,
  });

  return <HomePage hasSessionCookie={hasSessionCookie} demoAvailable={demoAvailable} />;
}
