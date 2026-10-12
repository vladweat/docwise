# Технический долг и риски

Дата аудита: 2026-10-12. Severity отражает потенциальный impact, а не подтверждённую
эксплуатацию уязвимости. Строки «риск» требуют runtime-проверки.

| Severity | Компонент | Наблюдение и evidence | Потенциальный impact | Рекомендация | Статус |
| --- | --- | --- | --- | --- | --- |
| High | PostgreSQL RLS | `docker-compose.yml` использует `POSTGRES_USER`; `app.core.rls` применяет role только через отсутствующую в Compose `DOCWISE_RLS_SESSION_ROLE` | Superuser обходит RLS; изоляция зависит от application filters | Создать least-privilege login/session role, задать переменную API и worker, добавить deployment smoke test cross-tenant | Подтверждённая конфигурационная слабость |
| High | Network exposure | Compose публикует `5432`, `6379`, `9000`, `9001` без TLS | Доступ к хосту/сети может открыть data services | Не публиковать внутренние порты либо ограничить firewall/private network; добавить TLS/reverse proxy | Подтверждено для Compose |
| High | Migration startup | `app.core.lifespan.lifespan` вызывает `run_migrations()` в каждом API process | Конкурирующие Alembic upgrades при scale-out | Выделить single migration job или advisory lock; запускать API после него | Потенциальный риск при нескольких replicas |
| Medium | Backup/recovery | `ops/backup-pilot.sh` сохраняет PostgreSQL и MinIO, но не Redis | Потеря queued tasks, sessions и in-flight ingestion; stuck statuses | Зафиксировать reconcile/requeue procedure и recovery acceptance test | Подтверждено |
| Medium | SSO | `app.api.v1.sso` обслуживает assertion только для `SSO_PROVIDER=dev` | Документированная enterprise capability не готова к production | Реализовать проверяемый provider adapter или маркировать SSO как fixture | Подтверждено |
| Medium | Retention | `docs/platform/data-retention.md` задаёт policy, scheduled purge в коде отсутствует | `rag_audit_logs.query` может храниться дольше policy | Добавить purge job, audit metrics и legal hold process | Подтверждено |
| Medium | Redis availability | `app.core.rate_limit.enforce_rate_limit` работает fail-open; один Redis используется несколькими подсистемами | Abuse limits исчезают; broker/session/cache имеют общий blast radius | Разделить workloads/DB или instances; alert на Redis errors; внешний edge limit | Подтверждено |
| Medium | Restore compatibility | `ops/restore-pilot.sh` не проверяет revision dump относительно кода; backend затем запускает migrations | Неожиданная несовместимость schema/code | Сохранять image/git revision с backup и проверять restore до rollout | Подтвержденный пробел процедуры |
| Medium | Observability | Есть JSON logs, Sentry и SQL audit, но нет Prometheus/OTel и worker healthcheck | Медленное обнаружение деградации и зависших jobs | Добавить metrics для queue age, ingestion duration/failures, retrieval latency и cache | Подтверждено |
| Medium | Task semantics | `worker.celery_app.process_document_task` retry для `Exception`, обработка имеет несколько DB commits и MinIO side effects | Повторы могут оставлять промежуточные статусы/objects | Классифицировать retryable errors; добавить recovery tests и явный idempotency contract | Подтверждённый риск, не доказанный defect |
| Medium | Chat consistency | `app.services.chat.sse.iter_sse_events` использует отдельные sessions для retrieval и persist | ACL/corpus могут измениться между retrieval и сохранением audit | Документировать snapshot semantics или сохранять corpus generation/version | Потенциальный race |
| Medium | Frontend config | `NEXT_PUBLIC_API_URL` встраивается `frontend/Dockerfile` во время build | Runtime смена endpoint без rebuild не действует | Сделать deployment-specific image build либо runtime config endpoint | Подтверждено |
| Low | API feedback | `ChatFeedbackRequest.comment` принимается, но handler сохраняет только `rating` | Клиент считает comment сохранённым, хотя данные теряются | Удалить поле или добавить schema/column и retention policy | Подтвержденный contract defect |
| Low | Health semantics | `make health` обращается к liveness `/health`, не readiness `/ready` | Скрипт может сообщить успех при недоступных dependencies | Добавить отдельную цель `ready`; в ops использовать только `/ready` | Подтверждено |
| Low | Storage consistency | Delete фиксирует PostgreSQL до удаления MinIO; cleanup ручной через reconcile | Orphan objects расходуют storage | Периодический reconcile с dry-run/alert и backup перед delete | Известный trade-off |
| Low | Dependency reproducibility | Backend использует version ranges без lock file | Повторная установка может получить иной patch/minor набор | Ввести проверяемый lock/constraints workflow | Подтверждено |
| Low | Error taxonomy | Routes смешивают `AppError` и FastAPI `HTTPException` | Непоследовательные error codes/telemetry | Определить единый error catalog без изменения внешнего контракта | Подтверждено |

## Приоритет remediation

1. Подтвердить production DB role/RLS и закрыть внутренние порты.
2. Отделить migrations от API startup и проверить backup/restore с revision metadata.
3. Реализовать retention job и операционную видимость worker/Redis.
4. Уточнить продуктовый статус SSO и исправить feedback contract.
5. Повысить reproducibility dependency installation и формализовать error catalog.

## Что требует дополнительной проверки

- реальные network policies, TLS и firewall вне репозитория;
- используемая production DB role и grants;
- внешнее расписание backup/retention;
- Sentry project settings и server-side scrubbing;
- provider-side LLM retention и data processing terms;
- фактические RPO/RTO и нагрузочные пределы.
