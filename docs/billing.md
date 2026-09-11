# Планы, квоты и биллинг

Канон коммерческой оболочки после [M5](milestones.md#milestone-5--shared-tenancy-b2b-saas). Веха: [M6](milestones.md#milestone-6--commercial-saas). Решение: [ADR-013](decisions.md). Tenancy и hostname: [tenancy.md](tenancy.md). SSO: [auth.md](auth.md).

План, квоты и флаги `sso` / `custom_domain` живут в **Postgres на организации**. Провайдер оплаты только пишет эти поля. Retrieval, upload и ACL **не** ходят в Stripe и не ослабляют `organization_id` + `access_roles`.

## Квоты ≠ rate limit

| Механизм | Зачем | Код |
| --- | --- | --- |
| Rate limit (уже в M0–M2) | антиабьюз: IP / `user.id` за минуту | `429` |
| Квота организации | коммерческий лимит за период | `402` |
| Entitlement плана | фича не входит в план (SSO, custom domain) | `403` |

`404` на **свою** квоту не использовать. Чужую org по-прежнему не подтверждать (`404` как у файла вне ACL).

## Планы (v1)

Литералы: `starter` \| `team` \| `enterprise`. Числа — конфиг env (ниже — ориентир Compose). Новая org после register — `starter`.

| | Starter | Team | Enterprise |
| --- | --- | --- | --- |
| Seats (`organization_memberships`) | 3 | 15 | 100 |
| Indexed pages (`documents.total_pages`, статусы кроме `failed`) | 200 | 2 000 | 20 000 |
| Chat tokens за период (`rag_audit_logs.tokens_used`) | 100 000 | 1 000 000 | 10 000 000 |
| SSO / SAML | нет | нет | да |
| Custom domain | нет | нет | да |

Эмбеддинги не биллить отдельно: себестоимость страницы. Storage GB — мягкий ориентир, не хард-лимит v1.

Окно токенов — `organizations.current_period_start` / `current_period_end` (по умолчанию 30 дней с создания org, `PLAN_PERIOD_DAYS`). Просроченное окно сдвигается вперёд при проверке квоты. Страницы и seats — текущее состояние, не обнуляются с периодом.

### Где резать

- **Seats:** инвайт и JIT SSO, до создания membership.
- **Pages:** `POST /documents/upload`, если текущая сумма страниц уже ≥ капа → `402` без постановки Celery. После парсинга, если `total_pages` документа вытолкнул бы org за кап → `failed` + `last_error` про квоту, чанки удалить, байты в MinIO убрать (как при ошибке ingest). Не оставлять `ready` сверх капа.
- **Tokens:** `POST /chat/stream` **до** retrieval и LLM. Исчерпано → SSE `type: error` с тем же смыслом, что HTTP `402` (фиксированная фраза). Не дергать эмбеддер и не писать чужие chunk id.

Org-admin видит usage в настройках. Employee при упоре в лимит видит отказ «квота организации исчерпана», без цифр биллинга и без намёка на чужие файлы.

`organizations.status = suspended` (уже M5): вход в эту org отклоняется. Биллинг `past_due` / отмена → тот же `suspended`. Смена плана не даёт читать корпус другой org и не обходит внутреннюю ACL.

## Провайдер (`BILLING_PROVIDER`)

Один интерфейс: текущая подписка, смена плана, отмена, `past_due`. Хендлеры квот читают только строки org.

| Значение | Когда | Деньги |
| --- | --- | --- |
| `dev` (дефолт Compose и не-`production`) | локально, CI, портфолио без эквайринга | нет. Org-admin меняет план API/UI |
| `stripe` | когда есть аккаунт и сеть до `api.stripe.com` | Checkout + Customer Portal + вебхуки |

Stripe **test keys не заменяют** `dev`: они всё равно требуют аккаунт и доступ к Stripe. С РФ это часто невозможно — критерий приёмки M6 закрывается на `dev`.

Адаптер `stripe` в коде допустим, в CI живой `api.stripe.com` не обязателен. ЮKassa и прочий эквайринг — отдельный провайдер тем же портом, не M6.

`ENVIRONMENT=production` и `BILLING_PROVIDER=dev`: явный выбор (демо-VPS), `/ready` помечает billing как `dev`. `BILLING_PROVIDER=stripe` без ключей → billing в `/ready` не `ok` (`degraded`), приложение не обязано падать. Не вызывать Stripe «на всякий случай» при `dev`.

## Dev-биллинг

Экран org-admin (бейдж **Dev billing**): выбрать план, «активировать», «просрочить», «отменить». Те же переходы `plan` / `billing_status` / `status`, что дал бы вебхук.

`POST /api/v1/billing/dev/simulate` — только `BILLING_PROVIDER=dev`, только **текущая** org из сессии, только `require_admin`. Иначе `404` (как выключенный inspect). Нельзя симулировать Globex из сессии Acme.

## Stripe (не критерий M6)

Checkout + Portal. Карты не хранить. `stripe_customer_id` / `stripe_subscription_id` на org, не в JWT и не в теле чата. Вебхуки: `checkout.session.completed` (привязка по `client_reference_id`), `customer.subscription.updated|deleted`, `invoice.paid`, `invoice.payment_failed`. Org после checkout — только по Stripe id на строке org, не по `metadata.organization_id`. Подпись, идемпотентность по `event.id` в `billing_events`. Маппинг Price → план. Платит только org-admin **текущей** org. Вебхук не читает корпус и не логирует chunk text.

## Запрещено

- Клиентский `plan` / `org_id` как источник квоты или ACL.
- Кэш LLM без `org_id` (как в M5); план в ключе кэша не нужен.
- Platform-admin, который смотрит usage или корпуса всех клиентов.
- `402`/`403`, которые подтверждают существование файла или org, которой нет в сессии.
- Включать SSO или custom domain org, чей план это не содержит (даже через dev-simulate чужого тенанта — его нет в сессии).
