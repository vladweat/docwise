# Docwise

**Enterprise RAG Workspace**  
**Репозиторий:** `docwise`  
**Тип:** B2B SaaS / внутренний корпоративный сервис умного поиска и Q&A по документам.

Production-grade Enterprise RAG: FastAPI, PostgreSQL/pgvector, Celery, Next.js. Поиск с учётом прав доступа (RBAC), гибридный retrieval с реранкингом и точные цитаты страниц PDF.

> Продуктовое ТЗ: [docs/srs.md](docs/srs.md). Реализация — **адаптация** соседнего [ChainWise](../chainwise): тот же каркас (FastAPI, Postgres, Celery, SSE, auth на куках, Next.js), другой парсер и retrieval с RBAC на pgvector. Отклонения от черновика ТЗ: [docs/decisions.md](docs/decisions.md). Карта переноса: [docs/reuse-from-chainwise.md](docs/reuse-from-chainwise.md).

## Какую проблему решаем

В компаниях копятся тысячи PDF/DOCX (регламенты, политики, NDA, отчёты, договоры).

- Поиск по ключевым словам не понимает смысл вопроса.
- Наивный RAG (нарезка по 500 символам) ломает таблицы, теряет заголовки и галлюцинирует.
- Главный риск Enterprise: **утечка прав доступа**. Стажёр не должен получать ответы из финансовых отчётов через общий AI-чат.
- Пользователь не верит модели без проверки: нужна **точная страница и абзац** в оригинале.

## Как это устроено

```
Пользователь (Next.js)
  ├─ загрузка PDF  → FastAPI → MinIO + PostgreSQL → Celery (parse → chunk → embed → pgvector)
  └─ вопрос (SSE)  → FastAPI → pgvector hybrid + RBAC → RRF → rerank → LLM stream
                     └─ Split-screen: ответ со сносками | PDF-вьюер на нужной странице
```

Подробности: [архитектура](docs/architecture.md).

## Стек

| Слой | Технологии |
| --- | --- |
| Backend | Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2 (**sync Session**, как в ChainWise) |
| Очереди | Redis 7, Celery 5 |
| Данные | PostgreSQL 15 + pgvector (`pgvector/pgvector:pg15`, dense 384d; FTS/BM25 на кандидатах) |
| Парсинг | PyMuPDF, pdfplumber |
| ML | fastembed (`bge-small-en-v1.5`, `bge-reranker-base`), LLM через OpenAI/Anthropic |
| Frontend | Next.js 15, React 19, TypeScript 5, Tailwind 4, shadcn/ui |
| Инфра | Docker Compose, MinIO, GitHub Actions |

## Документация

| Документ | Содержание |
| --- | --- |
| [docs/README.md](docs/README.md) | Оглавление |
| [docs/srs.md](docs/srs.md) | Продуктовое ТЗ (цели, FR, приёмка) |
| [docs/architecture.md](docs/architecture.md) | Обзор системы и потоки |
| [docs/decisions.md](docs/decisions.md) | ADR: ТЗ vs каркас ChainWise |
| [docs/data-model.md](docs/data-model.md) | PostgreSQL и pgvector |
| [docs/auth.md](docs/auth.md) | Сессия, роли, сборка ACL |
| [docs/ingestion.md](docs/ingestion.md) | Пайплайн обработки документов |
| [docs/retrieval.md](docs/retrieval.md) | Поиск, RBAC, генерация, SSE |
| [docs/api.md](docs/api.md) | REST + SSE |
| [docs/frontend.md](docs/frontend.md) | UI/UX |
| [docs/nfr.md](docs/nfr.md) | Безопасность, надёжность, perf |
| [docs/evaluation.md](docs/evaluation.md) | Ragas и бенчмарки |
| [docs/milestones.md](docs/milestones.md) | Этапы реализации |
| [docs/conventions.md](docs/conventions.md) | Соглашения по коду и репозиторию |
| [docs/reuse-from-chainwise.md](docs/reuse-from-chainwise.md) | Что копировать из ChainWise и чего нельзя |

Правила для агента Cursor лежат в `.cursor/rules/`. Краткий чеклист — [AGENTS.md](AGENTS.md).

## Запуск (Milestone 0)

Инфра как в ChainWise: зависимости ставятся на хосте (`make deps`), контейнеры собираются **offline** (`network: none`).

```bash
cp .env.example .env   # прокси, куки SameSite=None, секреты — как в ChainWise
make deps              # backend/.venv + frontend/node_modules
make up                # postgres 15+pgvector, redis, minio, backend, worker, frontend
make health            # GET http://localhost:8001/health
```

UI: http://localhost:3001 — регистрация и вход (куки `dw_*`).

## Структура

```
backend/          # FastAPI + Celery worker
frontend/         # Next.js 15 App Router
eval/             # golden dataset + Ragas runner (с M4)
docs/             # эта документация
reports/          # rag_benchmark.md (появляется после eval)
docker-compose.yml
```

## Позиционирование

*Production-grade Enterprise RAG system built with FastAPI, PostgreSQL/pgvector, Celery, and Next.js, featuring permission-aware retrieval, hybrid search with reranking, and exact PDF page citations.*
