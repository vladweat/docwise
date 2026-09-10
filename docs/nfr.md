# Нефункциональные требования

Дополняет [srs.md](srs.md). Пороги v1 — локальный Docker Compose / организация, не SLA облака. Нулевые утечки между org обязательны (см. [tenancy.md](tenancy.md)).

## Безопасность

- Auth обязателен на всём `/api/v1/*` кроме login/register/google. `/health` и `/ready` публичны.
- Сессия только в httpOnly cookies; Bearer не принимается. CSRF-заголовок/Origin при `SameSite=None`.
- RBAC enforcement: SQL-фильтр `organization_id` **и** `access_roles && allowed_roles` на pgvector/FTS **до** LLM. Промпт не является механизмом ACL и не изолирует компании.
- Один и тот же ACL на list / status / raw / search / inspect / chat, плюс тот же `org_id`.
- Не подтверждать существование чужого файла («документ X скрыт»), в том числе файла другой организации.
- LLM cache key включает `org_id` (M5) и `allowed_roles` вызывающего (иначе кэш — дыра ACL или кросс-тенант).
- Секреты только в env. Не коммитить `.env`, ключи, дампы NDA.
- Audit: `rag_audit_logs` без тела чанков (только UUID после реранкера). Inspect в production за `ENABLE_SEARCH_INSPECT` (по умолчанию выкл); чужой файл не подтверждается.
- Upload: лимит размера (ориентир 50 MB), только PDF в v1, SHA-256, rate limit как в ChainWise.
- XSS: не рендерить HTML из PDF/LLM как `dangerouslySetInnerHTML` без санитайза. Markdown ответа — безопасный рендер.

## Надёжность ingestion

- Парсинг и эмбеддинги только в Celery, не в upload-handler.
- Redis lock `indexing_lock:{document_id}`. Повтор задачи идемпотентен.
- Падение воркера: `failed` + `last_error`, индекс либо полный, либо удалён (нет «полуготового» документа со статусом ready).
- Каскадный DELETE: Postgres (документ + чанки), объект MinIO. Частичный успех логировать и ретраить удаление индекса.

## Производительность (ориентиры v1)

| Операция | Цель |
| --- | --- |
| Upload ACK | < 2 s до `201` + `pending` (без парсинга) |
| Ingest PDF ~20 стр. | минуты, не часы; прогресс через status |
| Chat TTFT (цитаты) | первые SSE citations до стрима токенов |
| Retrieval Top-4 | dense+sparse+RRF+rerank на CPU, без скролла всей коллекции |

Запрещено: `scroll` всех точек корпуса в RAM для BM25.

## Наблюдаемость

- JSON-логи с redaction (токены, пароли, длинный текст PDF).
- `rag_audit_logs`: query, user, UUID чанков после реранкера, latency_ms, tokens_used, feedback. Пишут чат и inspect. Не UUID и не полный текст.
- `/health` — liveness (`{"status":"ok"}`). `/ready` — Postgres + pgvector + Redis + MinIO (`200` / `503`).

## Качество RAG

- Faithfulness: ответ только из Top-4. Иначе фиксированная фраза отказа.
- Каждая фактическая клауза — цитата `{doc_id, page}`.
- Eval: [evaluation.md](evaluation.md). Релиз: Faithfulness ≥ 0.8 и **ноль** ACL-утечек на `must_not_doc_ids`. Первый прогон 2026-09-10: Faithfulness 1.000, Context Precision 0.976, Answer Relevance 0.789, page hit 0.929, ACL PASS. Ноль утечек `must_not` документов **другой** org, даже с тегом `all`.

## Совместимость и i18n

- Документы: EN/RU корпоративный текст.
- Пользовательские строки UI и отказы LLM: русский или английский — один язык интерфейса на организацию. i18n-фреймворк не обязателен.
- Идентификаторы API и код — английский.
