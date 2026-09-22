.PHONY: venv embeddings deps deps-frontend up up-fast up-frontend down build logs logs-frontend restart-worker demo-fresh demo-fresh-volumes test test-quick test-smoke test-frontend lint typecheck health migrate eval eval-retrieval demo

# Шаг 1 (нужен интернет): скачать зависимости backend + frontend
deps: venv embeddings deps-frontend

venv:
	bash backend/scripts/prepare-venv.sh

embeddings:
	backend/.venv/bin/python backend/scripts/prepare_embeddings.py

deps-frontend:
	bash frontend/scripts/prepare-deps.sh

# Шаг 2 (offline): собрать и запустить контейнеры
up:
	docker compose up -d --build

# Запуск без пересборки образов (если диск тесный)
up-fast:
	docker compose up -d

# Пересобрать и перезапустить только frontend (после изменений UI)
up-frontend:
	docker compose build frontend && docker compose up -d frontend

build:
	docker compose build --no-cache

down:
	docker compose down

# После правок ingestion/Celery (worker без uvicorn --reload)
restart-worker:
	docker compose restart celery-worker

# Миграции + повторный seed Demo org (тома Postgres/MinIO не трогаем)
demo-fresh: migrate demo

# Удаляет postgres_data и minio_data, поднимает стек, migrate, demo — только для локалки
demo-fresh-volumes:
	docker compose down -v
	$(MAKE) up-fast
	$(MAKE) migrate
	$(MAKE) demo

logs:
	docker compose logs -f backend frontend

logs-frontend:
	docker compose logs -f frontend

# pytest ходит в docwise_test, не в рабочую БД. Без лишних coverage-гейтов.
# -u: line-buffered stdout (видно прогресс сразу). test-quick: короче лог + top slow tests.
test:
	docker compose exec -T backend python -u -m pytest tests/ -v

test-quick:
	docker compose exec -T backend python -u -m pytest tests/ -q --durations=15

# ~3 min: parsers, layout, auth cookies, rate limit, golden JSON — no full ingest/chat/retrieval matrix
test-smoke:
	docker compose exec -T backend python -u -m pytest \
		tests/test_layout.py tests/test_text.py tests/test_logging.py tests/test_proxy.py \
		tests/test_auth_cookies.py tests/test_rate_limit.py tests/test_health.py \
		tests/test_redis_lock.py tests/test_sentry.py tests/test_billing_port.py \
		tests/test_eval_golden_dataset.py tests/test_chunker.py tests/test_pdf_parser.py \
		-q --tb=line

lint:
	cd backend && .venv/bin/ruff check app tests scripts worker
	cd backend && .venv/bin/mypy app worker

typecheck:
	cd frontend && npx tsc --noEmit

test-frontend:
	cd frontend && npm test

migrate:
	docker compose exec backend python -m alembic upgrade head

health:
	curl -s http://localhost:8001/health | python3 -m json.tool

# Live RAG eval (not default CI): LLM key + fixture PDFs. Writes reports/rag_benchmark.md
eval:
	docker compose exec -e PYTHONPATH=/app backend python /eval/run_eval.py --seed

eval-retrieval:
	docker compose exec -e PYTHONPATH=/app backend python /eval/run_eval.py --seed --retrieval-only

# Local demo: employee vs HR + six PDFs (all / hr / finance)
demo:
	docker compose exec -e PYTHONPATH=/app backend python /eval/seed_demo.py
