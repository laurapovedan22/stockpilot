# Design notes

## Keep the forecast close to the decision

A forecast on its own does not say how many units to buy. The calculation also needs
available stock, incoming orders, supplier lead time, review interval and packaging
constraints. StockPilot saves these terms with each proposal so the result can be
explained later, even after stock changes.

A target of 100 units, physical stock of 30, reserved stock of 5 and 20 eligible
incoming units give a position of 45. The raw need is 55. Packs of 12 and a minimum
order of 24 produce a request for 60 units, costing £150 at £2.50 each. If the target
is only 40, the request is zero; a minimum order does not create a need to buy.

Arrival dates still matter. An order due on day eight cannot cover a shortage on
day two. The chronological risk calculation checks this instead of relying only
on total incoming stock.

## Baselines belong in the product

Seasonal naive repeats the last observed week. The moving average uses the previous
28 days. Both are understandable references for XGBoost, and either can win temporal
validation. The final test window does not participate in model selection.

Recursive forecasts update lag features with earlier predictions. Using actual
future sales would give the evaluation information the operating model never has.

Uncertainty uses validation residuals and seven-day blocks to retain some temporal
dependence. Where product-specific residuals are insufficient, the fallback pools
products and mixes scales. Weekly bands come from summed trajectories, not sums of
daily interval bounds.

## Separate work from HTTP requests

Training and simulations can outlive a browser request. The API stores a job and
returns its ID; the worker claims it with a renewable lease. A lost worker can be
replaced, with a maximum of two attempts. Ownership is checked before completion so
an old worker cannot publish after another worker has reclaimed its job.

PostgreSQL provides the queue and transaction locks as well as application data.
This avoids another service to operate at the current scale. Queue behavior therefore
needs PostgreSQL integration tests rather than a SQLite substitute.

## Preserve the record

Stock edits copy the inventory snapshot. Recommendation explanations refer to their
original forecast and snapshot. Accepting a proposal creates a decision event, not a
supplier order or stock receipt. A version check catches stale screens, and a database
trigger prevents changing past decisions.

## Compare policies fairly

Each policy receives the same demand trajectory and starts with the same stock and
cost assumptions. Incoming orders arrive on their exact simulated day. Purchasing
cost stays separate from holding and lost-sales penalties because stock left at the
end still has value. The historical backtest uses observed sales as a demand proxy,
with simulated operational inputs; it cannot establish real business savings.
