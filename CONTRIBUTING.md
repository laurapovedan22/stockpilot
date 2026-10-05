# Working on StockPilot

The backend and frontend are kept as separate packages. The frontend is mainly responsible for displaying the results returned by the API, while the backend handles the calculations and business logic.
Some notes about the main design decisions and project structure are available in [Design notes](docs/design-notes.md) 

or local development, you will need Python 3.12, uv, Node 22 and npm.

Run:

make setup
make demo

make setup installs the required dependencies, while make demo starts the Docker services and prepares the sample data used by the application.

On Windows, the equivalent commands are:

./scripts/tasks.ps1 setup
./scripts/tasks.ps1 demo

For frontend development, run:

cd frontend
npm run dev

Vite proxies requests to /api to the backend running on port 8000.

For backend development, I normally run the API and the worker in separate terminals from the backend directory:

uv run uvicorn stockpilot.main:app --reload

uv run python -m stockpilot.worker.main

DATABASE_URL should point to a local PostgreSQL database.

If environment variables are needed, copy .env.example to .env. Credentials, raw datasets, generated models and local environments should not be committed to Git.

Checking changes

Before committing changes, I normally run:

make lint
make typecheck
make test

cd frontend
npm run format:check
npm run build

The Python code is formatted with Ruff, while the frontend uses Prettier.

To format the backend manually:

cd backend
uv run ruff format src tests migrations

For the frontend:

cd frontend
npm run format

When changing the interface, it is also useful to run:

make e2e

This runs the end-to-end tests against the demo environment. Desktop and mobile captures are stored in frontend/test-results, which makes it easier to check that the UI still behaves correctly.

PostgreSQL integration tests

Integration tests use a separate PostgreSQL database. It can be started with:

docker compose -f compose.test.yaml up -d --wait

cd backend

export DATABASE_URL='postgresql+psycopg://stockpilot:stockpilot@127.0.0.1:5433/stockpilot_test?connect_timeout=5'
export TEST_DATABASE_URL="$DATABASE_URL"

uv run --locked alembic upgrade head
uv run --locked pytest

On Windows, this can be done directly with:

./scripts/tasks.ps1 test-integration

This starts the test database, applies the migrations and runs the integration tests.

If TEST_DATABASE_URL is not defined, make test skips the PostgreSQL integration tests.

The test configuration should always use a dedicated test database and should never point to a database containing real data.
