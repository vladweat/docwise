import type { MessageKey } from "@/i18n/messages";
import type { UserResponse } from "@/types/auth";

export const ACCESS_ROLE_OPTIONS = [
  { value: "all", label: "General" },
  { value: "hr", label: "HR" },
  { value: "finance", label: "Finance" },
  { value: "engineering", label: "Engineering" },
  { value: "admin", label: "Admin" },
  { value: "manager", label: "Manager" },
  { value: "employee", label: "Employee" },
] as const;

const ROLE_LABELS = new Map<string, string>(ACCESS_ROLE_OPTIONS.map((item) => [item.value, item.label]));

export function canManageKnowledgeBase(user: UserResponse | null): boolean {
  return user?.role === "admin" || user?.role === "manager";
}

export function canManageOrganization(user: UserResponse | null): boolean {
  return user?.role === "admin";
}

export function allowedRolesForUser(user: UserResponse): string[] {
  return Array.from(new Set([user.role, "all", ...(user.departments ?? [])]));
}

export function rolesOverlap(selected: string[], allowed: string[]): boolean {
  const allowedSet = new Set(allowed);
  return selected.some((role) => allowedSet.has(role));
}

export function formatAccessRole(role: string): string {
  return ROLE_LABELS.get(role) ?? role;
}

export function accessRoleMessageKey(role: string): MessageKey {
  if (ROLE_LABELS.has(role)) return `accessRoles.${role}` as MessageKey;
  return `accessRoles.${role}` as MessageKey;
}
