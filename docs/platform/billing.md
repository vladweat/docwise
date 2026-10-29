# Планы, квоты и billing

Plan, quotas и entitlements хранятся на записи organization в PostgreSQL. Payment provider обновляет это состояние;
ни Stripe, ни plan не являются источником tenant/ACL. Связанные темы: [tenancy](tenancy.md), [auth](auth.md), [ADR-013](../engineering/decisions.md).

## Три разных ограничения

| Механизм | Для чего | HTTP |
| --- | --- | --- |
| Rate limit | Ограничить частоту запросов | `429` |
| Organization quota | Лимит по seats/pages/tokens | `402` |
| Plan entitlement | Функция не включена в plan (SSO/domain) | `403` |

Для своей организации не следует маскировать исчерпанную квоту как `404`; чужая organization не подтверждается.

## Тарифы

Значения ниже — defaults Compose; их можно переопределить environment variables.

| Возможность | Starter | Team | Enterprise |
| --- | ---: | ---: | ---: |
| Seats | 3 | 15 | 100 |
| Indexed pages | 200 | 2 000 | 20 000 |
| Chat tokens за период | 100 000 | 1 000 000 | 10 000 000 |
| SSO / custom domain | нет | нет | да |

Период token quota хранится в `current_period_start/end` и по умолчанию равен 30 дням.
Seats и pages — текущий объём; они не сбрасываются по периоду. Storage GB — soft guideline, не hard limit.

## Где проверяются квоты

- **Seats:** до приглашения/JIT membership.
- **Pages:** upload проверяет объявленное число страниц/разделов; после parsing проверяется итоговый объём.
- **Tokens:** chat проверяет квоту до retrieval и LLM.

Превышение квоты не ставит ingestion задачу и не передаёт вопрос в LLM.
Пользователь видит общее сообщение о квоте без plan details другой организации.

## Provider и demo режим

| `BILLING_PROVIDER` | Поведение |
| --- | --- |
| `dev` | Без платежей; admin меняет plan/status через UI/API |
| `stripe` | Checkout, customer portal и webhooks; нужны credentials и доступ к Stripe |

Публичное демо использует `BILLING_PROVIDER=dev` даже в `ENVIRONMENT=production`.
`/ready` показывает состояние `dev`, что является явным demo-режимом. Stripe без keys делает billing readiness degraded.

`POST /api/v1/billing/dev/simulate` работает только в `dev` и для admin текущей organization.
Он не может менять состояние чужого tenant.

## Stripe

Карта хранится у provider; приложение сохраняет customer/subscription IDs в organization row.
Webhook проверяет подпись и идемпотентность по `event.id` в `billing_events`.
Webhook не читает document corpus и не записывает chunk text.

## Запрещённые источники полномочий

- Не брать tenant/ACL из `organization_id`, `plan` или `access_roles` в client body.
- Не менять квоты на основании provider metadata, пока её связь с текущей org не проверена.
- Не использовать payment state для обхода `organization_id` или `access_roles`.
- Не включать SSO/custom domain, если у текущей org нет entitlement.
