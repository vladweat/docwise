export interface SsoAttributeRule {
  group: string;
  role?: string | null;
  departments: string[];
}

export interface SsoAttributeMap {
  default_role: string;
  default_departments: string[];
  rules: SsoAttributeRule[];
}

export interface SsoConnection {
  configured: boolean;
  slug: string;
  protocol: string;
  idp_entity_id: string | null;
  idp_metadata: Record<string, unknown>;
  jit_enabled: boolean;
  attribute_map: SsoAttributeMap;
  sso_enforced: boolean;
  login_path: string;
  acs_path: string;
  provider: string;
}

export interface SsoUpsertRequest {
  protocol?: "saml" | "oidc";
  idp_entity_id?: string | null;
  idp_metadata?: Record<string, unknown>;
  jit_enabled: boolean;
  attribute_map: SsoAttributeMap;
  sso_enforced: boolean;
}

export interface DevSsoAssertion {
  email: string;
  email_verified: boolean;
  groups: string[];
}
