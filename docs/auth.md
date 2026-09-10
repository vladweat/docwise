# Auth и ACL

Связано: [security-rbac rule](../.cursor/rules/security-rbac.mdc), [tenancy.md](tenancy.md), [retrieval.md](retrieval.md), [data-model.md](data-model.md).

Два слоя: **организация** (`org_id` сессии) и **роли/отделы** внутри неё. Роли не изолируют компании.

## Сессия

v1 — cookie-session ChainWise, куки `dw_access` / `dw_refresh` (см. [decisions.md](decisions.md) ADR-007).

- Login / register / Google отдают пользователя в JSON и ставят куки; `access_token` в теле нет. SSO ACS ставит те же куки, без токена в JSON.
- В access-токене есть `org_id` текущего членства; `GET /auth/me` отдаёт org + роль membership. Смена org — `POST /auth/switch-organization` (только своё membership), новые куки. На hostname, привязанном к org, смена на другую org запрещена ([ADR-015](decisions.md)).
- `GET /health` и `GET /ready` без auth. Остальной `/api/v1/*` — `get_current_user` (только cookie).
- CSRF: при cross-site cookies (`SameSite=None`) мутации требуют allowlisted `Origin` или `X-Requested-With: Docwise`. Origin allowlist после M6 — канонический фронт **и** verified hostname текущей org.
- Manage KB (upload, delete, смена `access_roles`, инвайты, биллинг, SSO, домен): только `require_admin` **текущей org**. Manager не загружает, не удаляет и не меняет ACL. Retrieval / list / status / raw **всё равно** фильтруются `org_id` + ACL документа, без admin-override и без чтения чужой org.

Не принимать `access_roles`, `user_id`, `document_ids`, `org_id` / `organization_id` из тела как источник прав.

## Роли пользователя

До M5 колонки жили на `users`. Сейчас — на `organization_memberships` (один человек — разные роли в разных org).

| Роль членства | Смысл |
| --- | --- |
| `admin` | Управление KB, инвайтами, биллингом, SSO и доменом **этой** org; `POST /search/inspect` при `ENABLE_SEARCH_INSPECT` (retrieval всё равно по `org_id` + ACL документа, без override) |
| `manager` | Типичный доступ к политикам отдела. Inspect — `403` |
| `employee` | Базовый сотрудник. Inspect — `403` |

Плюс `departments: string[]` (`engineering`, `hr`, `finance`, …) на том же членстве.

Оператор платформы с доступом к корпусам клиентов в M5/M6 не предусмотрен.

## SSO / SAML (M6)

Канон: [ADR-014](decisions.md). Гейт плана — [billing.md](billing.md).

- Коннектор (`organization_sso_connections`) принадлежит одной org. Маршруты `/api/v1/auth/sso/{slug}/login` и `…/acs`: `{slug}` → эта org, не атрибут assertion.
- SP-initiated в v1; ACS принимает IdP-initiated, если метаданные те же. Успех → `dw_access` / `dw_refresh` с `org_id` коннектора.
- JIT (если включён на коннекторе): создать/найти `users` по email и membership **только этой** org. Глобальный email как в M5: человек уже в Globex может получить Acme; роли Globex не менять. Seats-квота → `402`. Без JIT — только существующее membership или инвайт.
- `organizations.sso_enforced`: пароль и Google не выбирают эту org как текущую; `POST /auth/switch-organization` без свежего SSO-assertion (флаг в сессии / короткий redis-ключ) → отказ. Иначе SSO обходится через другую фирму.
- Маппинг групп IdP → `role` / `departments` — JSON/таблица, которую правит org-admin. Не писать группы в `documents.access_roles`. Не подменять `org_id`.
- Email без verified-эквивалента — отказ, как у Google.
- Compose: `SSO_PROVIDER=dev`, фикстурная assertion. План без entitlement SSO → `403` на upsert коннектора, не «неверный IdP».

Google OIDC M0 остаётся consumer-входом для планов без SSO. Это не замена SAML.

## Сборка `allowed_roles` для поиска

```
allowed_roles = { membership.role } ∪ set(membership.departments) ∪ { "all" }
```

До M5 то же собиралось с `users.role` / `users.departments` (один неявный тенант). Сейчас только membership текущей org.

Фильтр (оба конъюнкта):

```sql
WHERE organization_id = :current_org
  AND access_roles && ARRAY['employee', 'hr', 'all']::text[]
```

Документ с `access_roles = ["hr"]` виден пользователю **этой org**, у которого `hr` в `role` или `departments`. Документ `["all"]` виден всем членам **этой** организации, не всем залогиненным в SaaS.

Литералы ролей документа (теги админки): `admin`, `manager`, `employee`, отделы (`hr`, `finance`, …), плюс `all` / UI-лейбл **General**.

## Поверхности с одним правилом

| Поверхность | Проверка |
| --- | --- |
| `GET /documents` | `organization_id` сессии **и** `access_roles` пересекается с `allowed_roles` |
| `GET /documents/{id}/raw` | то же; иначе 404 (не 403 с названием файла; чужая org неотличима) |
| chat / search / inspect | `organization_id` **и** `&&` на `document_chunks`; не полагаться на промпт |
| `POST /search/inspect` | cookie; флаг выкл → `404`; не org-admin → `403`; затем тот же фильтр, что у чата |
| KB: `PATCH /documents/{id}` | `require_admin` текущей org; пишет `access_roles` документа **и** всех чанков; `org_id` не меняется |
| Billing / SSO / domain | `require_admin` текущей org; чужая org неотличима (`404` на simulate и чужой slug) |
| LLM cache | ключ включает `org_id` и канонический набор `allowed_roles` |

Смена ACL файла: обновить `documents` **и** все строки `document_chunks` этого файла (или полный re-upsert). Иначе индекс врёт.
