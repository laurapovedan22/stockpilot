# StockPilot: from a forecast to a purchase proposal

Personal project by Laura Poveda Nicolás.

A small retailer needs more than a forecast chart. Stock, supplier lead times,
incoming deliveries, minimum orders and cash constraints all affect what can be
bought. StockPilot brings these inputs into one planning flow and keeps the
calculation behind each recommendation visible.

## The planning flow

Sales imports are validated before they enter the daily series. Forecast evaluation
compares two simple baselines with XGBoost using time-based splits. The chosen model
feeds an inventory policy, and the scenario lab compares how three policies behave
under the same demand paths.

An immutable stock snapshot and a versioned forecast sit behind every purchase plan.
The user can inspect the target, stock position and pack rounding, then record a
decision or export a CSV. The assistant reads saved facts and fictional policies;
it cannot approve or send purchases.

## What the evaluation showed

The synthetic demo contains 20 products and 730 complete days. With seed 42,
validation selected XGBoost at 27.86% WAPE, compared with 35.45% for seasonal naive
and 33.04% for the moving average. Final test WAPE was 27.53%, MAE was 5.70 and the
empirical 90% intervals covered 88.57% of observations.

The UCI experiment produced a different result. Moving average won validation;
final WAPE was 87.56% and MAE was 78.95. Error remained substantial on these volatile
sales. This result gives the baseline comparison a practical role: a more complex
model should earn its place through evaluation.

In the historical policy backtest, fill rates were 18.00% without purchases,
77.53% with the deterministic moving-average policy and 86.95% with the selected
policy using empirical uncertainty. The latter also bought more: £183,180 versus
£111,465. Better simulated service came with higher purchasing, so these results
cannot be described as net savings.

The [forecast manifests](evidence/) and [backtest record](evidence/historical-backtest.json)
include the evaluation windows and assumptions. The inventory, suppliers and
acquisition costs in this historical experiment are simulated, not reconstructed
business records.

## Engineering choices

- A modular backend and PostgreSQL worker keep deployment manageable while allowing
  imports, training and simulations to run independently of HTTP requests.
- Snapshots and append-only decisions preserve the inputs behind past proposals.
- Temporal validation keeps future observations out of model selection and calibration.
- Shared demand paths make policy comparisons more useful than independent random runs.
- An offline assistant keeps the core demo usable without paid services.

Local checks passed 49 backend tests, 3 frontend tests and 6 browser tests across
desktop and mobile. A separate source installation reproduced the demo with fresh
volumes. These checks cover the prototype's main flow; public hosting needs its own
security configuration and review.

## What would need to change for real use

Historical sales do not reveal demand lost during stockouts. Actual supplier and
stock data would be needed to evaluate operating benefit. Volatile and intermittent
demand also deserves better treatment than this initial global model provides.
The current policies assume one warehouse, fixed suppliers and lost sales rather
than backorders. These assumptions are deliberate limits of this version.
