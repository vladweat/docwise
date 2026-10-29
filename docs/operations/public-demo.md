# Публичное демо Docwise

Этот профиль поднимает Docwise на `docwise.wvzl.site` за Caddy с автоматическим TLS.
Базовый [`docker-compose.yml`](../../docker-compose.yml) остаётся профилем локальной
разработки. Публичный стек запускайте отдельным Compose project, чтобы его volumes и
контейнеры не смешивались с другими приложениями на VPS.

## Перед запуском

1. В REG.RU добавьте A-запись `docwise.wvzl.site` → `148.113.144.255` — тот же адрес,
   на который сейчас указывает `landlords.wvzl.site`. Убедитесь, что входящие TCP-порты
   80 и 443 разрешены firewall.
2. Создайте `.env` из `.env.example`. Задайте уникальные `SECRET_KEY`,
   `POSTGRES_PASSWORD` и `MINIO_ROOT_PASSWORD`; последнее имя оставлено для совместимости
   с базовым Compose, а public-demo передаёт эти S3 credentials в Garage. Используйте
   hex-значения для паролей, которые входят в PostgreSQL URL. Не публикуйте `.env` и не
   добавляйте его в Git.
3. Задайте `OPENAI_API_KEY` и, если нужно, `OPENAI_BASE_URL`/`OPENAI_MODEL`.
4. Подготовьте локальные build inputs. На этой VPS отсутствует `make`; вместо `make deps`
   выполните:

   ```bash
   bash backend/scripts/prepare-venv.sh
   bash frontend/scripts/prepare-deps.sh
   ```

   Backend script требует `python3.12-venv` и `libgomp1`; он скачивает Python dependencies
   и embedding/reranker models в `backend/.models`. Frontend script создаёт
   `frontend/node_modules`. На VPS есть 2 vCPU и около 3.7 GiB RAM; модельный warm-up и
   первый build могут занять время.

Существующий `landlords` production Compose profile сейчас остановлен, а портов 80/443
у активных контейнеров нет. Профиль Docwise сам займёт эти порты; одновременно запускать
отдельный Caddy из Landlords нельзя, пока оба приложения не переведены на общий ingress.

## Поднять стек

Из корня checkout:

```bash
python3 ops/public-demo/prepare-garage-config.py
docker compose -p docwise-public-demo \
  -f docker-compose.yml -f docker-compose.public-demo.yml \
  up -d --build
```

Production overlay заменяет недоступный публичный образ MinIO на Garage и убирает host
ports у PostgreSQL, Redis, S3-хранилища, API и frontend. Garage работает как одноузловое
хранилище для демонстрации без репликации; его локальный config содержит случайные
admin/RPC secrets и не попадает в Git. Приложение использует S3 API Garage и не проверяет
S3 bucket policies: Garage не поддерживает этот S3 API, а права ограничены отдельным
access key. Только
Caddy слушает 80/443. API и frontend доступны через один HTTPS origin; `/api/*`, `/health`
и `/ready` идут в FastAPI, остальные запросы — в Next.js. Caddy sanitizes incoming
`X-Forwarded-*` headers, поэтому публичный клиент не может подменить IP для auth rate limit.
Профиль включает `RATE_LIMIT_TRUST_X_FORWARDED_FOR` только потому, что backend-порт не
опубликован и единственный ingress — Caddy; Redis outage при активном лимите возвращает 503.
Регистрация закрыта на ingress;
демо-входы показаны в login UI, self-service registration скрыта. `SSO_PROVIDER=disabled`:
разработческий SSO fixture не доступен в публичной среде. Подробнее о sanitizing proxy
headers — [Caddy reverse_proxy docs](https://caddyserver.com/docs/caddyfile/directives/reverse_proxy).

Выделенный service `db-migrate` перед миграциями идемпотентно создаёт/проверяет роль
`docwise_rls` и grants; это работает и с уже созданным PostgreSQL volume. API, worker и Beat
устанавливают `SET LOCAL ROLE docwise_rls`, чтобы RLS-политики выполнялись при запросах
к corpus и maintenance tables. Compose монтирует `eval/`
read-only только для запуска demo seed script. Seeder
применяет RLS bypass только к своей SQLAlchemy-сессии, чтобы записать synthetic fixtures;
постоянная настройка API и worker остаётся с tenant RLS. API и worker ждут успешного
завершения единственного migration job перед стартом.
Один `celery-beat` service запускает audit retention раз в день в 03:15 UTC; не масштабируйте
его более чем в одну replica.

Для `ops/backup-pilot.sh`, `ops/restore-pilot.sh`, `ops/reconcile-minio.sh` и
`ops/check-pilot-alerts.sh` задайте в deployment `.env` `COMPOSE_FILE` с обоими Compose
файлами и `COMPOSE_PROJECT_NAME=docwise-public-demo`. Для S3 client scripts задайте
`MC_ENDPOINT=http://minio:3900`, `MC_ACCESS_KEY=GK<значение S3_ACCESS_KEY>` и
`MC_SECRET_KEY=<значение S3_SECRET_KEY>`. Для alert check задайте `API_URL=https://<DOCWISE_DOMAIN>`;
сами значения остаются только в `.env`.

## Засеять demo corpus

После `/ready`:

```bash
docker compose -p docwise-public-demo \
  -f docker-compose.yml -f docker-compose.public-demo.yml \
  exec backend python /eval/seed_demo.py
```

Проверить извне:

```bash
curl -fsS https://docwise.wvzl.site/ready
```

Demo accounts и пароли заданы в коде/README и видны посетителям. Corpus должен содержать
только синтетические данные. Любой посетитель может пользоваться публичными ролями; не
храните в этой базе реальные документы или сведения клиентов. Admin demo account может
загружать и удалять документы, поэтому после экспериментов проверяйте состояние corpus и
пересевайте его при необходимости.

UI и вход работают без LLM credentials, но ответы чата требуют `OPENAI_API_KEY` и
`OPENAI_MODEL`, совместимую с `chat/completions` (batch-only модели не подходят). После
изменения этих значений напрямую в игнорируемом `.env` пересоздайте backend и worker:

```bash
docker compose -p docwise-public-demo \
  -f docker-compose.yml -f docker-compose.public-demo.yml \
  up -d --build --force-recreate backend celery-worker celery-beat
```

Эта команда также применяет миграцию для feedback comments и индекса retention. Для
повторной постановки ingestion после потери Redis сначала посмотрите кандидатов в dry-run;
команда выводит только document IDs и statuses:

```bash
docker compose -p docwise-public-demo \
  -f docker-compose.yml -f docker-compose.public-demo.yml \
  exec backend python -m scripts.requeue_stale_ingestion
```

После просмотра списка повторная постановка выполняется той же командой с `--apply`.

## Управление

Все команды должны повторять пару Compose-файлов и project name:

```bash
docker compose -p docwise-public-demo -f docker-compose.yml -f docker-compose.public-demo.yml ps
docker compose -p docwise-public-demo -f docker-compose.yml -f docker-compose.public-demo.yml logs --tail=100
docker compose -p docwise-public-demo -f docker-compose.yml -f docker-compose.public-demo.yml down
```

`down` сохраняет volumes. Не используйте `down -v`, если не хотите удалить PostgreSQL,
Garage и Caddy state для публичного demo.
