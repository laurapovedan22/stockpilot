# API contracts

Prefix `/api/v1`; live OpenAPI `/api/openapi.json`, local explorer `/api/docs`.
Errors: `error: {code, message, details, request_id}`. Local write guard returns 403
in `public_demo`; invalid schema 422, unavailable resource 404, version conflict 409,
invalid policy 400, oversize 413, unavailable database 503. Requests do not return
tracebacks, keys or uploaded file contents in logs.

Non-dataset-prefixed resources require `?dataset_id=UUID`. List endpoints use page≥1,
page_size≤100 (default 25); small inventory/methodology responses are bounded by the
20-product planning scope. Sales points are bounded by dataset coverage.

| Method | Path | Contract |
|---|---|---|
| GET | /health/live, /health/ready | Process / database migration 0001 |
| POST | /session | Random HttpOnly same-site demo cookie |
| GET | /datasets, /datasets/{id}/summary | Dataset catalog and persisted KPIs/latest resources |
| POST | /datasets | Local only: name, as_of_date, source, currency GBP, timezone Europe/London; creates a separate historical CSV dataset |
| GET | /datasets/{id}/products | Search, active, risk and supplier filters; pagination; active=true supplies all selected planning products |
| GET | /products/{id}, /products/{id}/sales | Dataset-scoped detail and start/end daily units |
| GET | /datasets/{id}/inventory | Latest snapshot/items/inbound |
| PATCH | /inventory/{id} | on_hand, reserved, expected_version; creates copied snapshot |
| POST | /datasets/{id}/imports/preview | multipart file/kind/mapping; token, checksum, rows/errors |
| POST | /datasets/{id}/imports/confirm | token, excluded_rows, idempotency_key, last_day_complete; 202 job |
| GET | /imports/{id} | Import counters and exclusions, no upload path |
| POST | /datasets/{id}/forecast-runs | cutoff_date, horizon≤42; 202 persistent job |
| GET | /datasets/{id}/forecast-runs, /forecast-runs/{id} | Run history, metrics and folds |
| GET | /forecast-runs/{id}/points | product_id, start/end, daily/weekly aggregation |
| POST | /datasets/{id}/recommendation-runs | forecast_run_id, snapshot_id, policy, budget |
| GET | /recommendation-runs/{id}, /recommendation-runs/{id}/items | Plan summary and paginated explanations/events |
| POST | /recommendation-items/{id}/decisions | action, optional final_units, reason, expected_version |
| GET | /recommendation-runs/{id}/export | Formula-safe CSV of latest local plan state |
| POST | /datasets/{id}/scenario-runs | base_run_id, name, multiplier .5–2, delay 0–14, horizon 7–28, budget, service, seed; 202 job |
| GET | /datasets/{id}/scenario-runs, /scenario-runs/{id} | Owner-scoped saved history/results |
| GET | /scenario-runs/{id}/daily-results | policy/product_id; paginated representative path |
| GET | /jobs/{id} | status, stage, progress, result_id and safe error |
| POST | /datasets/{id}/assistant/messages | text≤2000, session_id, context_ids≤4; tools and references |
| GET | /datasets/{id}/methodology | Source/date/rules/limitations/references |

Jobs: queued → running → succeeded/failed; lease expiry can requeue once. Import and
forecast cannot be simultaneously active for a dataset. Forecast idempotency hashes
parameters and current daily data checksum. Preview idempotency uses dataset/type/
content/mapping; same file returns its batch independently of client-generated keys.
`idempotency_key` is accepted for the confirm contract but content is authoritative.

Public scenario/result/summary/tool queries exclude expired results. Public jobs and
assistant conversations are unavailable after 24 hours, independently of cleanup.
The scenario queue admits at most two active jobs globally and three submissions
per minute/owner; the assistant admits ten messages per minute/owner across datasets.
Transaction-scoped advisory locks make these admission checks atomic. This does not
prevent someone from creating new sessions; deployment anti-abuse remains separate.

Example recommendation policy:

```json
{"forecast_run_id":"UUID","snapshot_id":"UUID","policy":{"service_level":0.95,"review_days":7},"budget":"250.00"}
```

Assistant context IDs are currently accepted but not used for offline routing; ask
with a SKU for an explanation. All LLM calculation facts are selected server-side.
Optional LLM coordination can consult only the seven read tools and attaches actual
tool references, with a four-call total cap and configurable deadline. TypeScript
interfaces are maintained in `frontend/src/types/api.ts`. Executed PostgreSQL and
browser checks cover the main contracts; broader response coverage remains before
claiming complete parity.
