export const DEMO_EMPLOYEE_EMAIL = "employee@docwise.example.com";
export const DEMO_HR_EMAIL = "hr@docwise.example.com";
export const DEMO_ADMIN_EMAIL = "admin@docwise.example.com";
export const DEMO_EMPLOYEE_PASSWORD = "demo-employee-pass";
export const DEMO_HR_PASSWORD = "demo-hr-pass";
export const DEMO_ADMIN_PASSWORD = "demo-admin-pass";

export type DemoPersona = "employee" | "hr" | "admin";

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
  const flag = process.env.NEXT_PUBLIC_SHOW_DEMO_LOGINS;
  if (flag === "true") return true;
  if (flag === "false") return false;
  if (typeof window === "undefined") return false;
  return window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1";
}
