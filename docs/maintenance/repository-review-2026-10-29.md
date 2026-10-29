# Обзор репозитория для demo/interview

**Снимок:** 2026-10-29. Это обзор проекта и runtime на дату подготовки демо; обновляемые риски ведутся отдельно в
[техническом долге](technical-debt.md).

## Что проект демонстрирует

- FastAPI + Next.js + Celery на общем Compose deployment.
- Организационная изоляция и document ACL в SQL до передачи контекста модели.
- Hybrid retrieval: pgvector + PostgreSQL FTS, RRF, cross-encoder и citations к PDF/DOCX.
- Durable операции вокруг загрузки и удаления файлов, миграции и queue recovery.
- Evaluation на synthetic corpus с positive и ACL-negative кейсами.

## Актуальный профиль демо

Публичный URL: [docwise.wvzl.site](https://docwise.wvzl.site). Профиль использует Caddy/TLS, PostgreSQL, Redis,
Garage single-node, backend, worker и frontend. Backend/Frontend healthchecks, TLS, `/` и `/ready` были проверены.
Профиль рассчитан на синтетические данные и не является HA deployment.

## Открытые ограничения

1. Backup/restore подготовлены, но отдельный restore drill и RPO/RTO не определены.
2. Реального SAML/OIDC adapter нет; публичный SSO отключён.
3. Один Redis используется несколькими подсистемами; отказ затрагивает queue, sessions, limits, locks и cache.
4. Внешние metrics/dashboard/tracing не настроены.
5. ACL/corpus version может измениться между retrieval и audit/persist; строгий snapshot не гарантируется.

Подробные статусы, next actions и runtime evidence: [technical-debt.md](technical-debt.md).

## Достоверность результатов

Сохранённый RAG benchmark — датированный снимок на 35 eval cases, не универсальная оценка новых данных.
Последняя проверка публичного demo не повторяла полный chat flow после обновления раннего SSE session metadata.
