# Открытый технический долг

**Сверено:** 2026-10-29 · **код:** текущая ветка `main` · **публичное демо:**
[docwise.wvzl.site](https://docwise.wvzl.site).

Приоритет отражает возможный impact. Статус «исправлено в коде» не означает, что есть нагрузочная проверка,
restore drill или подтверждённый SLA.

## Наиболее важное для следующего этапа

| Приоритет | Риск | Что это значит сейчас | Следующее действие |
| --- | --- | --- | --- |
| High | Нет проверенного восстановления | Backup включает PostgreSQL и S3, но нет restore drill, off-site копии и заданного RPO/RTO | Провести drill в изолированной среде |
| High | Single-VPS demo, без HA | Один Postgres, Redis, Garage node и ingress | Для production определить redundancy, monitoring и recovery targets |
| Medium | Нет реального enterprise SSO | Только dev fixture; публичный demo отключил SSO | Не обещать SAML/OIDC до внедрения provider adapter |
| Medium | Redis — общий blast radius | Queue, refresh state, rate limits, locks и cache используют Redis | Наблюдать availability; при росте разделить workload/DB |
| Medium | Ingestion не атомарен end-to-end | Статусы, chunks и S3 side effects фиксируются раздельно | Сохранять dry-run recovery и проверять повтор при restore drill |
| Medium | Chat corpus snapshot race | ACL/corpus может измениться между retrieval и audit/persist | Ввести version/snapshot guarantee, если требуется строгая воспроизводимость |
| Medium | Нет централизованных metrics/traces | Есть healthchecks, JSON logs и pilot checks | Добавить метрики до production/роста нагрузки |

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

- Публичный профиль обновлён из текущего checkout; backend и frontend healthchecks были healthy.
- После последнего обновления проверены TLS, `GET /` и `/ready` (`200`).
- В этой последней проверке полный chat flow после раннего `meta` не запускался.
- Не проводились restore drill, нагрузочный прогон, failover Redis/Postgres/Garage или проверка real SAML/Stripe credentials.
- Внешние firewall/network policies проверены только в пределах доступной VPS/Compose конфигурации.

Для подробных процедур: [operations](../operations/operations.md), [public demo](../operations/public-demo.md),
[security](../security/overview.md).
