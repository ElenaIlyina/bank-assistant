.PHONY: install infra migrate api lint test

install:
	uv sync --frozen

infra:
	docker compose -p mortgage-assistant up -d --wait

migrate:
	uv run python -m app.core.migrate

api:
	uv run uvicorn app.main:app --reload --port 8000

lint:
	uv run ruff check .

test:
	uv run pytest -q

worker:
	uv run python -m app.temporal_worker
