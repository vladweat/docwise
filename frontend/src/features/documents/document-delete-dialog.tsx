"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";

import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { buttonVariants } from "@/components/ui/button";
import { useI18n } from "@/i18n/locale-provider";
import { ApiRequestError, deleteDocument } from "@/lib/api";
import { cn } from "@/lib/utils";
import { useToastStore } from "@/stores/toast-store";
import type { DocumentResponse } from "@/types/document";

export function DocumentDeleteDialog({
  document,
  onClose,
}: {
  document: DocumentResponse | null;
  onClose: () => void;
}) {
  const { t } = useI18n();
  const queryClient = useQueryClient();
  const pushToast = useToastStore((state) => state.push);
  const mutation = useMutation({
    mutationFn: (id: string) => deleteDocument(id),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["documents"] });
      pushToast(t("documents.deletedToast"), "info");
      onClose();
    },
    onError: (err) => {
      const message =
        err instanceof ApiRequestError ? err.message : t("errors.deleteDocumentFailed");
      pushToast(message, "error");
    },
  });

  return (
    <AlertDialog
      open={document !== null}
      onOpenChange={(open) => {
        if (!open && !mutation.isPending) onClose();
      }}
    >
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>{t("documents.deleteTitle")}</AlertDialogTitle>
          <AlertDialogDescription>
            {t("documents.deleteBody", { title: document?.title ?? "" })}
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel disabled={mutation.isPending}>{t("common.cancel")}</AlertDialogCancel>
          <AlertDialogAction
            className={cn(buttonVariants({ variant: "destructive" }))}
            disabled={mutation.isPending || !document}
            onClick={(event) => {
              event.preventDefault();
              if (document) mutation.mutate(document.id);
            }}
          >
            {mutation.isPending ? t("common.deleting") : t("common.delete")}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
