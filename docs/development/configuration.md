# Конфигурация

Backend читает environment variables через `app.core.config.Settings`. Файл `.env` загружается
Pydantic Settings и Compose; переменные в `docker-compose.yml` могут переопределять его.
Не коммитьте `.env` и реальные ключи. Безопасный перечень-заготовка — `.env.example`.

## Runtime и данные

| Переменная | Default в `Settings` | Назначение |
| --- | --- | --- |
| `ENVIRONMENT` | `development` | Управляет production guard и доступностью OpenAPI/inspect |
| `LOG_LEVEL` | `INFO` | Уровень JSON-логов backend |
| `DATABASE_URL` | локальный PostgreSQL URL | SQLAlchemy connection URL; Compose задаёт hostname `postgres` |
| `DB_POOL_SIZE` | `10` | Размер основного connection pool |
| `DB_MAX_OVERFLOW` | `20` | Дополнительные соединения pool |
| `REDIS_URL` | `redis://localhost:6379/0` | Refresh sessions, rate limits, cache и locks |
| `CELERY_BROKER_URL` | `redis://redis:6379/0` | Broker Celery |
| `CELERY_RESULT_BACKEND` | `redis://redis:6379/0` | Result backend Celery |
| `S3_ENDPOINT` | `http://localhost:9000` | MinIO/S3 endpoint |
| `S3_REGION` | `us-east-1` | S3 signing region |
| `S3_BUCKET_POLICY_SUPPORTED` | `true` | Whether readiness enforces private-bucket S3 policy checks |
| `S3_ACCESS_KEY` | `docwise` | S3 access key; секрет в production |
| `S3_SECRET_KEY` | placeholder | S3 secret; обязательно заменить |
| `S3_BUCKET` | `documents` | Закрытый bucket оригиналов |
| `EMBEDDING_MODEL_PATH` | пусто | Каталог ONNX-моделей; Compose задаёт `/app/.models` |

`POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`, `MINIO_ROOT_USER` и
`MINIO_ROOT_PASSWORD` читаются Compose-сервисами, а не `Settings`. Значения по умолчанию в
Compose предназначены только для локальной среды.

`DOCWISE_RLS_SESSION_ROLE` читается напрямую в `app.core.rls`, поэтому не входит в `Settings`.
Base и public-demo Compose передают `docwise_rls` API, worker и Beat. Одноразовый `db-migrate`
создаёт/проверяет роль и grants перед запуском этих процессов. Вне поддерживаемых Compose
профилей оператор должен настроить эту роль и проверить `SET LOCAL ROLE` сам.

