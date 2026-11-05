# API диагностики поиска

`inspect` показывает этапы поиска. Это не позволяет обойти ACL: организация и роли доступа к документам
остаются теми же, что используются в чате.

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

`query` — 1–4000 символов после удаления пробелов по краям; `limit` — 1–50 (по умолчанию 15) результатов на каждый этап.
Поля `access_roles`, `document_ids`, `user_id` и `organization_id` из тела запроса не задают права доступа.

Ответ содержит списки `dense`, `sparse`, `rrf` и `reranked`. Каждый результат содержит `chunk_id`, `document_id`, `page`,
`score` и короткий `snippet`; полный текст фрагмента не возвращается.

| Условие | HTTP |
| --- | --- |
| Нет сессии | `401 auth.unauthorized` |
| `ENABLE_SEARCH_INSPECT` выключен | `404 resource.not_found` |
| Нет роли администратора организации | `403 auth.forbidden` |
| Неверные `query` или `limit` | `422 request.validation` |
| Ошибка модели векторных представлений или повторного ранжирования | `503 service.unavailable` |

`inspect` записывает в `rag_audit_logs` поисковый запрос, пользователя, ID текстовых фрагментов после повторного
ранжирования и задержку; для этого маршрута `session_id`, `message_id` и `tokens_used` равны `null`.
API не подтверждает наличие чужих документов.

Настройка флага и границы доступа: [безопасность](../../security/overview.md), [аутентификация](../../platform/auth.md).
