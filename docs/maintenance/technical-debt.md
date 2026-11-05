# Открытый технический долг

**Инфраструктурные сведения сверены:** 2026-10-29 · **evaluation обновлена:** 2026-11-01 ·
**статус демо проверен:** 2026-11-05 — приостановлено, недоступно.

Приоритет отражает возможный impact. Статус «исправлено в коде» не означает, что есть нагрузочная проверка,
restore drill или подтверждённый SLA.

## Наиболее важное для следующего этапа

| Приоритет | Риск | Что это значит сейчас | Следующее действие |
| --- | --- | --- | --- |
| High | Нет проверенного восстановления | Backup включает PostgreSQL и S3, но нет restore drill, off-site копии и заданного RPO/RTO | Провести drill в изолированной среде |
| High | Single-VPS demo, без HA | Один Postgres, Redis, Garage node и ingress | Для production определить redundancy, monitoring и recovery targets |
| Medium | Нет реального enterprise SSO | Только dev fixture; публичный demo отключил SSO | Не обещать SAML/OIDC до внедрения provider adapter |
| Medium | RAG quality gates не пройдены | На последнем полном наборе из 132 кейсов Top-4 имеет Context Precision `0.952` и English Answer Relevance `0.799` против gates `0.975` и `0.827`; Top-2 также не проходит и теряет recall. См. [evaluation](../product/evaluation.md) и [каталог](../../reports/README.md) | Разобрать false refusals и judge-оценки контекстов по rank; не продвигать профиль или Top-K до повторной проверки |
| Medium | Redis — общий blast radius | Queue, refresh state, rate limits, locks и cache используют Redis | Наблюдать availability; при росте разделить workload/DB |
| Medium | Ingestion не атомарен end-to-end | Статусы, chunks и S3 side effects фиксируются раздельно | Сохранять dry-run recovery и проверять повтор при restore drill |
| Medium | Chat corpus snapshot race | ACL/corpus может измениться между retrieval и audit/persist | Ввести version/snapshot guarantee, если требуется строгая воспроизводимость |
| Medium | Нет централизованной observability | Есть приватный HTTP `/metrics`, healthchecks, JSON logs и pilot checks; scrape server/dashboard/traces отсутствуют | Подключить private Prometheus scrape и alerting до production/роста нагрузки |

## Исправлено в source и Compose

| Область | Текущее состояние |
| --- | --- |
| PostgreSQL RLS | Base и public-demo Compose задают `docwise_rls`; migration service создаёт роль/grants; runtime должен быть non-superuser |
| Сеть | Base ports привязаны к loopback; public profile публикует приложения через Caddy |
| Миграции | Один `db-migrate` выполняется до API/worker |
| Удаление объекта | PostgreSQL delete и `storage_deletions` outbox фиксируются транзакционно; S3 cleanup повторяется |
| Queue recovery | Dry-run-first CLI показывает stale ingestion candidates; apply требует явного флага |
| Retry и locks | Ingestion retry ограничен transient failures; Redis lock использует owner token |
| Same-session chat | Второй активный stream получает `409`; разные sessions независимы |
| API errors | HTTP API использует общий `{ error: { code, message, details? } }` envelope |
| Audit retention | Celery Beat ежедневно удаляет просроченные строки по `AUDIT_LOG_RETENTION_DAYS` |

Эти пункты уже не являются источниковыми backlog items. Их эксплуатационную надёжность всё ещё следует проверять.

## Runtime evidence и ограничения

- **Текущая проверка 2026-11-05:** контейнеры `docwise-public-demo-*` exited; HTTPS для `docwise.wvzl.site` не проходит TLS. Публичное демо приостановлено и недоступно.
- Предыдущие healthcheck/TLS/`GET /`/`/ready` результаты относятся к историческому состоянию до 2026-11-05; полный chat flow после раннего `meta` тогда не запускался. Они не подтверждают текущую доступность.
- Не проводились restore drill, нагрузочный прогон, failover Redis/Postgres/Garage или проверка real SAML/Stripe credentials.
- Внешние firewall/network policies проверены только в пределах доступной VPS/Compose конфигурации.

Для подробных процедур: [operations](../operations/operations.md), [public demo](../operations/public-demo.md),
[security](../security/overview.md).