Не подключайте runtime как PostgreSQL superuser без этой переменной: superuser всегда обходит RLS.
Подробнее: [tenancy.md](../platform/tenancy.md#postgresql-rls).

## Auth, cookies и tenancy

| Переменная | Default | Назначение и требования |
| --- | --- | --- |
| `SECRET_KEY` | небезопасный placeholder | Подпись JWT; production startup откажется работать с default |
| `ALGORITHM` | `HS256` | JWT algorithm |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `15` | TTL access token |
| `REFRESH_TOKEN_EXPIRE_MINUTES` | `10080` | TTL refresh token, 7 суток |
| `GOOGLE_CLIENT_ID` | пусто | Проверка Google ID token |
| `COOKIE_SAMESITE` | `none` | Атрибут SameSite для `dw_access`/`dw_refresh` |
| `COOKIE_SECURE` | `true` | Secure cookies |
| `CORS_ORIGINS` | localhost origins | Список разрешённых origins через запятую |
| `FRONTEND_URL` | пусто | Публичный frontend URL; иначе первый CORS origin |
| `PLATFORM_HOST_SUFFIXES` | `localhost,docwise.app` | Разрешённые suffix для tenant hostnames |
| `SSO_PROVIDER` | `dev` | Только fixture `dev`; production SAML/OIDC adapter отсутствует |
| `SSO_FRESH_TTL_SECONDS` | `900` | TTL признака свежего SSO в Redis |

Production SAML/OIDC adapter в коде отсутствует: любое значение `SSO_PROVIDER`, отличное от
`dev`, не подключает внешний IdP и публичные SSO routes возвращают `404`. Публичный demo
явно отключает fixture.

## Upload, retrieval и LLM

| Переменная | Default | Назначение |
| --- | --- | --- |
| `UPLOAD_MAX_BYTES` | `52428800` | Максимальный размер PDF/DOCX, 50 MiB |
| `RATE_LIMIT_UPLOAD_PER_MINUTE` | `10` | Upload limit на user ID |
| `RATE_LIMIT_CHAT_PER_MINUTE` | `30` | Chat limit на user ID |
| `RATE_LIMIT_AUTH_PER_MINUTE` | `20` | Login/register/google limit на IP |
| `RATE_LIMIT_TRUST_X_FORWARDED_FOR` | `false` | Использовать XFF только за настроенным proxy; включать лишь если API недоступен напрямую |
| `AUDIT_LOG_RETENTION_DAYS` | `90` | Срок хранения retrieval audit и feedback comments; минимум 1 день |
| `RERANK_THRESHOLD` | `0.25` | Минимальный sigmoid score reranker |
| `HNSW_ITERATIVE_SCAN` | `relaxed_order` | PostgreSQL pgvector scan mode |
| `HNSW_MAX_SCAN_TUPLES` | `20000` | Лимит HNSW iterative scan |
| `OPENAI_API_KEY` | пусто | Секрет OpenAI-compatible API |
| `OPENAI_BASE_URL` | пусто | Опциональный base URL совместимого gateway |
| `OPENAI_MODEL` | пусто | Опциональное имя модели |
| `ENABLE_SEARCH_INSPECT` | вычисляется | Если не задано: включено не в production, выключено в production |

Клиент в `app.services.chat.llm` использует OpenAI-compatible HTTP. Отдельного Anthropic
adapter нет. При настроенном лимите недоступность Redis возвращает HTTP 503: ограничение не
пропускает запрос fail-open. `X-Forwarded-For` игнорируется, пока явно не включён
`RATE_LIMIT_TRUST_X_FORWARDED_FOR`; public demo включает его только при закрытом порте API и
единственном публичном ingress через Caddy. Caddy по умолчанию очищает входящие значения
X-Forwarded-* от недоверенного клиента.

Backend зависимости устанавливаются из `backend/requirements.lock`. Чтобы обновить pins после
изменения `requirements.txt`, создайте временный Python 3.12 venv, установите в нём ranges из
`requirements.txt` и запишите `python -m pip freeze --all > requirements.lock`; затем проверьте
lock-файл чистой установкой. Сборочный скрипт использует только lock-файл.

## Планы и billing

| Переменная | Default |
| --- | --- |
| `PLAN_PERIOD_DAYS` | `30` |
| `PLAN_STARTER_SEATS` | `3` |
| `PLAN_STARTER_PAGES` | `200` |
| `PLAN_STARTER_TOKENS` | `100000` |
| `PLAN_TEAM_SEATS` | `15` |
| `PLAN_TEAM_PAGES` | `2000` |
| `PLAN_TEAM_TOKENS` | `1000000` |
| `PLAN_ENTERPRISE_SEATS` | `100` |
| `PLAN_ENTERPRISE_PAGES` | `20000` |
| `PLAN_ENTERPRISE_TOKENS` | `10000000` |
| `BILLING_PROVIDER` | `dev` |
| `STRIPE_SECRET_KEY` | пусто |
| `STRIPE_WEBHOOK_SECRET` | пусто |
| `STRIPE_PRICE_STARTER` | пусто |
| `STRIPE_PRICE_TEAM` | пусто |
| `STRIPE_PRICE_ENTERPRISE` | пусто |

Stripe считается настроенным только при наличии secret key и webhook secret. Price IDs
нужны для соответствующих планов. Значения — секреты или provider identifiers; в примерах
используйте placeholders.

## Наблюдаемость и frontend

| Переменная | Default | Назначение |
| --- | --- | --- |
| `SENTRY_DSN` | пусто | Включает Sentry SDK; без DSN интеграция no-op |
| `API_BASE_URL` | `http://localhost:8001` в Compose | Runtime API origin, передаётся frontend server при старте контейнера |
| `NEXT_PUBLIC_GOOGLE_CLIENT_ID` | пусто | Публичный Google client ID, встраивается при build |
| `NEXT_PUBLIC_SHOW_DEMO_LOGINS` | не задано | Явно показывает demo login; localhost показывается автоматически |

`HTTP_PROXY`, `HTTPS_PROXY`, их lowercase-варианты и `NO_PROXY` передаются Compose в backend
и worker. Внутренние hostnames `postgres`, `redis`, `minio` должны оставаться в `NO_PROXY`.

## Eval-only переменные

Compose задаёт backend:

- `EVAL_DIR=/eval`;
- `EVAL_DATASET=/eval/golden_dataset.json`;
- `EVAL_REPORT=/reports/rag_benchmark.md`;
- `HF_HUB_OFFLINE=1`, `TRANSFORMERS_OFFLINE=1`;
- `LD_LIBRARY_PATH=/usr/local/lib`.

Первые три используются eval tooling, а не `Settings`. Offline flags запрещают runtime
загрузку моделей из Hugging Face.

## Профили среды

- **Local/Compose:** `BILLING_PROVIDER=dev`, `SSO_PROVIDER=dev`, inspect включён, host ports
  привязаны к loopback, backend работает с `--reload`.
- **Test/CI:** PostgreSQL и Redis services, отдельная `docwise_test`, MinIO не поднимается,
  LLM key пуст, внешние вызовы замоканы или исключены.
- **Public demo:** `ENVIRONMENT=production`, RLS session role и отдельный migration job; TLS и
  закрытые внутренние ports добавляет `docker-compose.public-demo.yml`. `SSO_PROVIDER=disabled`,
  `BILLING_PROVIDER=dev`, storage — одноузловой Garage.
- **Other production:** OpenAPI и inspect по умолчанию выключены; default `SECRET_KEY` блокирует
  startup. Compose запускает миграции отдельно и использует non-superuser RLS session role;
  нужно отдельно обеспечить TLS, secrets, backup/recovery, network policy, monitoring и настоящий
  identity/payment provider, если это требуется продукту.
