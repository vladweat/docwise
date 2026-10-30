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
    const syncTitle = () => {
      const title = t(titleKeyForPath(pathname));
      if (document.title !== title) document.title = title;
    };

    syncTitle();
    const observer = new MutationObserver(syncTitle);
    observer.observe(document.head, { childList: true, subtree: true, characterData: true });
    return () => observer.disconnect();
  }, [pathname, t]);

  return null;
}
