# Auth и ACL

Связано: [security-rbac rule](../.cursor/rules/security-rbac.mdc), [tenancy.md](tenancy.md), [retrieval.md](retrieval.md), [data-model.md](data-model.md).

Два слоя: **организация** (`org_id` сессии) и **роли/отделы** внутри неё. Роли не изолируют компании. До M5 слой организации в коде отсутствует (один неявный тенант).

## Сессия

v1 — cookie-session ChainWise, куки `dw_access` / `dw_refresh` (см. [decisions.md](decisions.md) ADR-007).

- Login / register / Google отдают пользователя в JSON и ставят куки; `access_token` в теле нет.
- После M5 в access-токене есть `org_id` текущего членства; `GET /auth/me` отдаёт org + роль membership. Смена org — `POST /auth/switch-organization` (только своё membership), новые куки.
- `GET /health` и `GET /ready` без auth. Остальной `/api/v1/*` — `get_current_user` (только cookie).
- CSRF: при cross-site cookies (`SameSite=None`) мутации требуют allowlisted `Origin` или `X-Requested-With: Docwise`.
- Manage KB (upload, delete, смена `access_roles`, инвайты): только `require_admin` **текущей org**. Manager не загружает, не удаляет и не меняет ACL. Retrieval / list / status / raw **всё равно** фильтруются `org_id` + ACL документа, без admin-override и без чтения чужой org.

Не принимать `access_roles`, `user_id`, `document_ids`, `org_id` / `organization_id` из тела как источник прав.

## Роли пользователя

До M5 колонки живут на `users`. После — на `organization_memberships` (один человек — разные роли в разных org).

| Роль членства | Смысл |
| --- | --- |
| `admin` | Управление KB и инвайтами **этой** org; `POST /search/inspect` при `ENABLE_SEARCH_INSPECT` (retrieval всё равно по `org_id` + ACL документа, без override) |
| `manager` | Типичный доступ к политикам отдела. Inspect — `403` |
| `employee` | Базовый сотрудник. Inspect — `403` |

Плюс `departments: string[]` (`engineering`, `hr`, `finance`, …) на том же членстве.

Оператор платформы с доступом к корпусам клиентов в M5 не предусмотрен.

## Сборка `allowed_roles` для поиска

```
allowed_roles = { membership.role } ∪ set(membership.departments) ∪ { "all" }
```

До M5 то же с `users.role` / `users.departments` (один неявный тенант).

Фильтр (после M5 — оба конъюнкта; до M5 в коде только второй):

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
| LLM cache | ключ включает `org_id` и канонический набор `allowed_roles` |

Смена ACL файла: обновить `documents` **и** все строки `document_chunks` этого файла (или полный re-upsert). Иначе индекс врёт.
