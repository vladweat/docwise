import type { OrganizationDomain } from "@/types/domain";
import type { SsoConnection, SsoUpsertRequest } from "@/types/sso";

import { apiFetch } from "./client";

export async function fetchOrganizationSso(): Promise<SsoConnection> {
  return apiFetch<SsoConnection>("/organizations/sso");
}

export async function upsertOrganizationSso(payload: SsoUpsertRequest): Promise<SsoConnection> {
  return apiFetch<SsoConnection>("/organizations/sso", {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}

export async function fetchOrganizationDomain(): Promise<OrganizationDomain> {
  return apiFetch<OrganizationDomain>("/organizations/domain");
}

export async function upsertOrganizationDomain(hostname: string | null): Promise<OrganizationDomain> {
  return apiFetch<OrganizationDomain>("/organizations/domain", {
    method: "PUT",
    body: JSON.stringify({ hostname }),
  });
}

export async function verifyOrganizationDomain(token: string): Promise<OrganizationDomain> {
  return apiFetch<OrganizationDomain>("/organizations/domain/verify", {
    method: "POST",
    body: JSON.stringify({ token }),
  });
}
