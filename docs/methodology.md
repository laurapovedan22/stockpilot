# Methodology

## Target and selection

The target is positive units sold per product and complete local day. Returns and
non-positive prices are excluded from positive demand, but transaction audit rows
remain. Reindex only from the first positive-demand day to the dataset's complete cutoff.
Zero filling expresses an assumption of no recorded sales; it does not prove no demand.
Naive ISO timestamps use dataset timezone; offset timestamps convert to local dates.
Unconfirmed last days remain in source transactions and are excluded from aggregation.

Product selection requires at least 365 series days and 90 positive days before
cutoff minus 112 days. Rank by preselection units, break ties by SKU, retain at most
20. Selection is computed before validation and frozen through evaluation. Every
forecast query clips source series at its cutoff. Synthetic product identity exists
in the generator independently of later performance.

## Forecasting and evaluation

Seasonal naïve repeats the last available seven days. Moving average uses the last
28 available days. Global XGBoost receives fold-fitted one-hot product encoding,
weekday/month/weekend/time trend, lags 1/7/14/28 and mean/std windows 7/28/56.
History ends at t−1; recursion appends predictions, never observed future demand.

Reserve final 28 complete days as test. Three earlier 28-day windows use expanding
training with at least 365 days. Candidate training needs at least 477 total days
per selected product for the complete schedule; otherwise baselines are compared
on available folds. With no valid fold, choose the moving-average fallback explicitly.
Select global model on aggregate validation WAPE and MAE tie-break; evaluate the
selected model on test and retrain operationally on all permitted data. Separate
evaluation and operation pipelines are written when XGBoost is selected.

MAE and RMSE use all evaluated product/day observations. WAPE is total absolute
error divided by total actual units, not the average SKU percentage. Bias is signed
total forecast error divided by actual units. Zero denominator returns null and a
reason. No accuracy or real business savings are reported.

## Empirical uncertainty

Signed residuals from validation are retained as 28-day sequences per product.
Daily intervals use product residuals when at least ten sequences are available,
and pooled validation residual sequences across products otherwise. The run records
this scope and its calibration sample count. Daily 5th/95th quantiles are by horizon; horizons beyond 28 repeat
those calibration positions. Apply a documented central envelope and floor lower at
zero. Coverage is calculated on the **final enveloped interval** on the test set.
Pooling increases sample size but mixes product error scales. Estimates remain
empirical and coarse. No conformal/service guarantee is claimed.

Sample overlapping consecutive seven-day blocks of validation residuals with a fixed
seed to construct 200 non-negative demand trajectories. Weekly intervals sum each
trajectory first, then take quantiles. With insufficient residuals, intervals/risk
are unavailable, purchase target uses a declared 15% deterministic buffer and scenario
execution is rejected. Cross-product error dependence is not jointly modelled.

## Purchasing policy

Protection P = lead L + review R. Require a forecast covering P and reject insufficient
horizons. Available A = on-hand − reserved. Eligible inbound I arrives within P.
Target is the service quantile of cumulative trajectory demand. Position = A + I.
Raw = max(0, ceil(target − position)). Positive requests round max(raw, MOQ) up to
the SKU pack; zero raw stays zero. Line cost uses Decimal.

Contract example: target 100; on-hand 30; reserved 5; inbound 20. A=25, position=45,
raw=55. Pack 12, MOQ 24 → 60 units. Unit cost £2.50 → £150.00. Target 40 → zero units.
Chronological risk checks arrivals before demand and flags shortage before delivery.
Low <20%, medium 20–<50%, high ≥50% of paths with any lost demand.

Budgets allocate minimum MOQ-rounded packs first, then individual packs. Repeatedly
select affordable positive shortage reduction per cost, breaking ties by risk/SKU.
The same paths compare increments. It is a heuristic, not an optimality claim.

## Scenarios and backtests

All policies start with identical stocks, inbound and rounded demand per trajectory.
Daily order: receive due orders, review/purchase, serve min(stock,demand), record
loss and final-stock holding cost. New orders arrive on review day + lead + delay.
Delay applies to both existing and new arrivals. No backorders or negative stock.
Demand rounds half up. Pending end-of-horizon purchases stay in pipeline.

Three policies: no purchases, trailing moving-average replenishment and selected-model
replenishment. Budget applies equally per review. Service, lost units, average stock,
holding, simulated penalties, purchases, final stock and pipeline are separate.
Future scenarios report mean/P10/P90 over 200 paths; daily detail is trajectory zero,
not an average inventory path. Forecast tails beyond the available horizon hold the
last value; this extrapolation is explicitly recorded.

Historical CLI backtest retains observed sales as demand proxy and forecasts using
only data before each review. Model selection and calibration rerun at that origin.
Initial stocks and costs are a frozen simulated snapshot, not observed historical
operations. No claims of recovered historical stockouts or profit are warranted.

## Assistant

Offline intent routing calls schema-validated, allowlisted read tools with server-fixed
dataset scope. Policy retrieval uses TF-IDF over persisted heading-based chunks, a
0.08 relevance threshold and up to three references. Imported content remains data;
it cannot expand the tool allowlist. Scenarios link to visible controls for confirmation.
Optional OpenAI coordination uses the [Responses API function tools](https://developers.openai.com/api/docs/guides/function-calling),
strict argument schemas, four total read-tool calls including the initial offline
read, a configurable model and total deadline (default 20 seconds), and explicit
offline fallback. Dataset context is never a model-controlled tool parameter.
Sources are attached from actual tool results by the server. Public LLM mode is disabled.

## Results

The [case study](portfolio-case-study.md) discusses the synthetic and UCI evaluations.
Saved forecast runs, the historical policy backtest and screenshots are in
`docs/results/`. Historical inventory and operating costs are simulated.
