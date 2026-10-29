# Organizations, планы и enterprise endpoints

Все операции работают с текущей организацией из cookie session. Переданные клиентом `organization_id` и `plan`
не заменяют контекст сессии.

## Регистрация, участники и переключение org

```http
POST /api/v1/auth/register
POST /api/v1/auth/switch-organization
GET  /api/v1/organizations/members
POST /api/v1/organizations/invites
```

- Регистрация без invite создаёт user, organization и membership `admin`.
- Invite принимает `{ "email", "role", "departments" }`; существующему user добавляется membership,
  новый принимает приглашение при регистрации.
- Seat quota проверяется до создания membership; превышение — `402`.
- Switch принимает `{ "organization_id": "<uuid>" }` только при существующем membership.
- Если hostname закреплён за другой org, смена организации через этот host запрещена.

Роли и границы tenant: [tenancy.md](../../platform/tenancy.md).

## План и квоты

```http
GET  /api/v1/billing/subscription
GET  /api/v1/billing/usage
POST /api/v1/billing/plan
```

Org-admin видит текущий план, usage, entitlements и provider. Тело `POST /billing/plan`:
`{ "plan": "team" }` — это целевой план **текущей org**, не произвольной организации.

| Provider | Поведение |
| --- | --- |
| `dev` | Сразу обновляет состояние в Postgres; используется local, CI и public demo |
| `stripe` | Использует checkout/webhook adapter; без ключей недоступен и влияет на readiness |

```http
POST /api/v1/billing/dev/simulate
```

Dev-only смена состояния (`set_plan`, `past_due`, `cancel`, `activate`). Если `BILLING_PROVIDER != dev`
или caller не org-admin, route не доступен. Webhook Stripe не требует cookie, но проверяет подпись и event id.

Quota — `402`, rate limit — `429`, отсутствие entitlement — `403`. Подробности: [billing.md](../../platform/billing.md).

## SSO

```http
GET  /api/v1/auth/sso/{slug}/login
POST /api/v1/auth/sso/{slug}/acs
GET  /api/v1/organizations/sso
PUT  /api/v1/organizations/sso
```

`{slug}` выбирает org через connector; assertion не выбирает tenant. Connector settings требуют org-admin и
SSO entitlement. Если `SSO_PROVIDER != dev`, login/ACS отвечают `404`.

В local Compose `dev` включает fixture, а не настоящий SAML/OIDC. Публичный demo задаёт `disabled`.
Реального production IdP adapter нет. См. [auth.md](../../platform/auth.md).

## Custom domain

```http
GET  /api/v1/organizations/domain
PUT  /api/v1/organizations/domain
POST /api/v1/organizations/domain/verify
```

Требуется org-admin и соответствующий entitlement. `PUT` принимает hostname или `null` для отключения.
Verification использует TXT/HTTP token; в Compose это проверка dev token, не настройка Let's Encrypt.
Непроверенный hostname не закрепляет текущую сессию за организацией.

Неизвестная/чужая организация не раскрывается через hostname, slug или body ID.
