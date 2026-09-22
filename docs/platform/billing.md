# Plans, quotas, and billing

Canonical commercial envelope after shared tenancy ([tenancy.md](tenancy.md)). Decision: [ADR-013](../engineering/decisions.md). SSO: [auth.md](auth.md).

Plan, quotas, and `sso` / `custom_domain` flags live in **Postgres on the organization**. Payment provider only writes these fields. Retrieval, upload, and ACL **do not** call Stripe and do not weaken `organization_id` + `access_roles`.

## Quotas ≠ rate limit

| Mechanism | Purpose | Code |
| --- | --- | --- |
| Rate limit | anti-abuse: IP / `user.id` per minute | `429` |
| Organization quota | commercial limit per period | `402` |
| Plan entitlement | feature not in plan (SSO, custom domain) | `403` |

Do not use `404` for **own** quota. Foreign org still not confirmed (`404` as for file outside ACL).

## Plans

Literals: `starter` \| `team` \| `enterprise`. Numbers — env config (below — Compose guideline). New org after register — `starter`.

| | Starter | Team | Enterprise |
| --- | --- | --- | --- |
| Seats (`organization_memberships`) | 3 | 15 | 100 |
| Indexed pages (`documents.total_pages`, statuses except `failed`) | 200 | 2 000 | 20 000 |
| Chat tokens per period (`rag_audit_logs.tokens_used`) | 100 000 | 1 000 000 | 10 000 000 |
| SSO / SAML | no | no | yes |
| Custom domain | no | no | yes |

Do not bill embeddings separately: cost is per page. Storage GB — soft guideline, not a hard limit.

Token window — `organizations.current_period_start` / `current_period_end` (default 30 days from org creation, `PLAN_PERIOD_DAYS`). Expired window rolls forward on quota check. Pages and seats — current state, not reset with period.

### Where to enforce

- **Seats:** invite and JIT SSO, before creating membership.
- **Pages:** `POST /documents/upload`, if current page sum already ≥ cap → `402` without enqueueing Celery. After parse, if document `total_pages` would push org over cap → `failed` + quota `last_error`, delete chunks, remove MinIO bytes (as ingest error). Do not leave `ready` over cap.
- **Tokens:** `POST /chat/stream` **before** retrieval and LLM. Exhausted → SSE `type: error` with same meaning as HTTP `402` (fixed phrase). Do not call embedder or write foreign chunk ids.

Org-admin sees usage in settings. Employee at limit sees “organization quota exceeded”, no billing numbers and no hint of foreign files.

`organizations.status = suspended`: login to this org rejected. Billing `past_due` / cancel → same `suspended`. Plan change does not read another org’s corpus and does not bypass inner ACL.

## Provider (`BILLING_PROVIDER`)

Single interface: current subscription, plan change, cancel, `past_due`. Quota handlers read org rows only.

| Value | When | Money |
| --- | --- | --- |
| `dev` (Compose default and non-`production`) | local, CI, portfolio without payment processing | none. Org-admin changes plan via API/UI |
| `stripe` | when account and network to `api.stripe.com` exist | Checkout + Customer Portal + webhooks |

Stripe **test keys do not replace** `dev`: they still need account and Stripe access. From some regions this is often impossible — portfolio and CI acceptance use `dev`.

`stripe` adapter in code is fine; live `api.stripe.com` not required in CI. YooKassa and other processors — separate provider on the same port.

`ENVIRONMENT=production` and `BILLING_PROVIDER=dev`: explicit choice (demo VPS), `/ready` marks billing as `dev`. `BILLING_PROVIDER=stripe` without keys → billing in `/ready` not `ok` (`degraded`), app need not crash. Do not call Stripe “just in case” when `dev`.

## Dev billing

Org-admin screen (**Dev billing** badge): pick plan, “activate”, “past due”, “cancel”. Same `plan` / `billing_status` / `status` transitions as webhook would.

`POST /api/v1/billing/dev/simulate` — only `BILLING_PROVIDER=dev`, only **current** org from session, only `require_admin`. Else `404` (like disabled inspect). Cannot simulate Globex from Acme session.

## Stripe (optional)

Checkout + Portal. Do not store cards. `stripe_customer_id` / `stripe_subscription_id` on org, not in JWT or chat body. Webhooks: `checkout.session.completed` (bind via `client_reference_id`), `customer.subscription.updated|deleted`, `invoice.paid`, `invoice.payment_failed`. Org after checkout — only by Stripe id on org row, not `metadata.organization_id`. Signature, idempotency via `event.id` in `billing_events`. Price → plan mapping. Only org-admin of **current** org pays. Webhook does not read corpus or log chunk text.

## Forbidden

- Client `plan` / `org_id` as quota or ACL source.
- LLM cache without `org_id`; plan not needed in cache key.
- Platform-admin viewing usage or all customer corpora.
- `402`/`403` that confirm file or org existence outside session.
- Enable SSO or custom domain for org whose plan lacks it (even via dev-simulate foreign tenant — not in session).
