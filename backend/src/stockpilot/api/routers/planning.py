import csv
import io
from datetime import date, timedelta
from decimal import Decimal
from typing import Literal

import numpy as np
from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import Response
from sqlalchemy import func, select

from stockpilot.api.dependencies import DB, local_only, session_hash
from stockpilot.api.errors import AppError
from stockpilot.api.schemas import DecisionInput, ForecastInput, RecommendationInput, ScenarioInput
from stockpilot.config import settings
from stockpilot.db.models import (
    Decision,
    EvaluationResult,
    ForecastPoint,
    ForecastRun,
    Job,
    Product,
    RecommendationItem,
    RecommendationRun,
    ScenarioDaily,
    ScenarioRun,
    utcnow,
)
from stockpilot.db.repositories import get, scoped, serialize
from stockpilot.services.access import owned_scenario
from stockpilot.services.forecasts import load_paths
from stockpilot.services.recommendations import create_recommendations, decide
from stockpilot.worker.queue import dataset_lock, enqueue

router = APIRouter()


@router.post(
    "/datasets/{dataset_id}/forecast-runs", status_code=202, dependencies=[Depends(local_only)]
)
def start_forecast(dataset_id: str, inputs: ForecastInput, db: DB):
    from stockpilot.db.models import Dataset

    dataset = get(db, Dataset, dataset_id)
    if inputs.cutoff_date and inputs.cutoff_date > dataset.as_of_date:
        raise AppError(400, "INVALID_CUTOFF", "Cutoff exceeds reference date")
    job = enqueue(db, dataset_id, "forecast", inputs.model_dump(mode="json"))
    db.commit()
    return serialize(job)


@router.get("/forecast-runs/{identifier}")
def forecast_run(identifier: str, dataset_id: str, db: DB):
    run = scoped(db, ForecastRun, identifier, dataset_id)
    return {k: v for k, v in serialize(run).items() if k != "artifact_path"} | {
        "folds": [
            serialize(fold)
            for fold in db.scalars(
                select(EvaluationResult).where(EvaluationResult.run_id == identifier)
            )
        ]
    }


