.PHONY: setup up migrate seed-demo demo test lint typecheck e2e fetch-retail train-retail
setup:
	cd backend && uv lock && uv sync
	cd frontend && npm install
up:
	docker compose up --build -d
migrate:
	docker compose run --rm migrate
seed-demo:
	docker compose exec api python -m stockpilot.cli seed-demo
demo: up
	docker compose exec api python -m stockpilot.cli demo
test:
	cd backend && uv run pytest
	cd frontend && npm test
lint:
	cd backend && uv run ruff check src tests migrations
	cd frontend && npm run lint
typecheck:
	cd backend && uv run mypy src
	cd frontend && npm run typecheck
e2e:
	cd frontend && npx playwright install chromium && npm run e2e
fetch-retail:
	docker compose exec api python -m stockpilot.cli fetch-retail
train-retail:
	docker compose exec api python -m stockpilot.cli train-retail
