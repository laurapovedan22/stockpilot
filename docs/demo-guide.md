# Demo walkthrough

Start with `make demo` or `./scripts/tasks.ps1 demo` on Windows.

1. Open Overview. Explain that the dataset has synthetic sales through 31 December
   2025, GBP, and simulated operations. KPI values come from persisted resources.
2. Open Products → Inspect. Distinguish on hand, reserved and available inventory;
   review observed sales against the forecast.
3. Open Forecasts. Inspect validation model comparison, selected model, final test
   metrics, temporal folds and daily/weekly intervals. A baseline may win.
4. Open Replenishment → Explain. Show target, protection period, position, raw need,
   packs/MOQ and cost. Explain that decisions create plans, not supplier orders.
5. Open Scenario lab → Supplier delay. Confirm the visible delay is four days. Run
   explicitly; wait for the real job. Compare service, losses, purchases and operating
   costs using the same demand paths. Results are projected, not actual savings.
6. Ask why DEMO-004 should be ordered. Open references and identify the saved run
   and offline tool. Finish with Methodology and download the plan CSV.

If readiness fails, inspect `docker compose logs migrate api worker`. If training
fails, inspect `/api/v1/jobs/{id}?dataset_id=...`.
