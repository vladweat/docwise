"use client";

import { type FormEvent, useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { useAuth } from "@/features/auth/auth-provider";
import { AccessRolesField } from "@/features/documents/access-roles-field";
import { AccessAudiencePreview } from "@/features/documents/access-audience-preview";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { useI18n } from "@/i18n/locale-provider";
import { canManageKnowledgeBase, normalizeAccessRoles } from "@/lib/access-roles";
import { ApiRequestError, fetchDocumentAccessOptions, patchDocumentAccess } from "@/lib/api";
import { userFacingApiMessage } from "@/lib/quota";
import { useToastStore } from "@/stores/toast-store";
import type { DocumentResponse } from "@/types/document";

export function DocumentAclDialog({
  document,
  onClose,
}: {
  document: DocumentResponse | null;
  onClose: () => void;
}) {
  const { user } = useAuth();
  const { t } = useI18n();
  const queryClient = useQueryClient();
  const pushToast = useToastStore((state) => state.push);
  const accessOptionsQuery = useQuery({
    queryKey: ["document-access-options", user?.organization_id],
    queryFn: fetchDocumentAccessOptions,
    enabled: Boolean(document) && canManageKnowledgeBase(user),
  });
  const [roles, setRoles] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (document) {
      setRoles(normalizeAccessRoles(document.access_roles));
      setError(null);
    }
  }, [document]);

  const mutation = useMutation({
    mutationFn: () => {
      if (!document) throw new Error("missing document");
      return patchDocumentAccess(document.id, roles);
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["documents"] });
      pushToast(t("documents.aclSavedToast"), "info");
      onClose();
    },
    onError: (err) => {
      const raw = err instanceof ApiRequestError ? err.message : t("errors.patchAclFailed");
      const message =
        err instanceof ApiRequestError ? userFacingApiMessage(err.status, err.message) : raw;
      setError(message);
    },
  });

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    if (
      !document ||
      roles.length === 0 ||
      accessOptionsQuery.isLoading ||
      accessOptionsQuery.isError ||
      mutation.isPending
    ) return;
    mutation.mutate();
  }

  return (
    <Dialog
      open={document !== null}
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
    >
      <DialogContent className="sm:max-w-lg" showCloseButton>
        <form onSubmit={onSubmit} className="grid gap-4">
          <DialogHeader>
            <DialogTitle>{t("documents.editAccessTitle")}</DialogTitle>
            <DialogDescription>
              {t("documents.editAccessDescription", { title: document?.title ?? "" })}
            </DialogDescription>
          </DialogHeader>
          <AccessRolesField
            roles={roles}
            roleOptions={accessOptionsQuery.data?.roles ?? []}
            departments={accessOptionsQuery.data?.departments ?? []}
            isLoading={accessOptionsQuery.isLoading}
            onChange={setRoles}
          />
          {accessOptionsQuery.isError ? (
            <Alert variant="destructive">
              {accessOptionsQuery.error instanceof ApiRequestError
                ? accessOptionsQuery.error.message
                : t("errors.loadAccessOptionsFailed")}
            </Alert>
          ) : null}
          <AccessAudiencePreview roles={roles} user={user} />
          {error ? <Alert variant="destructive">{error}</Alert> : null}
          <DialogFooter>
            <Button type="button" variant="ghost" onClick={onClose} disabled={mutation.isPending}>
              {t("common.cancel")}
            </Button>
            <Button
              type="submit"
              disabled={
                roles.length === 0 ||
                accessOptionsQuery.isLoading ||
                accessOptionsQuery.isError ||
                mutation.isPending
              }
            >
              {mutation.isPending ? "…" : t("common.save")}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
