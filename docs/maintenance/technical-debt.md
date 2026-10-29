# Технический долг и риски

Дата аудита: 2026-10-12; remediation status refreshed 2026-10-29. Severity отражает
потенциальный impact, а не подтверждённую эксплуатацию уязвимости. Строки «риск» требуют
runtime-проверки.

| Severity | Компонент | Наблюдение и evidence | Потенциальный impact | Рекомендация | Статус |
| --- | --- | --- | --- | --- | --- |
| High | PostgreSQL RLS | Compose app containers задают `DOCWISE_RLS_SESSION_ROLE=docwise_rls`; `db-migrate` идемпотентно создаёт роль, membership и grants | Ручной deployment вне Compose может продолжить использовать superuser | Повторить runtime check роли/grants на VM и при каждом новом типе deployment | Закрыто в Compose source; runtime после обновления не проверен |
| High | Network exposure | Base Compose binds host ports to `127.0.0.1`; public-demo закрывает внутренние порты и направляет трафик через Caddy | Внешние deployments вне этих Compose профилей требуют отдельной сетевой политики | Проверять firewall и ingress при новом deployment | Закрыто для base/public-demo Compose; VM config не проверен |
| High | Migration startup | Одноразовый `db-migrate` service выполняет upgrades и блокирует старт API/worker до успеха | Runtime/scale behavior за пределами Compose не подтверждён | Запускать один migration job перед масштабированием API | Исправлено в Compose source; runtime не проверен |
| Medium | Backup/recovery | Backup содержит PostgreSQL, MinIO, Alembic revision и SHA-256; restore проверяет revision/checksums, синхронизирует bucket и показывает requeue кандидатов | Redis/session/cache не восстанавливаются; ручной restore drill не выполнен | Провести restore drill в отдельном изолированном окружении и определить RPO/RTO | Подготовлено в source; runtime drill не выполнен |
| Medium | SSO | Реализован только `SSO_PROVIDER=dev` fixture; public-demo задаёт `SSO_PROVIDER=disabled` | Enterprise SSO не готов; fixture нельзя выдавать за рабочий IdP | Реализовать реальный adapter до заявления о production SSO | Fixture явно обозначен и отключён на demo |
| Medium | Retention | Celery Beat ежедневно удаляет `rag_audit_logs` старше `AUDIT_LOG_RETENTION_DAYS` (default 90), ограниченными пакетами | Требуется ровно один Beat scheduler и наблюдение за ошибками задачи | Настроить alert/операционную проверку для production deployment | Реализовано в коде; runtime schedule не проверен |
| Medium | Redis availability | Rate limit теперь fail-closed при Redis errors; Redis всё ещё общий для broker/session/cache/locks | Redis outage блокирует auth/chat/upload limits и затрагивает остальные подсистемы | Разделить workloads или DB; alert на Redis health | Fail-closed реализовано; общий blast radius остаётся |
| Medium | Restore compatibility | Backup manifest сохраняет `alembic_version`; restore до остановки сервисов отклоняет revision, отсутствующую в текущем migration graph | Проверка известной revision не заменяет restore rehearsal | Проверять полный restore и приложение на совместимом образе | Реализовано; runtime drill не выполнен |
| Medium | Observability | Compose worker healthcheck, `make check-pilot-alerts`, ingestion duration/error-class logs, stale queue and deletion backlog checks; Prometheus/OTel отсутствуют | Нет dashboard/долгосрочных метрик; health/retention нужно проверить после запуска | Подключить централизованные метрики при production use | Частично закрыто; runtime сигналов нет |
| Medium | Task semantics | Retry ограничен transient storage/database/Redis/embedding errors; format/parser/quota failures terminal; outbox cleanup повторяем; stages всё ещё коммитятся отдельно | Ingestion полностью неатомарен; recovery после Redis потери требует dry-run и ручного apply | Сохранить ручной recovery workflow; проверять повторный ingestion при restore drill | Частично закрыто; строгая транзакционная idempotency не заявляется |
| Medium | Chat consistency | PostgreSQL advisory lock допускает один активный stream на существующую chat-сессию; retrieval и persist по-прежнему используют отдельные sessions | Одновременные turns одной сессии отклоняются `409`; ACL/corpus всё ещё могут измениться между retrieval и audit/persist; долгий stream занимает дополнительное DB connection | Сохранять corpus generation/version; наблюдать DB pool при нагрузке | Same-session overlap исправлен в source и покрыт тестами; ACL/corpus snapshot race и runtime load остаются |
| Medium | Frontend config | `API_BASE_URL` выводится из runtime env в root document | Изменение домена/конфигурации требует обновления runtime env и перезапуска frontend | Проверять runtime URL после смены окружения | Исправлено в source; runtime не проверен |
| Low | API feedback | `comment` сохраняется в `rag_audit_logs.feedback_comment`, ограничен 2000 символами и удаляется вместе с audit row | Feedback хранит свободный текст до 90 дней по умолчанию | Сохранять описание хранения и доступ к audit ограниченным | Исправлено в коде и документации |
| Low | Health semantics | `make health` обращается к liveness `/health`, не readiness `/ready` | Скрипт может сообщить успех при недоступных dependencies | Добавить отдельную цель `ready`; в ops использовать только `/ready` | Подтверждено |
| Low | Storage consistency | API atomically deletes relational rows and inserts a `storage_deletions` outbox row; Beat retries idempotent MinIO cleanup | Object cleanup is eventual; outage leaves a private object until the worker recovers | Monitor backlog and run `make reconcile-minio` periodically | Исправлено в source; runtime не проверен |
| Low | Dependency reproducibility | Backend requirements имеют lock с exact installed Python 3.12 package versions; setup использует lock | Lock отражает поддерживаемый Linux/Python environment и требует обновления вместе с requirements | Проверять clean venv на change dependency | Исправлено; clean install не выполнялся |
| Low | Error taxonomy | AppError, HTTPException, request validation, CSRF and unhandled errors share `{ "error": { "code", "message", "details?" } }` | SSE errors after stream headers retain event-stream format | Keep frontend parser compatible during rollout | Исправлено в source; runtime не проверен |

## Приоритет remediation

1. Обновить и проверить Compose на VM: migration job, RLS role, loopback/private ports, worker/Beat health.
2. Провести backup/restore drill в отдельном окружении; отработать requeue и MinIO deletion outbox.
3. Подтвердить в runtime API URL, error envelope, audit retention и alert checks.
4. Реализовать реальный SAML/OIDC provider только если Docwise будет заявлять enterprise SSO.
5. При росте окружения добавить централизованные метрики и определить RPO/RTO.

## Что требует дополнительной проверки

- реальные network policies, TLS и firewall вне репозитория;
- фактически активная DB role и grants после запуска migration job;
- внешнее расписание backup и runtime health Celery Beat retention;
- Sentry project settings и server-side scrubbing;
- provider-side LLM retention и data processing terms;
- фактические RPO/RTO и нагрузочные пределы.
