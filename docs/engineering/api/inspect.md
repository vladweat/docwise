# Search Inspect API

`inspect` показывает этапы поиска для диагностики. Это не ACL bypass: org и document roles остаются теми же,
что используются в чате.

```http
POST /api/v1/search/inspect
Content-Type: application/json
```

```json
{
  "query": "What is the daily travel reimbursement cap?",
  "limit": 15
}
```

`query` — 1–4000 символов после trim; `limit` — 1–50 (default 15) hits на каждый этап.
Поля `access_roles`, `document_ids`, `user_id` и `organization_id` из тела запроса не задают доступ.

Ответ содержит списки `dense`, `sparse`, `rrf` и `reranked`. У hit есть `chunk_id`, `document_id`, `page`,
`score` и короткий `snippet`; полный текст chunk не возвращается.

| Условие | HTTP |
| --- | --- |
| Нет сессии | `401 auth.unauthorized` |
| `ENABLE_SEARCH_INSPECT` выключен | `404 resource.not_found` |
| Нет роли org-admin | `403 auth.forbidden` |
| Валидация query/limit | `422 request.validation` |
| Ошибка embedder/reranker | `503 service.unavailable` |

Inspect пишет в `rag_audit_logs` query, user, IDs chunks после rerank и latency; `session_id`, `message_id`
и `tokens_used` для этого маршрута `null`. Чужие документы не подтверждаются в ответе.

Настройка флага и границы доступа: [security](../../security/overview.md), [auth](../../platform/auth.md).
