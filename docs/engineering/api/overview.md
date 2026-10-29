# Общие ответы API

Этот файл дополняет [главную страницу API](../api.md). Точные routes и схемы берутся из
`backend/app/api/` и `backend/app/schemas/`; OpenAPI `/docs` включён только вне production.

## HTTP-ошибки

Все HTTP failures используют один envelope:

```json
{
  "error": {
    "code": "request.validation",
    "message": "Request validation failed",
    "details": { "issues": [{ "location": ["body", "query"], "code": "missing" }] }
  }
}
```

`details.issues` содержат locations и validator codes, но не отправленные значения или exception text.
Необработанная ошибка возвращает общий `500`. Frontend сохраняет совместимость с legacy `detail`
форматом во время rollout.

Ошибки после начала stream используют [чатовый SSE формат](chat.md), не HTTP envelope.

## Health endpoints

| Route | Что проверяет | Ответ |
| --- | --- | --- |
| `GET /` | Метаданные сервиса; `/docs` будет `null` в production | `200` |
| `GET /health` | Только liveness процесса | `200`, пока процесс отвечает |
| `GET /ready` | PostgreSQL/pgvector, Redis, S3 storage и billing adapter | `200` ready или `503` degraded |

`BILLING_PROVIDER=dev` отображается как `dev`, не как ошибка. Stripe без нужных credentials делает readiness degraded.

## Общие auth и tenancy правила

- Cookie session требуется на всех API routes, кроме явно публичных login/register/Google, SSO login/ACS
  и Stripe webhook routes.
- Первичная регистрация создаёт user, organization и membership `admin`; приглашение добавляет user в существующую org.
- `organization_id`, `org_id`, `access_roles`, `document_ids` и `user_id` из chat/search body не являются authority.
- Идентификатор чужого документа/сессии не подтверждается: API возвращает тот же `404`, что и для отсутствующей записи.

Подробнее: [auth](../../platform/auth.md) и [tenancy](../../platform/tenancy.md).
