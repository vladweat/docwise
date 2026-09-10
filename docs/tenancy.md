# Мультитеннантность (shared B2B SaaS)

Канон изоляции между компаниями. Внутри компании действует [auth.md](auth.md) (роли и отделы). Модель таблиц: [data-model.md](data-model.md). Решение: [ADR-012](decisions.md).

Docwise — **shared B2B SaaS**: много организаций на одном деплое (общий Postgres, MinIO, Redis, LLM). On-prem / private cloud — тот же код с одной организацией, не отдельный продукт.

Код до M5 жил как **один неявный тенант**. После M5 на одном деплое много организаций; изоляция — SQL `organization_id`.

## Два слоя доступа

Роли **не** заменяют организацию. `hr` и `all` — теги внутри фирмы, не идентификаторы клиента.

```
1. Тенант (внешняя стена):  org_id = current_org     — чужая компания невидима
2. RBAC (внутренняя стена): access_roles && allowed_roles  — стажёр не читает HR
```

На каждый list / status / raw / dense / sparse / inspect / chat:

```sql
WHERE org_id = :current_org
  AND access_roles && ARRAY['employee', 'hr', 'all']::text[]
```

`current_org` берётся из сессии (cookie/JWT), **не** из тела запроса. Не фильтровать тенант «потом в промпте». Не использовать `access_roles = ['acme']` вместо `org_id`.

Пока M5 не был влит, в коде был только слой 2. Слой 1 обязателен на каждом list / search / chat.

## Организация и членство

| Сущность | Смысл |
| --- | --- |
| `users` | Глобальный человек (email unique). Пароль / Google. Без `role` / `departments` |
| `organizations` | Компания-клиент: имя, slug, статус |
| `organization_memberships` | Связь user↔org: `role` (`admin` \| `manager` \| `employee`) и `departments[]` |

Один пользователь может состоять в нескольких организациях (подрядчик, холдинг). Роль **своя в каждой**: admin в Acme и employee в Globex — норма.

`require_admin` — **admin текущей организации**, не оператор платформы. Platform-admin, который читает чужие корпуса, в M5 нет и по умолчанию не появится.

## Планы, hostname, SSO (M6)

Канон квот: [billing.md](billing.md). SSO: [auth.md](auth.md). ADR-013–015.

- План и квоты — поля **этой** org. Смена плана в dev-simulate или Stripe не даёт читать другую org.
- Если `Host` привязан к организации (slug-поддомен или verified custom domain), он должен совпасть с `org_id` сессии. Hostname **пинит** тенант, не заменяет `WHERE organization_id = :current_org`.
- Куки сессии — host-only, без `Domain` на родительский суффикс платформы (иначе cookie Acme уедет на хост Globex).
- SSO-коннектор принадлежит одной org. Assertion не выбирает тенант.
- `all` по-прежнему только члены этой org, в том числе после SSO JIT.

На кастомном/slug-хосте Acme `switch-organization` в Globex запрещён (нужен хост Globex).

## Сессия

- Cookie `dw_access` / `dw_refresh` как в [ADR-007](decisions.md). В access-токене — `sub` (email/id) **и** `org_id` текущего членства.
- `GET /auth/me` отдаёт текущую org и роль членства, не «глобальную» роль.
- Смена org: только `POST /api/v1/auth/switch-organization` при существующем membership; новые куки. На hostname, привязанном к другой org, смена запрещена. Поле `organization_id` / `org_id` в chat/search/upload **игнорируется** как источник прав (как `access_roles` сегодня).
- Нет членства в org из токена → `401` / `403`, без списка чужих организаций в `detail`.

## Регистрация и инвайты

Self-serve:

1. `POST /auth/register` создаёт `users` + `organizations` + membership `admin`. Тело: email, password, `organization_name`.
2. Org-admin приглашает: `POST /api/v1/organizations/invites` `{ email, role, departments }`.
3. Существующий пользователь с этим email получает membership; новый — регистрируется по инвайту и входит в org, **не** создаёт вторую фирму по тому же инвайту.
4. Открытый register без имени организации не делает «employee глобального инстанса».

Первый пользователь пустой БД больше не «admin всей платформы»: он admin **своей** организации.

## Поверхности с одним правилом

| Поверхность | Проверка |
| --- | --- |
| `GET /documents`, `/raw`, `/status` | `org_id` + пересечение `access_roles` |
| chat / search / inspect | то же на `document_chunks` (`org_id` **и** ACL); чанки копируют `org_id` документа |
| KB write (upload, delete, PATCH ACL, инвайты) | membership `admin` **текущей** org; строка всё равно с `org_id` сессии; seats/pages квота M6 |
| чат-сессии, аудит | `org_id`; история Acme не подмешивается в Globex; токены периода — квота этой org |
| LLM cache | ключ включает `org_id` **и** канонический `allowed_roles` |
| `file_hash` | unique `(org_id, file_hash)`, не глобально |
| MinIO | ключ с префиксом org, без публичного URL |
| биллинг / usage | только текущая org; `dev/simulate` чужой org → `404` |
| SSO ACS | org из коннектора `{slug}`; JIT только в неё |
| custom domain | verified hostname → одна org; несовпадение с сессией → отказ |

Чужой тенант: `404` как у файла вне ACL. Не подтверждать, что у другой компании есть документ / совпал SHA-256.

## Запрещено

- Две компании в одной БД без `org_id` на документах **и** чанках.
- Считать `all` «всем залогиненным в SaaS».
- Кэш LLM только по ролям (employee Acme получит ответ, прогретый employee Globex).
- Клиентский `org_id` / `organization_id` как источник прав.
- Org-admin override внутренней ACL (как и сейчас: admin без `hr` не видит HR-файл).
- Подсказывать в ошибке `409`, что такой PDF уже есть у *другой* организации.
- Считать план, Stripe customer id или SAML-атрибут `org` источником `organization_id`.

## Вне M6 (позже)

Postgres RLS как defense-in-depth, консоль оператора платформы, SCIM. RLS не заменяет `org_id` в запросах приложения. Боевой эквайринг (live Stripe / ЮKassa) не критерий продукта, пока M6 закрыт на `dev`.
