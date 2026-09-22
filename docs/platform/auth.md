# Auth and ACL

Related: [tenancy.md](tenancy.md), [retrieval.md](../pipeline/retrieval.md), [data-model.md](data-model.md).

Two layers: **organization** (session `org_id`) and **roles/departments** inside it. Roles do not isolate companies.

## Session

v1 — cookie session, cookies `dw_access` / `dw_refresh` (see [decisions.md](../engineering/decisions.md) ADR-007).

- Login / register / Google return user JSON and set cookies; no `access_token` in body. SSO ACS sets the same cookies, no token in JSON.
- Access JWT lives **15 minutes** (`ACCESS_TOKEN_EXPIRE_MINUTES`); refresh — 7 days. Client on `401` calls `POST /auth/refresh` once and retries.
- Access/refresh JWT: `sub`, current membership `org_id`, `exp`, `typ`; refresh also `jti`. **No `role` in token** — source of truth is `organization_memberships`, `GET /auth/me` reads membership from DB.
- Access token includes current membership `org_id`; `GET /auth/me` returns org + membership role. Org switch — `POST /auth/switch-organization` (own membership only), new cookies. On hostname bound to an org, switching to another org is forbidden ([ADR-015](../engineering/decisions.md)).
- `GET /health` and `GET /ready` without auth. Rest of `/api/v1/*` — `get_current_user` (cookie only).
- CSRF: with cross-site cookies (`SameSite=None`) mutations require allowlisted `Origin` or `X-Requested-With: Docwise`. Origin allowlist includes canonical frontend **and** verified hostname of current org.
- Manage KB (upload, delete, change `access_roles`): `require_kb_admin` — `admin` or `manager` of **current org**. Employee denial HTTP `403` with `detail: "Admin access required"` (same message as `require_admin`; role not revealed in body). Invites, billing, SSO, domain, inspect — `require_admin` only. Retrieval / list / status / raw **still** filter by `org_id` + document ACL, no admin override and no cross-org read.

Do not accept `access_roles`, `user_id`, `document_ids`, `org_id` / `organization_id` from the body as authority.

## User roles

Roles and departments live on `organization_memberships` (one person, different roles per org).

| Membership role | Meaning |
| --- | --- |
| `admin` | Manage KB, invites, billing, SSO and domain **for this org**; `POST /search/inspect` when `ENABLE_SEARCH_INSPECT` (retrieval still `org_id` + document ACL, no override) |
| `manager` | KB for this org: upload, delete, change ACL. Invites / billing / SSO / domain / inspect — `403` |
| `employee` | Base employee. KB write and inspect — `403` |

Plus `departments: string[]` (`engineering`, `hr`, `finance`, …) on the same membership.

Platform operator with access to customer corpora is not part of the product.

## SSO / SAML

Canonical: [ADR-014](../engineering/decisions.md). Plan gate — [billing.md](billing.md).

- Connector (`organization_sso_connections`) belongs to one org. Routes `/api/v1/auth/sso/{slug}/login` and `…/acs`: `{slug}` → that org, not assertion attribute.
- SP-initiated in v1; ACS accepts IdP-initiated if metadata matches. Success → `dw_access` / `dw_refresh` with connector `org_id`.
- JIT (if enabled on connector): create/find `users` by email and membership **only in that org**. Email is global: person already in Globex may join Acme; do not change Globex roles. Seats quota → `402`. Without JIT — existing membership or invite only.
- `organizations.sso_enforced`: password and Google cannot select this org as current; `POST /auth/switch-organization` without fresh SSO assertion (session flag / short redis key) → denied. Otherwise SSO is bypassed via another company.
- IdP group → `role` / `departments` mapping — JSON/table edited by org-admin. Do not write groups into `documents.access_roles`. Do not replace `org_id`.
- Email without verified equivalent — denied, same as Google.
- Compose: `SSO_PROVIDER=dev`, fixture assertion. Plan without SSO entitlement → `403` on connector upsert, not “wrong IdP”.

Google OIDC remains consumer login for plans without SSO. Not a SAML replacement.

## Building `allowed_roles` for search

```
allowed_roles = { membership.role } ∪ set(membership.departments) ∪ { "all" }
```

Filter (both conjuncts):

```sql
WHERE organization_id = :current_org
  AND access_roles && ARRAY['employee', 'hr', 'all']::text[]
```

Document with `access_roles = ["hr"]` is visible to a user **in this org** who has `hr` in `role` or `departments`. Document `["all"]` is visible to all members **of this organization**, not all logged-in SaaS users.

Document role literals (admin UI tags): `admin`, `manager`, `employee`, departments (`hr`, `finance`, …), plus `all` / UI label **General**.

## Surfaces with one rule

| Surface | Check |
| --- | --- |
| `GET /documents` | session `organization_id` **and** `access_roles` intersects `allowed_roles` |
| `GET /documents/{id}/raw` | same; else 404 (not 403 with filename; foreign org indistinguishable) |
| chat / search / inspect | `organization_id` **and** `&&` on `document_chunks`; do not rely on prompt |
| `POST /search/inspect` | cookie; flag off → `404`; not org-admin → `403`; then same filter as chat |
| KB: `PATCH /documents/{id}` | `require_kb_admin` (admin or manager of current org); writes document `access_roles` **and** all chunks; `org_id` unchanged |
| Billing / SSO / domain | `require_admin` of current org; foreign org indistinguishable (`404` on simulate and foreign slug) |
| LLM cache | key includes `org_id`, index generation, and canonical `allowed_roles` set |

ACL change on a file: update `documents` **and** all `document_chunks` rows for that file (or full re-upsert). Otherwise the index lies.
