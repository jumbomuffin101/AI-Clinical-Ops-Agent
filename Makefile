.PHONY: test-backend run-backend run-frontend build-frontend migrate

test-backend:
	cd apps/api && python -m pytest -q

run-backend:
	cd apps/api && uvicorn app.main:app --reload --port 8000

run-frontend:
	cd apps/web && npm run dev

build-frontend:
	cd apps/web && npm run build

migrate:
	cd apps/api && alembic upgrade head
