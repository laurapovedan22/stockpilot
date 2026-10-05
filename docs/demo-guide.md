# Demo guide (3–5 minutes)

First execute `make demo` or the Windows task equivalent and verify readiness.

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

Browser evidence: `make e2e` writes actual desktop/mobile dashboard and scenario PNGs
in `frontend/test-results`. Review them and browser console failures before placing
a screenshot in README. Saved captures are available in `docs/evidence`.

If readiness fails, inspect `docker compose logs migrate api worker`. If training
fails, inspect `/api/v1/jobs/{id}?dataset_id=...`. Do not hide a failed comparison or
replace it with a static favorable result.
