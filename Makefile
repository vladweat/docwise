.PHONY: venv deps deps-frontend up up-fast up-frontend down build logs logs-frontend test lint health migrate

# Шаг 1 (нужен интернет): скачать зависимости backend + frontend
deps: venv deps-frontend

venv:
	bash backend/scripts/prepare-venv.sh

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

# pytest ходит в docwise_test, не в рабочую БД
test:
	docker compose exec backend python -m pytest tests/ -v --cov-report=term-missing

lint:
	docker compose exec backend python -m flake8 app tests scripts

migrate:
	docker compose exec backend python -m alembic upgrade head

health:
	curl -s http://localhost:8001/health | python3 -m json.tool
