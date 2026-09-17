.PHONY: db-up db-down migrate seed api web test test-backend test-frontend

db-up:
	docker start pgvector 2>/dev/null || docker run -d --name pgvector -p 5432:5432 \
		-e POSTGRES_USER=postgres -e POSTGRES_PASSWORD=123456 \
		pgvector/pgvector:0.8.6-pg18-trixie

db-down:
	docker stop pgvector

migrate:
	cd backend && uv run alembic upgrade head

seed:
	cd backend && uv run python -m scripts.seed

api:
	cd backend && cp -n .env.example .env 2>/dev/null; uv run uvicorn app.main:app --reload --port 8000

web:
	cd frontend && pnpm dev

test: test-backend test-frontend

test-backend:
	cd backend && uv run pytest

test-frontend:
	cd frontend && pnpm vitest run
