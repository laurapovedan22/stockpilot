# Architecture

StockPilot is a modular monolith with an independently scheduled worker. FastAPI
routers validate HTTP, services own transaction boundaries, domain modules perform
calculations and repositories scope SQLAlchemy queries. React consumes persisted API
resources; it does not calculate business replenishment quantities.

PostgreSQL contains source transactions, daily aggregates, inventory snapshots,
forecast/evaluation rows, purchase proposals, decisions, scenarios, jobs and assistant
references. Native UUID keys, relational constraints, Numeric money, JSONB metadata
and timestamps distinguish operational data from auditing.

The initial migration reads a frozen SQL schema independent of current ORM definitions.
Later schema changes require new migrations. Application startup does not create
tables or seed data; the one-shot migration service runs before API/worker.

Jobs are claimed using `FOR UPDATE SKIP LOCKED`; a 60-second renewable lease and
15-second heartbeat support reclamation, capped at two total attempts. A transaction
advisory lock serializes mutation per dataset. Ownership is fenced before completion.
Results and completion are committed together; validation failures do not retry.
Worker logs expose local exceptions; API errors expose safe messages/request IDs.

Forecast trajectories are non-pickle NPZ files in a project-controlled directory.
Own XGBoost pipelines can be written to joblib; user uploads never load artifacts.
Temporary trajectory files are atomically renamed. Failed runs can leave orphan
artifact directories, which currently require manual review/cleanup.

Inventory edits copy snapshots and pending orders. Recommendation items retain numeric
formula terms, forecast and snapshot versions. Decision events do not mutate stock.
Budget decisions serialize on the plan row, and the database rejects decision updates
and deletes.

Public demo mode blocks shared imports, edits, training and decisions in backend
dependencies. Browser cookies contain random tokens; hashes scope public scenarios,
jobs and conversations. Expiry is 24 hours, hourly worker maintenance cleans expired
results/messages and upload files. Public simulations have bounded input ranges,
two global active jobs and three submissions per session/minute. These behaviors
are covered by PostgreSQL isolation, concurrency and expiry tests. They do not
replace deployment access controls.
