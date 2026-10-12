# Multi-tenancy (shared B2B SaaS)

Canonical isolation between companies. Inside a company — [auth.md](auth.md) (roles and departments). Table model: [data-model.md](data-model.md). Decision: [ADR-012](../engineering/decisions.md).

Docwise is **shared B2B SaaS**: many organizations on one deploy (shared Postgres, MinIO, Redis, LLM). On-prem / private cloud — same code with one organization, not a separate product.

One deploy hosts many organizations; isolation — SQL `organization_id`.

## Two access layers

Roles **do not** replace organization. `hr` and `all` are tags inside a company, not customer identifiers.

```
1. Tenant (outer wall):  org_id = current_org     — foreign company invisible
2. RBAC (inner wall): access_roles && allowed_roles  — intern cannot read HR
```

On every list / status / raw / dense / sparse / inspect / chat:

```sql
WHERE org_id = :current_org
  AND access_roles && ARRAY['employee', 'hr', 'all']::text[]
```

`current_org` from session (cookie/JWT), **not** from request body. Do not filter tenant “later in prompt”. Do not use `access_roles = ['acme']` instead of `org_id`.

Both layers are mandatory on every list / search / chat.

## Organization and membership

| Entity | Meaning |
| --- | --- |
| `users` | Global person (email unique). Password / Google. No `role` / `departments` |
| `organizations` | Customer company: name, slug, status |
| `organization_memberships` | user↔org link: `role` (`admin` \| `manager` \| `employee`) and `departments[]` |

One user may belong to several orgs (contractor, holding). Role **per org**: admin at Acme and employee at Globex is normal.

`require_admin` — **admin of current organization**, not platform operator. A platform operator with access to foreign corpora is not part of the product.

## Plans, hostname, SSO

Quota canonical: [billing.md](billing.md). SSO: [auth.md](auth.md). ADR-013–015.

- Plan and quotas — fields of **this** org. Plan change in dev-simulate or Stripe does not grant another org’s corpus.
- If `Host` is bound to an org (slug subdomain or verified custom domain), it must match session `org_id`. Hostname **pins** tenant, does not replace `WHERE organization_id = :current_org`.
- Session cookies — host-only, no `Domain` on platform parent suffix (otherwise Acme cookie leaks to Globex host).
- SSO connector belongs to one org. Assertion does not choose tenant.
- `all` still only members of this org, including after SSO JIT.

On Acme custom/slug host, `switch-organization` to Globex is forbidden (need Globex host).

## Session

Session cookies, JWT claims, org switch, and CSRF: [auth.md](auth.md). Access token carries `sub` and current membership `org_id`; role comes from `organization_memberships`, not the JWT. Field `organization_id` / `org_id` in chat/search/upload is ignored as authority.

## Registration and invites

Self-serve:

1. `POST /auth/register` creates `users` + `organizations` + membership `admin`. Body: email, password, `organization_name`.
2. Org-admin invites: `POST /api/v1/organizations/invites` `{ email, role, departments }`.
3. Existing user with that email gets membership; new user registers via invite and joins org, **does not** create second company from same invite.
4. Open register without org name does not create “employee of global instance”.

First user on empty DB is no longer “admin of whole platform”: admin **of own** organization.

## Surfaces with one rule

| Surface | Check |
| --- | --- |
| `GET /documents`, `/raw`, `/status` | `org_id` + `access_roles` intersection |
| chat / search / inspect | same on `document_chunks` (`org_id` **and** ACL); chunks copy document `org_id` |
| KB write (upload, delete, PATCH ACL, invites) | membership `admin`/`manager` **current** org; row still session `org_id`; seats/pages quota per plan |
| chat sessions, audit | `org_id`; Acme history not mixed into Globex; period tokens — this org quota |
| LLM cache | key includes `org_id`, index generation **and** canonical `allowed_roles` |
| `file_hash` | unique `(org_id, file_hash)`, not global |
| MinIO | key with org prefix, no public URL |
| billing / usage | current org only; `dev/simulate` foreign org → `404` |
| SSO ACS | org from connector `{slug}`; JIT only into it |
| custom domain | verified hostname → one org; mismatch with session → deny |

Auth-specific write gates (`require_kb_admin` / `require_admin`) and inspect flag: [auth.md](auth.md). Foreign tenant: `404` as for file outside ACL. Do not confirm another company has a document / matching SHA-256.

## Forbidden

- Two companies in one DB without `org_id` on documents **and** chunks.
- Treat `all` as “every logged-in SaaS user”.
- LLM cache keyed only by roles (Acme employee gets Globex-warmed answer).
- Client `org_id` / `organization_id` as authority.
- Org-admin override of inner ACL (admin without `hr` still does not see HR file).
- Hint in `409` that same PDF exists at *another* organization.
- Treat plan, Stripe customer id, or SAML `org` attribute as source of `organization_id`.

## Postgres RLS (corpus)

RLS only on **`documents`** and **`document_chunks`**: hybrid retrieval surface; missed `organization_id` in one SQL path would expose foreign indexed text. Policy `docwise_tenant_visible(organization_id)` via GUC `app.organization_id`. API/SSE chat set org because same query reads chunks. Celery: one lookup by `document_id` with brief bypass, then GUC = `document.organization_id` (`fetch_document_for_ingestion` in worker).

Chat (`chat_sessions` / `chat_messages`) and `rag_audit_logs` **without** RLS: code already hard-filters `organization_id` (+ `user_id` for sessions). RLS there adds complexity without gain (no `organization_id` on messages).

**Does not replace** `WHERE organization_id` and `access_roles` in application (inner ACL still only in SQL/services).

**Runtime prerequisite:** PostgreSQL superuser всегда обходит RLS, включая `FORCE ROW LEVEL
SECURITY`. `app.core.rls` выполняет `SET LOCAL ROLE` только если задана
`DOCWISE_RLS_SESSION_ROLE`. Текущий `docker-compose.yml` эту переменную и отдельную
least-privilege role не настраивает, поэтому в Compose изоляция фактически опирается на
application filters. Tests создают отдельную role в `backend/tests/conftest.py`; production
deployment обязан воспроизвести и проверить эту настройку отдельно.

## Not in product scope

Platform operator console, SCIM. Live payment processing (live Stripe / YooKassa) is optional via the Stripe adapter; Compose and portfolio acceptance use `BILLING_PROVIDER=dev` ([billing.md](billing.md)).
