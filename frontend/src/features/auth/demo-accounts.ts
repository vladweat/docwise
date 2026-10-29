export const DEMO_EMPLOYEE_EMAIL = "employee@docwise.example.com";
export const DEMO_HR_EMAIL = "hr@docwise.example.com";
export const DEMO_ADMIN_EMAIL = "admin@docwise.example.com";
export const DEMO_EMPLOYEE_PASSWORD = "demo-employee-pass";
export const DEMO_HR_PASSWORD = "demo-hr-pass";
export const DEMO_ADMIN_PASSWORD = "demo-admin-pass";

export type DemoPersona = "employee" | "hr" | "admin";
export type LoginVariant = "standard" | "demo";

export function demoLoginsAvailable({
  flag,
  hostname,
}: {
  flag: string | undefined;
  hostname: string | null;
}): boolean {
  if (flag === "true") return true;
  if (flag === "false") return false;
  return hostname === "localhost" || hostname === "127.0.0.1";
}

export function initialLoginVariant({
  publicDemo,
  demoLogins,
  requestedMode,
}: {
  publicDemo: boolean;
  demoLogins: boolean;
  requestedMode: string | null;
}): LoginVariant {
  if (demoLogins && requestedMode === "standard") return "standard";
  if (publicDemo || (demoLogins && requestedMode === "demo")) return "demo";
  return "standard";
}

export const DEMO_ACCOUNTS: {
  persona: DemoPersona;
  label: string;
  shortLabel: string;
  hint: string;
  email: string;
  password: string;
}[] = [
  {
    persona: "employee",
    label: "Войти как сотрудник",
    shortLabel: "Сотрудник",
    hint: "без HR и Finance",
    email: DEMO_EMPLOYEE_EMAIL,
    password: DEMO_EMPLOYEE_PASSWORD,
  },
  {
    persona: "hr",
    label: "Войти как HR",
    shortLabel: "HR",
    hint: "плюс compensation",
    email: DEMO_HR_EMAIL,
    password: DEMO_HR_PASSWORD,
  },
  {
    persona: "admin",
    label: "Войти как admin",
    shortLabel: "Admin",
    hint: "KB и inspect",
    email: DEMO_ADMIN_EMAIL,
    password: DEMO_ADMIN_PASSWORD,
  },
];

export function showDemoLogins(): boolean {
  const hostname = typeof window === "undefined" ? null : window.location.hostname;
  return demoLoginsAvailable({ flag: process.env.NEXT_PUBLIC_SHOW_DEMO_LOGINS, hostname });
}

/** Public demo VPS: demo buttons + no self-serve registration in the login UI. */
export function publicDemoProfile(): boolean {
  return process.env.NEXT_PUBLIC_SHOW_DEMO_LOGINS === "true";
}
