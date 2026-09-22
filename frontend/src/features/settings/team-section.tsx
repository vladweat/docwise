"use client";

import { useState } from "react";

import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { InviteMemberModal } from "@/features/settings/invite-member-modal";
import { useI18n } from "@/i18n/locale-provider";
import { accessRoleMessageKey } from "@/lib/access-roles";
import { ApiRequestError } from "@/lib/api";
import { userFacingApiMessage } from "@/lib/quota";
import { formatDateTime } from "@/lib/format";
import type { MemberListResponse } from "@/types/auth";

const MEMBERSHIP_ROLE_KEY: Record<string, "settings.membershipRoleAdmin" | "settings.membershipRoleManager" | "settings.membershipRoleEmployee"> = {
  admin: "settings.membershipRoleAdmin",
  manager: "settings.membershipRoleManager",
  employee: "settings.membershipRoleEmployee",
};

export function TeamSection({
  members,
  loading,
  error,
  onRefresh,
}: {
  members?: MemberListResponse;
  loading: boolean;
  error: unknown;
  onRefresh: () => void;
}) {
  const { t } = useI18n();
  const [inviteOpen, setInviteOpen] = useState(false);

  return (
    <>
      <Card>
        <CardHeader className="flex flex-row items-start justify-between gap-3">
          <div>
            <CardTitle>{t("settings.teamTitle")}</CardTitle>
            <CardDescription>{t("settings.teamDescription")}</CardDescription>
          </div>
          <Button type="button" size="sm" variant="outline" onClick={() => setInviteOpen(true)}>
            {t("common.invite")}
          </Button>
        </CardHeader>
        <CardContent className="text-sm text-slate-300">
          {loading ? <Skeleton className="h-24 w-full" /> : null}
          {error ? (
            <Alert variant="destructive">
              {error instanceof ApiRequestError
                ? userFacingApiMessage(error.status, error.message)
                : t("errors.loadMembersFailed")}
            </Alert>
          ) : null}
          {members ? (
            <div className="overflow-x-auto rounded-lg border border-slate-800">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>{t("settings.teamColEmail")}</TableHead>
                    <TableHead>{t("settings.teamColRole")}</TableHead>
                    <TableHead>{t("settings.teamColDepartments")}</TableHead>
                    <TableHead className="whitespace-nowrap">{t("settings.teamColJoined")}</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {members.items.map((member) => (
                    <TableRow key={member.user_id}>
                      <TableCell className="font-medium text-slate-100">{member.email}</TableCell>
                      <TableCell>
                        {MEMBERSHIP_ROLE_KEY[member.role]
                          ? t(MEMBERSHIP_ROLE_KEY[member.role])
                          : member.role}
                      </TableCell>
                      <TableCell className="text-slate-400">
                        {member.departments.length > 0
                          ? member.departments.map((d) => t(accessRoleMessageKey(d))).join(", ")
                          : "—"}
                      </TableCell>
                      <TableCell className="whitespace-nowrap text-slate-400">
                        {formatDateTime(member.created_at)}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          ) : null}
        </CardContent>
      </Card>
      <InviteMemberModal
        open={inviteOpen}
        onClose={() => setInviteOpen(false)}
        onSuccess={onRefresh}
      />
    </>
  );
}
