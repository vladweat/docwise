# Документация Docwise

Код, миграции и тесты имеют приоритет над описанием. OpenAPI доступен на `/docs` только
при `ENVIRONMENT != production`. Ручной HTTP-контракт поддерживается в
[engineering/api.md](engineering/api.md).

Внутренние roadmap, production runbooks и заметки находятся в gitignored `docs/_private/`;
см. [PRIVATE.md](PRIVATE.md). Их отсутствие в clone не означает, что публичный Compose
является готовой production-конфигурацией.

## Быстрый маршрут

1. [Локальная разработка](development/getting-started.md) и
   [конфигурация](development/configuration.md).
2. [Архитектура](product/architecture.md), [tenancy](platform/tenancy.md) и
   [модель данных](platform/data-model.md).
3. [Ingestion](pipeline/ingestion.md) и [retrieval](pipeline/retrieval.md).
4. [API](engineering/api.md), [auth](platform/auth.md) и [security](security/overview.md).
5. [Эксплуатация](operations/operations.md), [публичное демо](operations/public-demo.md),
   [обзор проблемных мест](maintenance/repository-review-2026-10-29.md)
   и [технический долг](maintenance/technical-debt.md).

## Каталог

| Раздел | Содержание |
| --- | --- |
| `product/` | SRS, архитектура, NFR, frontend и evaluation |
| `platform/` | Tenancy, auth, billing, data model и retention |
| `pipeline/` | Ingestion и hybrid retrieval |
| `engineering/` | HTTP contract, ADR и Python conventions |
| `development/` | Запуск, тестирование и environment variables |
| `operations/` | Compose deployment, [публичное демо](operations/public-demo.md), health, backup/restore и troubleshooting |
| `security/` | Trust boundaries, auth и подтверждённые ограничения |
| `maintenance/` | [Обзор проблемных мест](maintenance/repository-review-2026-10-29.md), risk register и [аудит документации](maintenance/documentation-audit.md) |
| `portfolio/screenshots/` | Артефакты для корневого README |

Ключевые инварианты: tenant isolation по `organization_id`, SQL ACL до LLM и
cite-or-refuse. RLS является дополнительным слоем только при корректной non-superuser
runtime role; подробнее в [security/overview.md](security/overview.md).
