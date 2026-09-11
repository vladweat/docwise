.PHONY: venv embeddings deps deps-frontend up up-fast up-frontend down build logs logs-frontend test test-frontend lint typecheck health migrate eval eval-retrieval demo

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

logs:
	docker compose logs -f backend frontend

logs-frontend:
	docker compose logs -f frontend

# pytest ходит в docwise_test, не в рабочую БД. Без coverage-гейтов ChainWise.
test:
	docker compose exec backend python -m pytest tests/ -v

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

# Local demo: employee vs HR + handbook (all) / HR compensation (hr)
demo:
	docker compose exec -e PYTHONPATH=/app backend python /eval/seed_demo.py
