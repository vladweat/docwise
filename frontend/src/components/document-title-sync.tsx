"use client";

import { useEffect } from "react";
import { usePathname } from "next/navigation";

import { useI18n } from "@/i18n/locale-provider";
import type { MessageKey } from "@/i18n/messages";

const PATH_TITLE: Record<string, MessageKey> = {
  "/": "meta.titleChat",
  "/login": "meta.titleLogin",
  "/documents": "meta.titleDocuments",
  "/settings": "meta.titleSettings",
  "/inspect": "meta.titleInspect",
};

function titleKeyForPath(pathname: string): MessageKey {
  if (pathname.startsWith("/chat")) return "meta.titleChat";
  return PATH_TITLE[pathname] ?? "meta.titleChat";
}

export function DocumentTitleSync() {
  const pathname = usePathname();
  const { t } = useI18n();

  useEffect(() => {
    document.title = t(titleKeyForPath(pathname));
  }, [pathname, t]);

  return null;
}