@router.get("/datasets/{dataset_id}/forecast-runs")
def forecast_history(
    dataset_id: str, db: DB, page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=100)
):
    from stockpilot.db.models import Dataset

    get(db, Dataset, dataset_id)
    rows = db.scalars(
        select(ForecastRun)
        .where(ForecastRun.dataset_id == dataset_id)
        .order_by(ForecastRun.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return {
        "items": [{k: v for k, v in serialize(row).items() if k != "artifact_path"} for row in rows]
    }


@router.get("/forecast-runs/{identifier}/points")
def forecast_points(
    identifier: str,
    dataset_id: str,
    product_id: str,
    db: DB,
    start: date | None = None,
    end: date | None = None,
    frequency: Literal["daily", "weekly"] = "daily",
):
    run = scoped(db, ForecastRun, identifier, dataset_id)
    scoped(db, Product, product_id, dataset_id)
    if start and end and start > end:
        raise AppError(400, "INVALID_RANGE", "Start must precede end")
    rows = db.scalars(
        select(ForecastPoint)
        .where(ForecastPoint.run_id == identifier, ForecastPoint.product_id == product_id)
        .order_by(ForecastPoint.day)
    ).all()
    selected = [r for r in rows if (not start or r.day >= start) and (not end or r.day <= end)]
    if frequency == "daily":
        return {"items": [serialize(row) for row in selected], "cutoff_date": run.cutoff_date}
    paths = load_paths(run).get(product_id)
    buckets: dict[date, list[int]] = {}
    for index, row in enumerate(rows):
        if row not in selected:
            continue
        monday = row.day - timedelta(days=row.day.weekday())
        buckets.setdefault(monday, []).append(index)
    items = []
    for day, positions in buckets.items():
        central = sum(float(rows[i].yhat) for i in positions)
        bands = (
            np.quantile(paths[:, positions].sum(axis=1), [0.05, 0.95])
            if paths is not None
            else [None, None]
        )
        items.append(
            {
                "day": day,
                "yhat": central,
                "lower": float(bands[0]) if bands[0] is not None else None,
                "upper": float(bands[1]) if bands[1] is not None else None,
            }
        )
    return {
        "items": items,
        "cutoff_date": run.cutoff_date,
        "interval_method": "Quantiles of aggregated trajectories",
    }


@router.post("/datasets/{dataset_id}/recommendation-runs", dependencies=[Depends(local_only)])
def recommendations(dataset_id: str, inputs: RecommendationInput, db: DB):
    dataset_lock(db, dataset_id)
    try:
        identifier = create_recommendations(db, dataset_id, inputs)
    except ValueError as exc:
        raise AppError(400, "INVALID_POLICY", str(exc)) from exc
    db.commit()
    return serialize(get(db, RecommendationRun, identifier))


@router.get("/recommendation-runs/{identifier}")
def recommendation_run(identifier: str, dataset_id: str, db: DB):
    run = scoped(db, RecommendationRun, identifier, dataset_id)
    items = db.scalars(
        select(RecommendationItem).where(RecommendationItem.run_id == identifier)
    ).all()
    return {
        **serialize(run),
        "allocated_cost": str(sum(i.cost for i in items)),
        "requested_cost": str(
            sum(Decimal(i.explanation["unit_cost"]) * i.requested_units for i in items)
        ),
    }


@router.get("/recommendation-runs/{identifier}/items")
def recommendation_items(
    identifier: str,
    dataset_id: str,
    db: DB,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
):
    scoped(db, RecommendationRun, identifier, dataset_id)
    rows = db.scalars(
        select(RecommendationItem)
        .where(RecommendationItem.run_id == identifier)
        .order_by(RecommendationItem.risk.desc().nulls_last(), RecommendationItem.product_id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    result = []
    for row in rows:
        events = db.scalars(
            select(Decision).where(Decision.item_id == row.id).order_by(Decision.version)
        ).all()
        result.append({**serialize(row), "decisions": [serialize(e) for e in events]})
    return {
        "items": result,
        "total": db.scalar(
            select(func.count())
            .select_from(RecommendationItem)
            .where(RecommendationItem.run_id == identifier)
        ),
        "page": page,
        "page_size": page_size,
    }


@router.post("/recommendation-items/{identifier}/decisions", dependencies=[Depends(local_only)])
def decision(identifier: str, dataset_id: str, inputs: DecisionInput, db: DB):
    result = decide(db, identifier, dataset_id, inputs)
    db.commit()
    return serialize(result)


def csv_text(value: str) -> str:
    return "'" + value if value.lstrip().startswith(("=", "+", "-", "@")) else value


@router.get("/recommendation-runs/{identifier}/export")
def export(identifier: str, dataset_id: str, db: DB):
    scoped(db, RecommendationRun, identifier, dataset_id)
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        [
            "sku",
            "description",
            "requested_units",
            "allocated_units",
            "final_units",
            "decision",
            "cost_gbp",
            "forecast_version",
        ]
    )
    for item in db.scalars(
        select(RecommendationItem).where(RecommendationItem.run_id == identifier)
    ):
        last = db.scalar(
            select(Decision)
            .where(Decision.item_id == item.id)
            .order_by(Decision.version.desc())
            .limit(1)
        )
        final = last.final_units if last else item.allocated_units
        writer.writerow(
            [
                csv_text(item.explanation["sku"]),
                csv_text(item.explanation["description"]),
                item.requested_units,
                item.allocated_units,
                final,
                last.action if last else "proposed",
                Decimal(item.explanation["unit_cost"]) * final,
                item.explanation["forecast_version"],
            ]
        )
    return Response(
        buffer.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="stockpilot-plan-{identifier}.csv"'},
    )


@router.post("/datasets/{dataset_id}/scenario-runs", status_code=202)
def start_scenario(dataset_id: str, inputs: ScenarioInput, db: DB, request: Request):
    scoped(db, RecommendationRun, inputs.base_run_id, dataset_id)
    owner = session_hash(request)
    dataset_lock(db, dataset_id)
    if settings.app_mode == "public_demo":
        dataset_lock(db, "public-scenarios")
        active = (
            db.scalar(
                select(func.count())
                .select_from(Job)
                .where(Job.kind == "scenario", Job.status.in_(["queued", "running"]))
            )
            or 0
        )
        recent = (
            db.scalar(
                select(func.count())
                .select_from(Job)
                .where(Job.owner_hash == owner, Job.created_at > utcnow() - timedelta(minutes=1))
            )
            or 0
        )
        if active >= 2 or recent >= 3:
            raise AppError(429, "RATE_LIMIT", "Demo computation limit reached; try again later")
    job = enqueue(db, dataset_id, "scenario", inputs.model_dump(mode="json"), owner)
    db.commit()
    return serialize(job)


@router.get("/datasets/{dataset_id}/scenario-runs")
def scenario_history(
    dataset_id: str,
    db: DB,
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
):
    query = (
        select(ScenarioRun)
        .join(RecommendationRun)
        .join(ForecastRun)
        .where(
            ForecastRun.dataset_id == dataset_id, ScenarioRun.owner_hash == session_hash(request)
        )
    )
    if settings.app_mode == "public_demo":
        query = query.where(ScenarioRun.expires_at > utcnow())
    return {
        "items": [
            serialize(row)
            for row in db.scalars(
                query.order_by(ScenarioRun.created_at.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        ]
    }


@router.get("/scenario-runs/{identifier}")
def scenario(identifier: str, dataset_id: str, db: DB, request: Request):
    return serialize(owned_scenario(db, identifier, dataset_id, session_hash(request)))


@router.get("/scenario-runs/{identifier}/daily-results")
def daily_results(
    identifier: str,
    dataset_id: str,
    db: DB,
    request: Request,
    policy: Literal["no_purchase", "moving_average", "selected_model"] = "selected_model",
    product_id: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
):
    owned_scenario(db, identifier, dataset_id, session_hash(request))
    query = select(ScenarioDaily).where(
        ScenarioDaily.scenario_id == identifier, ScenarioDaily.policy == policy
    )
    if product_id:
        scoped(db, Product, product_id, dataset_id)
        query = query.where(ScenarioDaily.product_id == product_id)
    return {
        "items": [
            serialize(row)
            for row in db.scalars(
                query.order_by(ScenarioDaily.day, ScenarioDaily.product_id)
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        ]
    }


@router.get("/jobs/{identifier}")
def job_status(identifier: str, dataset_id: str, db: DB, request: Request):
    job = scoped(db, Job, identifier, dataset_id)
    if settings.app_mode == "public_demo" and (
        job.owner_hash != session_hash(request) or job.created_at <= utcnow() - timedelta(hours=24)
    ):
        raise AppError(404, "NOT_FOUND", "Job not found")
    return serialize(job)
