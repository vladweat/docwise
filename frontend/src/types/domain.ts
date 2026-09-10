export interface OrganizationDomain {
  slug: string;
  platform_hostnames: string[];
  custom_hostname: string | null;
  custom_verified: boolean;
  verified_at: string | null;
  verification_token: string | null;
  entitlement: boolean;
}
