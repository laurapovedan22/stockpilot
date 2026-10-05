from datetime import timedelta
from decimal import Decimal

import numpy as np
from sqlalchemy.orm import Session

from stockpilot.api.errors import AppError
from stockpilot.api.schemas import ScenarioInput
from stockpilot.db.models import (
    ForecastRun,
    RecommendationRun,
    ScenarioDaily,
    ScenarioRun,
    Snapshot,
    utcnow,
)
from stockpilot.db.repositories import get, scoped
from stockpilot.domain.inventory.simulation import simulate
from stockpilot.services.recommendations import operational_items


def create_scenario(session: Session, dataset_id: str, inputs: dict, owner_hash: str | None) -> str:
    params = ScenarioInput.model_validate(inputs)
    base = scoped(session, RecommendationRun, params.base_run_id, dataset_id)
    forecast = get(session, ForecastRun, base.forecast_run_id)
    snapshot = get(session, Snapshot, base.snapshot_id)
    items = operational_items(session, forecast, snapshot)
    if not items or any(item["paths"] is None for item in items):
        raise AppError(
            400, "NO_CALIBRATION", "A forecast with validation trajectories is required to simulate"
        )
    rng = np.random.default_rng(params.seed)
    for item in items:
        indices = rng.integers(0, len(item["paths"]), 200)
        item["paths"] = item["paths"][indices]
    results = simulate(
        items,
        params.demand_multiplier,
        params.lead_time_delay_days,
        params.horizon_days,
        params.service_level,
        Decimal(str(params.budget)) if params.budget is not None else None,
    )
    run = ScenarioRun(
        base_run_id=base.id,
        name=params.name,
        inputs=inputs,
        results={
            "policies": {
                key: {"metrics": value["metrics"]} for key, value in results["policies"].items()
            },
            "assumptions": results["assumptions"],
            "trajectory_count": results["trajectory_count"],
        },
        owner_hash=owner_hash,
        expires_at=utcnow() + timedelta(hours=24) if owner_hash else None,
    )
    session.add(run)
    session.flush()
    for policy, value in results["policies"].items():
        for row in value["daily"]:
            session.add(
                ScenarioDaily(
                    scenario_id=run.id,
                    policy=policy,
                    product_id=row["product_id"],
                    day=forecast.cutoff_date + timedelta(days=row["day"]),
                    values=row,
                )
            )
    return run.id
