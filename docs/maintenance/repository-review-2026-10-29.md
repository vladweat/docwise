# Обзор проблемных мест и технического долга

Дата: 2026-10-29. Метод: статический обзор tracked-кода и документации. Runtime-сервисы,
тесты, production-инфраструктура и внешние интеграции не запускались и не проверялись.
Рабочее дерево на момент обзора было чистым.

## Обновление remediation от 2026-10-29

После обзора в source добавлены RLS role и закрытие host ports в Compose, отдельная migration
job, checksum-проверки backup/restore, worker health/операционные сигналы, bounded retry для
transient ingestion failures, runtime `API_BASE_URL`, единый error envelope и durable MinIO
deletion outbox. Это не меняет исторические findings ниже: код не выкладывался на VM, runtime
и restore drill не проверялись. Текущий статус отражён в
[technical-debt.md](technical-debt.md).

## Кратко

Репозиторий структурирован понятно: FastAPI/Celery backend, Next.js frontend, 15 Alembic-
миграций и отдельная документация по безопасности, эксплуатации и техдолгу. В retrieval
tenant- и ACL-фильтры применяются до передачи контекста в LLM. Главные ограничения связаны
с эксплуатацией: стандартная Compose-конфигурация не включает отдельную runtime-роль для
RLS, не предназначена для внешнего production-размещения и запускает миграции из каждого
API-процесса.

## Приоритетные риски

### Высокий приоритет

1. **RLS не действует как дополнительная граница изоляции в стандартном Compose.** PostgreSQL
   запускается с `POSTGRES_USER`; `DOCWISE_RLS_SESSION_ROLE` не задана. Код включает эту роль
   только при наличии переменной, а PostgreSQL superuser обходит RLS. При этом прикладные
   фильтры tenant и ACL в retrieval присутствуют.
   Evidence: [docker-compose.yml](../../docker-compose.yml#L2),
   [rls.py](../../backend/app/core/rls.py#L14).

2. **Compose не является production-конфигурацией.** Он публикует PostgreSQL, Redis и MinIO
   без TLS и содержит credentials по умолчанию. Документация также отмечает отсутствие
   production reverse proxy, TLS automation и secret manager.
   Evidence: [docker-compose.yml](../../docker-compose.yml#L2),
   [operations.md](../operations/operations.md#L1).

3. **Rate limit доверяет входящему `X-Forwarded-For`.** Auth-лимит использует первый IP из
   этого заголовка без проверки доверенного proxy. Если API доступен напрямую или proxy не
   перезаписывает заголовок, клиент может менять адрес, по которому считается лимит.
   Evidence: [rate_limit.py](../../backend/app/core/rate_limit.py#L17).

4. **Миграции запускаются при старте каждого API-процесса.** При нескольких replicas
   возможны конкурентные Alembic upgrades. Миграции лучше вынести в одноразовую deployment
   job или сериализовать.
   Evidence: [lifespan.py](../../backend/app/core/lifespan.py#L25),
   [migrations.py](../../backend/app/core/migrations.py#L9).

### Функциональные и эксплуатационные пробелы

- **SSO работает только как dev fixture.** Login и ACS возвращают `404`, если
  `SSO_PROVIDER` отличается от `dev`; реального SAML/OIDC adapter в runtime нет.
  Evidence: [sso.py](../../backend/app/api/v1/sso.py#L75).
- **Feedback API принимает `comment`, но не сохраняет его.** Handler передаёт в persistence
  только `rating`, поэтому API-контракт расходится с реализацией.
  Evidence: [chat.py schema](../../backend/app/schemas/chat.py#L35),
  [chat.py route](../../backend/app/api/v1/chat.py#L121).
- **Автоматическое удаление audit-записей не реализовано.** Политика retention задаёт 90
  дней, но purge job отсутствует; audit содержит текст пользовательского запроса.
  Evidence: [audit.py](../../backend/app/services/retrieval/audit.py#L39),
  [data-retention.md](../platform/data-retention.md#L9).
- **Повторы ingestion требуют recovery-процедуры.** Worker автоматически повторяет любые
  `Exception`, тогда как обработка фиксирует промежуточные состояния и выполняет MinIO
  side effects несколькими шагами. Повтор может оставить несогласованные статусы или
  объекты; строгая идемпотентность не гарантирована.
  Evidence: [celery_app.py](../../backend/worker/celery_app.py#L54),
  [technical-debt.md](technical-debt.md#L17).
- **Backup/recovery не охватывает Redis.** Backup сохраняет PostgreSQL и MinIO; при
  восстановлении могут потеряться queued tasks и остаться документы в `pending` или
  `processing`.
  Evidence: [operations.md](../operations/operations.md#L77).
- **Backend-зависимости не закреплены lock-файлом.** `requirements.txt` задаёт диапазоны;
  frontend имеет `package-lock.json`, backend — нет. Установка со временем может собрать
  другой набор версий.
  Evidence: [requirements.txt](../../backend/requirements.txt#L1).

## Состояние документации и проверок

Документация в целом согласуется с кодом; известные ограничения собраны в
[реестре техдолга](technical-debt.md). Явные расхождения реализации с контрактом — feedback
comment и enterprise-возможность SSO. Реестр техдолга датирован 2026-10-12; production-
настройки, реальные backup-процедуры и внешние интеграции в этом обзоре не проверялись.

CI запускает backend lint/typecheck и pytest, а также frontend typecheck, tests, lint и
build. Supply-chain проверки помечены как advisory: их ошибки не блокируют pipeline.
Локальные тесты и сервисы во время этого обзора не запускались.

## Рекомендуемый порядок работ

1. Определить целевой режим: pilot или production.
2. Для production настроить отдельную runtime DB role/RLS, закрыть внутренние порты и
   заменить placeholder credentials.
3. Вынести миграции из старта API и определить проверяемый процесс backup/recovery.
4. Усилить обработку proxy headers и наблюдаемость worker/Redis.
5. Уточнить продуктовый статус SSO, исправить feedback contract и добавить retention job,
   если это требуется условиями хранения данных.
