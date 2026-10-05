# StockPilot development

Read docs/methodology.md and docs/architecture.md before changing behavior.
If local docs/specification.md and docs/progress.md exist, read them too.
Python uses uv; frontend uses npm. Commands: `make setup`, `make up`,
`make migrate`, `make seed-demo`, `make demo`, `make test`, `make lint`,
`make typecheck`, `make e2e`. Windows equivalents: `./scripts/tasks.ps1 <task>`.

Keep calculations in pure domain modules, transactions in services, HTTP in routers.
Use dataset-scoped queries. Snapshot operational inputs; decisions are append-only.
Do not load user-supplied pickle/joblib. Do not commit secrets, raw UCI data or models.
Do not publish, commit or push without an instruction. Report checks actually run.
Temporal evaluation must never use future observations. Label simulated data.
Finish with tests, lint, types, build, actual UI inspection and updated progress.
