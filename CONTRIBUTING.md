# Working on StockPilot

The backend and frontend are separate packages. 
Frontend components display API results rather than recomputing purchase quantities.
[Design notes](docs/design-notes.md) explain the main boundaries.

## Local setup

Install Python 3.12, uv, Node 22 and npm. Run `make setup` to install dependencies,
then `make demo` to start Docker services and prepare sample data. On Windows use
`./scripts/tasks.ps1 setup` and `./scripts/tasks.ps1 demo`.

Run `npm run dev` from `frontend` for frontend development; Vite proxies `/api` to
port 8000. Backend development uses `uv run uvicorn stockpilot.main:app --reload`
and `uv run python -m stockpilot.worker.main` in separate terminals from `backend`,
with `DATABASE_URL` pointing to a local PostgreSQL database.

Copy `.env.example` to `.env` if needed. Keep credentials, raw datasets, generated
models and local environments out of Git.

## Check a change

```sh
make lint
make typecheck
make test
cd frontend
npm run format:check
npm run build
```

Python uses Ruff formatting; frontend files use Prettier. Run
`uv run ruff format src tests migrations` from `backend`, or `npm run format` from
`frontend`. For interface changes, run `make e2e` against the prepared demo and inspect
the desktop/mobile captures in `frontend/test-results`.

PostgreSQL integration tests require a separate migrated database:

```sh
docker compose -f compose.test.yaml up -d --wait
cd backend
export DATABASE_URL='postgresql+psycopg://stockpilot:stockpilot@127.0.0.1:5433/stockpilot_test?connect_timeout=5'
export TEST_DATABASE_URL="$DATABASE_URL"
uv run --locked alembic upgrade head
uv run --locked pytest
```

On Windows, `./scripts/tasks.ps1 test-integration` starts the test database, applies
migrations and runs integration tests. `make test` skips integration tests when
`TEST_DATABASE_URL` is absent. Tests must not point at a database containing real data.


