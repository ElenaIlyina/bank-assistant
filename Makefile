.PHONY: install up down migrate test lint run

# Start infra (Postgres/pgvector + Temporal)
up:
	docker-compose up -d

down:
	docker-compose down -v

# Apply pending migrations (idempotent: re-run applies nothing)
migrate:
	uv run python -m migrations.runner "$${DATABASE_URL:-postgresql://bank:bank@localhost:5432/bank}"

install:
	uv sync

# Unit tests (no DB required)
test:
	uv run pytest -q

lint:
	uv run ruff check app migrations tests
	uv run ruff format --check app migrations tests

# Dev server
run:
	uv run uvicorn app.main:app --reload --port 8000
