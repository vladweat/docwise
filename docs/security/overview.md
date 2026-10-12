# Безопасность и доверительные границы

Документ описывает реализованные механизмы, а не сертификацию или гарантию отсутствия
уязвимостей. Канонические детали tenancy и сессий: [tenancy](../platform/tenancy.md) и
[auth](../platform/auth.md).

## Доверительные границы

```mermaid
flowchart LR
  B[Browser] -->|host-only cookies + CSRF checks| API[FastAPI]
  API -->|organization_id + ACL SQL| PG[(PostgreSQL)]
  API -->|authenticated object access| S3[(MinIO)]
  API -->|sessions, limits, cache| R[(Redis)]
  API -->|только разрешённые Top-4 chunks| LLM[OpenAI-compatible API]
  W[Celery worker] --> PG
  W --> S3
  W --> R
```

Основная граница tenant — `organization_id`; `access_roles` — внутренняя граница документов
организации. Клиентские поля `organization_id`, `org_id`, `user_id`, `access_roles` и
`document_ids` не являются источником полномочий.

## Аутентификация

- API v1 принимает host-only cookies `dw_access` и `dw_refresh`; Bearer auth не реализован.
- JWT содержит `sub`, текущий `org_id`, `typ`, `exp`; refresh также содержит `jti`.
- Role не хранится в token и читается из `organization_memberships`.
- Refresh `jti` хранится и ротируется в Redis.
- Пароли хэшируются через password helpers; `hashed_password` не возвращается API.
- Google ID token проверяется с `GOOGLE_CLIENT_ID`.
- Production startup блокируется при default `SECRET_KEY`.

Cookies не используют parent `Domain`, поэтому session одного tenant hostname не должна
автоматически передаваться другому. При hostname, привязанном к организации, host pin должен
совпадать с `org_id` сессии.

## Авторизация и изоляция

`allowed_roles = {membership.role} ∪ departments ∪ {"all"}`.

Dense, FTS, list, status и raw document paths применяют:

```sql
WHERE organization_id = :current_org
  AND access_roles && :allowed_roles
```

Фильтрация выполняется до RRF, rerank, LLM и формирования citation. Admin не получает
автоматического обхода внутреннего ACL. `require_kb_admin` разрешает запись `admin` и
`manager`; billing, invites, SSO, domain и inspect требуют `admin`.

RLS включена миграцией только для `documents` и `document_chunks`. Она является
дополнительной защитой и не заменяет application filters. Текущий Compose подключается
PostgreSQL superuser и не задаёт `DOCWISE_RLS_SESSION_ROLE`; в такой конфигурации RLS нельзя
считать действующей. Tests создают отдельную session role, но это не production setup.

## CSRF и CORS

При `COOKIE_SAMESITE=none` mutating `/api/v1` requests требуют разрешённый `Origin`/`Referer`
или `X-Requested-With: Docwise`. Stripe webhook и SSO ACS исключены, поскольку имеют
собственную модель проверки. `TenantCORSMiddleware` разрешает configured origins и
проверенные tenant hostnames.

Ошибочная широкая настройка `CORS_ORIGINS`, отключение `COOKIE_SECURE` или использование
недоверенного proxy меняют эту границу и требуют отдельного review.

## Секреты и внешние сервисы

- `.env` исключён из Git; `.env.example` содержит placeholders.
- Чувствительные значения: `SECRET_KEY`, DB/S3 credentials, `OPENAI_API_KEY`,
  `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, `SENTRY_DSN`.
- LLM получает только прошедшие SQL ACL Top-4 chunks. Реализован OpenAI-compatible transport;
  отдельного Anthropic transport нет.
- MinIO bucket проверяется как private, оригиналы выдаются через authenticated API.
- Stripe webhook должен пройти provider signature validation и имеет idempotency table.
- `SSO_PROVIDER=dev` — fixture, не production identity provider.

## Логи, audit и sensitive data

`RedactingJsonFormatter` и Sentry scrubber маскируют известные sensitive keys и bulk text.
`rag_audit_logs` хранит query пользователя, chunk UUIDs, latency, tokens и feedback, но не
полный chunk text. Автоматический purge для декларируемого retention period не реализован.

В логах и документации запрещено публиковать:

- access/refresh tokens и cookie values;
- пароли, API keys, private keys и webhook secrets;
- содержимое customer documents и database dumps;
- restricted snippets или filenames в ошибках другого tenant.

## Rate limiting

Redis-backed limits применяются к auth по IP, upload и chat по user ID. При ошибке Redis
реализация пропускает запрос (fail-open). Rate limiting не заменяет WAF, network controls или
provider quotas.

## Подтверждённые ограничения

| Severity | Ограничение | Последствие |
| --- | --- | --- |
| High | Compose использует PostgreSQL superuser без runtime role | RLS может обходиться; остаются application SQL filters |
| High | Внутренние data services опубликованы без TLS | Нужен firewall/private network перед внешним deployment |
| Medium | Production SSO adapter отсутствует | `dev` fixture нельзя использовать как enterprise SSO |
| Medium | Rate limit fail-open при отказе Redis | Защита от abuse деградирует |
| Medium | Один Redis DB для broker/session/cache/locks | Общая зона отказа и отсутствие session continuity после restore |
| Medium | Автоматического retention purge нет | Audit query может храниться дольше заявленной политики |
| Low | OpenAPI скрыт, но routes остаются доступны | Это уменьшает discoverability, но не является access control |

Полная приоритизация и remediation: [technical-debt.md](../maintenance/technical-debt.md).
