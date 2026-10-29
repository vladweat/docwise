# Нефункциональные требования

Пороговые значения производительности — ориентиры для локального Compose и одной организации, не SLA.
Нулевые утечки между организациями — обязательное требование. Реальные защитные границы описаны в
[security](../security/overview.md) и [tenancy](../platform/tenancy.md).

## Безопасность

| Область | Требование |
| --- | --- |
| Аутентификация | API использует host-only HttpOnly cookies; проверяет активную сессию и membership в БД |
| Tenant | `organization_id` берётся из сессии/БД, не из тела запроса |
| Документный ACL | `access_roles` применяется к list/status/raw и обоим search путям до LLM |
| Кэш | Ключ учитывает организацию, поколение индекса и разрешённые роли |
| Audit | Хранить query и IDs chunks; не хранить полный текст chunks |
| Ошибки | Не возвращать stack trace, значения формы или сведения о чужом документе |
| Cookies | Для cross-site режима требовать доверенный origin/CSRF header; production использует secure cookie |
| Secrets | `.env`, API keys, storage credentials и реальные документы не коммитить |

RLS на corpus-таблицах — дополнительный слой только при non-superuser runtime role
`docwise_rls`. Она не заменяет SQL-фильтры приложения.

## Надёжность ingestion

- Upload handler сохраняет файл и ставит Celery задачу; parsing выполняется worker-ом.
- Retry ограничен transient ошибками; ошибки формата, parsing и quota должны завершаться как `failed`.
- Обработка chunks и этапов не является единой транзакцией с S3; повторный ingestion и recovery проверяются отдельно.
- Удаление S3 object повторяется через transactional `storage_deletions` outbox.
- После потери Redis очередь может потребовать ручной dry-run → apply recovery.

## Производительность и ёмкость

| Операция | Ориентир |
| --- | --- |
| Upload acknowledgement | До 2 секунд, без parsing в HTTP request |
| PDF около 20 страниц | Минуты; прогресс виден по статусу |
| Chat time-to-first-answer | Citations должны прийти до token stream; ранний `meta` может прийти раньше citations |
| Retrieval | Dense + FTS + RRF + rerank без загрузки всего корпуса в память |

Запрет: не делать corpus-wide `scroll` ради одного chat query.

## Масштабирование

Публичный профиль — один VPS, одна PostgreSQL, один Redis, один Garage node, один Beat scheduler.
Перед масштабированием нужно определить RPO/RTO, разделить критические Redis workloads при необходимости,
проверить DB connection pool и перенести secrets/наблюдаемость в production-grade сервисы.

## Наблюдаемость и качество

- `/health` проверяет процесс; `/ready` — зависимости и billing status.
- Структурированные логи редактируют чувствительные поля; Sentry опционален.
- Central metrics/dashboard и распределённый tracing в репозитории не настроены.
- RAG качество отслеживается golden set и ACL-negative кейсами; текущие числа — в [evaluation](evaluation.md).

## Совместимость

API и переменные конфигурации имеют English identifiers. Пользовательский интерфейс и документация могут быть локализованы;
ошибки API должны оставаться безопасными и пригодными для локализации.
