import type { MessageKey } from "@/i18n/messages";
import type { UserResponse } from "@/types/auth";

export const ACCESS_ROLE_OPTIONS = [
  { value: "admin", label: "Admin" },
  { value: "manager", label: "Manager" },
  { value: "employee", label: "Employee" },
] as const;

export const ACCESS_DEPARTMENT_OPTIONS = [
  { value: "hr" },
  { value: "finance" },
  { value: "engineering" },
  { value: "legal" },
  { value: "security" },
] as const;

const ROLE_LABELS = new Map<string, string>([
  ...ACCESS_ROLE_OPTIONS.map((item) => [item.value, item.label] as const),
  ["all", "General"],
  ["hr", "HR"],
  ["finance", "Finance"],
  ["engineering", "Engineering"],
]);
const ACCESS_ROLE_MESSAGE_KEYS: Record<string, MessageKey> = {
  all: "accessRoles.all",
  hr: "accessRoles.hr",
  finance: "accessRoles.finance",
  engineering: "accessRoles.engineering",
  legal: "accessRoles.legal",
  security: "accessRoles.security",
  admin: "accessRoles.admin",
  manager: "accessRoles.manager",
  employee: "accessRoles.employee",
};

export function toggleAccessRole(current: string[], value: string, checked: boolean): string[] {
  if (!checked) return current.filter((role) => role !== value);
  if (value === "all") return ["all"];
  return Array.from(new Set([...current.filter((role) => role !== "all"), value]));
}

export function normalizeAccessRoles(roles: string[]): string[] {
  const unique = Array.from(new Set(roles));
  return unique.includes("all") ? ["all"] : unique;
}

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

export function accessRoleMessageKey(role: string): MessageKey | undefined {
  return ACCESS_ROLE_MESSAGE_KEYS[role];
}

export function humanizeAccessTag(role: string): string {
  return role.replace(/[-_]/g, " ").replace(/\b\w/g, (character) => character.toUpperCase());
}
