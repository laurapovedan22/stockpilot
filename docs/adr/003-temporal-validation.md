# ADR 003 — Temporal validation

Decision: three expanding 28-day validation folds, then a final independent 28-day
holdout. Selection uses aggregate validation WAPE, then MAE. Products freeze before
the first validation date. Insufficient coverage reduces folds and omits the candidate.
Reason: random splitting leaks future patterns and SKU-level percentage averages mislead.
Tradeoff: limited folds, coarse residual quantiles and candidate training cost.
