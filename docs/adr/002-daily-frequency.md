# ADR 002 — Daily frequency

Decision: aggregate by dataset-local complete day; default visible forecast 28 days,
operation up to 42. Weekly displays aggregate daily trajectories before quantiles.
Reason: delivery and reviews operate by days; weekly-only series lose arrival timing.
Tradeoff: more sparse observations and explicit zero-filling/completeness assumptions.
