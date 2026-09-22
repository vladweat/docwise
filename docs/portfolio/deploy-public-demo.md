# Публичный read-only demo (C1)

Один VPS, тот же Docker Compose, что локально. Не прод с живым биллингом: `BILLING_PROVIDER=dev`, `SSO_PROVIDER=dev`.

После деплоя обновите URL в [README.md](../../README.md) (блок Live demo) и прогоните smoke ниже.

## Цели и ограничения

- Pre-seeded org **Demo** (`make demo`): employee / HR / admin, 12 синтетических PDF.
- Посетитель входит через **demo-кнопки** (`NEXT_PUBLIC_SHOW_DEMO_LOGINS=true`); регистрация новых org в UI отключена.
- Chat требует LLM key на сервере; заложи rate limit и квоты starter org.
- `/inspect` на публичном стенде **выключен** (`ENABLE_SEARCH_INSPECT` не `true` в production).

## 1. Сервер

- Ubuntu 22.04+ (или аналог), 4 GB RAM минимум (эмбеддинги в worker).
- Открыты 80/443; Postgres/Redis/MinIO **не** публиковать наружу — только через reverse proxy к frontend/backend.

## 2. TLS и прокси

Пример схемы:

```text
Internet → Caddy/Traefik (TLS) → frontend :3001
                              → backend  :8001 (/api/v1)
```

- Выдай сертификат Let's Encrypt на `demo.yourdomain.com`.
- Проксируй WebSocket/SSE для `POST /api/v1/chat/stream` без буферизации.

## 3. Env (production demo profile)

Скопируй `.env` с сервера из `.env.example` и задай минимум:

| Переменная | Значение для публичного demo |
| --- | --- |
| `ENVIRONMENT` | `production` |
| `SECRET_KEY` | длинный случайный |
| `POSTGRES_PASSWORD`, `MINIO_ROOT_PASSWORD`, `S3_SECRET_KEY` | уникальные сильные |
| `OPENAI_API_KEY` | ключ с лимитом расхода у провайдера |
| `BILLING_PROVIDER` | `dev` |
| `SSO_PROVIDER` | `dev` |
| `FRONTEND_URL` | `https://demo.yourdomain.com` |
| `CORS_ORIGINS` | `https://demo.yourdomain.com` |
| `COOKIE_SECURE` | `true` |
| `COOKIE_SAMESITE` | `none` (cross-site API на поддомене) или `lax` если фронт и API на одном хосте |
| `ENABLE_SEARCH_INSPECT` | не задавать или `false` |
| `RATE_LIMIT_CHAT_PER_MINUTE` | `10`–`20` (ниже дефолта при абьюзе) |
| `RATE_LIMIT_AUTH_PER_MINUTE` | `10` |
| `RATE_LIMIT_UPLOAD_PER_MINUTE` | `5` или отключить upload в UI политикой «demo read-only» (upload всё ещё возможен API — не давай admin пароль публично) |

**Frontend build-time** (в `docker-compose` для сервиса `frontend`):

| Переменная | Значение |
| --- | --- |
| `NEXT_PUBLIC_SHOW_DEMO_LOGINS` | `true` |

Пересобери frontend после смены `NEXT_PUBLIC_*`.

Полный список-ориентир: `.env.example` § Public demo profile.

## 4. Deploy

```bash
git clone <your-repo> && cd docwise
cp .env.example .env
# edit .env — secrets, FRONTEND_URL, CORS, keys

make deps    # на сервере или образы с предзагруженными моделями
make up
make demo    # Demo org + 12 PDF + три пользователя
```

Убедись, что OpenAPI `/docs` недоступен (`ENVIRONMENT=production`).

## 5. Smoke

| Шаг | Ожидание |
| --- | --- |
| Открыть `/login` | Три demo-кнопки; нет вкладки «Регистрация» |
| Employee: working hours | Цитата handbook |
| Employee: L3 salary | Отказ |
| HR: L3 salary | Диапазон USD + compensation PDF |
| `GET /health` | `ok` |

Не публикуй пароли admin в README — достаточно employee/HR для витрины ACL.

## 6. Disclaimer (в README Live demo)

- Synthetic documents only; no customer data.
- Demo credentials are intentional; do not upload confidential files.
- LLM answers may incur cost; rate limits apply.

## 7. Риски

| Риск | Митигация |
| --- | --- |
| LLM cost spike | Низкий `RATE_LIMIT_CHAT_PER_MINUTE`; кап токенов org; мониторинг у провайдера |
| Сканирование / боты | Rate limit auth; опционально Cloudflare |
| Новые org через API register | UI без регистрации; не раздавай публично invite/admin |
| Upload от admin demo | Не рекламируй admin login на публичном стенде |

Live Stripe и corporate IdP для этого стенда не нужны.
