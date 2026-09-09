# Auth и ACL

Связано: [security-rbac rule](../.cursor/rules/security-rbac.mdc), [retrieval.md](retrieval.md), [data-model.md](data-model.md).

## Сессия

v1 — cookie-session ChainWise, куки `dw_access` / `dw_refresh` (см. [decisions.md](decisions.md) ADR-007).

- Login / register / Google отдают пользователя в JSON и ставят куки; `access_token` в теле нет.
- `GET /health` и `GET /ready` без auth. Остальной `/api/v1/*` — `get_current_user` (только cookie).
- CSRF: при cross-site cookies (`SameSite=None`) мутации требуют allowlisted `Origin` или `X-Requested-With: Docwise`.
- Manage KB (upload, delete, смена `access_roles`): только `require_admin`. Manager в v1 не загружает, не удаляет и не меняет ACL. Retrieval / list / status / raw **всё равно** фильтруются ACL документа (`allowed_roles`), без admin-override.

Не принимать `access_roles`, `user_id`, `document_ids` из тела как источник прав.

## Роли пользователя

| `users.role` | Смысл |
| --- | --- |
| `admin` | Управление KB, inspect (за флагом) |
| `manager` | Типичный доступ к политикам отдела + manage по решению ADR |
| `employee` | Базовый сотрудник |

Плюс `users.departments: string[]` (`engineering`, `hr`, `finance`, …).

## Сборка `allowed_roles` для поиска

```
allowed_roles = { user.role } ∪ set(user.departments) ∪ { "all" }
```

Фильтр:

```sql
access_roles && ARRAY['employee', 'hr', 'all']::text[]
```

Документ с `access_roles = ["hr"]` виден пользователю, у которого `hr` в `role` или `departments`. Документ `["all"]` виден всем аутентифицированным.

Литералы ролей документа (теги админки): `admin`, `manager`, `employee`, отделы (`hr`, `finance`, …), плюс `all` / UI-лейбл **General**.

## Поверхности с одним правилом

| Поверхность | Проверка |
| --- | --- |
| `GET /documents` | строка `documents.access_roles` пересекается с `allowed_roles` |
| `GET /documents/{id}/raw` | то же; иначе 404 (не 403 с названием файла) |
| chat / search / inspect | тот же `&&` на `document_chunks.access_roles`; не полагаться на промпт |
| KB: `PATCH /documents/{id}` | `require_admin`; пишет `documents.access_roles` **и** все чанки этого файла |
| LLM cache | ключ включает канонический набор `allowed_roles` |

Смена ACL файла: обновить `documents` **и** все строки `document_chunks` этого файла (или полный re-upsert). Иначе индекс врёт.
