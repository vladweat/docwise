"use client";

import { type FormEvent, useEffect, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { useAuth } from "@/features/auth/auth-provider";
import { AccessRolesField } from "@/features/documents/access-roles-field";
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
import { allowedRolesForUser, rolesOverlap } from "@/lib/access-roles";
import { ApiRequestError, patchDocumentAccess } from "@/lib/api";
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
  const [roles, setRoles] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (document) {
      setRoles([...document.access_roles]);
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
    if (!document || roles.length === 0 || mutation.isPending) return;
    mutation.mutate();
  }

  const allowed = user ? allowedRolesForUser(user) : ["all"];
  const visibleAfterSave = rolesOverlap(roles, allowed);

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
            onChange={setRoles}
            showOverlapWarning={!visibleAfterSave && roles.length > 0}
          />
          {error ? <Alert variant="destructive">{error}</Alert> : null}
          <DialogFooter>
            <Button type="button" variant="ghost" onClick={onClose} disabled={mutation.isPending}>
              {t("common.cancel")}
            </Button>
            <Button type="submit" disabled={roles.length === 0 || mutation.isPending}>
              {mutation.isPending ? "…" : t("common.save")}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
