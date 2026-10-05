from decimal import Decimal

import numpy as np
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from stockpilot.api.errors import AppError
from stockpilot.api.schemas import DecisionInput, RecommendationInput
from stockpilot.db.models import (
    DailySale,
    Decision,
    ForecastPoint,
    ForecastRun,
    Inbound,
    InventoryItem,
    Product,
    RecommendationItem,
    RecommendationRun,
    Snapshot,
)
from stockpilot.db.repositories import get, scoped, serialize
from stockpilot.domain.inventory.allocation import allocate
from stockpilot.domain.inventory.replenishment import arrival_risk, chronological_losses, recommend
from stockpilot.services.forecasts import load_paths


def operational_items(session: Session, forecast: ForecastRun, snapshot: Snapshot) -> list[dict]:
    paths = load_paths(forecast)
    items = []
    for item in session.scalars(
        select(InventoryItem).where(InventoryItem.snapshot_id == snapshot.id)
    ):
        product = get(session, Product, item.product_id)
        points = list(
            session.scalars(
                select(ForecastPoint)
                .where(ForecastPoint.run_id == forecast.id, ForecastPoint.product_id == product.id)
                .order_by(ForecastPoint.day)
            )
        )
        if not points:
            continue
        central = np.asarray([float(p.yhat) for p in points])
        arrivals: dict[int, int] = {}
        for order in session.scalars(
            select(Inbound).where(
                Inbound.snapshot_id == snapshot.id, Inbound.product_id == product.id
            )
        ):
            day = (order.arrival - forecast.cutoff_date).days
            if day > 0:
                arrivals[day] = arrivals.get(day, 0) + order.quantity
        recent = list(
            session.scalars(
                select(DailySale.units)
                .where(DailySale.product_id == product.id, DailySale.day <= forecast.cutoff_date)
                .order_by(DailySale.day.desc())
                .limit(28)
            )
        )
        items.append(
            {
                **serialize(item),
                "product_id": product.id,
                "sku": product.sku,
                "description": product.description,
                "unit_cost": str(item.unit_cost),
                "holding_cost": str(item.holding_cost),
                "stockout_penalty": str(item.stockout_penalty),
                "central": central,
                "paths": paths.get(product.id),
                "arrivals": arrivals,
                "moving_average": float(np.mean(recent)) if recent else 0,
            }
        )
    return items


def create_recommendations(session: Session, dataset_id: str, inputs: RecommendationInput) -> str:
    forecast = scoped(session, ForecastRun, inputs.forecast_run_id, dataset_id)
    snapshot = scoped(session, Snapshot, inputs.snapshot_id, dataset_id)
    if forecast.cutoff_date != snapshot.as_of_date:
        raise AppError(400, "DATE_MISMATCH", "Inventory and forecast must share reference date")
    operational = operational_items(session, forecast, snapshot)
    if not operational:
        raise AppError(400, "NO_INVENTORY", "Import inventory for forecast products first")
    calculated = []
    for item in operational:
        explanation = recommend(
            item["paths"],
            item["central"],
            item,
            item["arrivals"],
            inputs.policy.service_level,
            inputs.policy.review_days,
        )
        calculated.append(
            {
                **item,
                **explanation,
                "paths": item["paths"]
                if item["paths"] is not None
                else np.tile(item["central"], (200, 1)),
                "explanation": explanation,
            }
        )
    allocated = allocate(calculated, inputs.budget)
    run = RecommendationRun(
        forecast_run_id=forecast.id,
        snapshot_id=snapshot.id,
        policy=inputs.policy.model_dump(),
        budget=inputs.budget,
    )
    session.add(run)
    session.flush()
    for item in calculated:
        units = allocated[item["product_id"]]
        explanation = dict(item["explanation"])
        if item["risk"] is not None:
            losses = chronological_losses(
                item["paths"][:, : explanation["protection_days"]],
                explanation["available"],
                item["arrivals"],
                units,
                item["lead_time_days"],
            )
            explanation["risk_after_requested"] = explanation["risk_after"]
            explanation["risk_after"] = float(np.mean(losses > 0))
            first, before = arrival_risk(
                item["paths"],
                explanation["available"],
                item["arrivals"],
                units,
                item["lead_time_days"],
                explanation["protection_days"],
            )
            explanation.update(
                first_arrival_day=first,
                risk_before_first_arrival=before,
                arrival_warning=before > 0,
            )
        session.add(
            RecommendationItem(
                run_id=run.id,
                product_id=item["product_id"],
                requested_units=item["requested_units"],
                allocated_units=units,
                cost=(Decimal(item["unit_cost"]) * units).quantize(Decimal(".01")),
                risk=item["risk"],
                explanation={
                    **explanation,
                    "sku": item["sku"],
                    "description": item["description"],
                    "allocated_units": units,
                    "unmet_units": item["requested_units"] - units,
                    "cause": "budget_constraint" if units < item["requested_units"] else None,
                    "forecast_version": forecast.id,
                    "snapshot_version": snapshot.version,
                },
            )
        )
    return run.id


def decide(session: Session, item_id: str, dataset_id: str, inputs: DecisionInput) -> Decision:
    item = scoped(session, RecommendationItem, item_id, dataset_id)
    run = get(session, RecommendationRun, item.run_id)
    # Serialize all decisions in a budgeted plan, including different SKUs.
    session.execute(
        select(RecommendationRun).where(RecommendationRun.id == run.id).with_for_update()
    ).scalar_one()
    version = (
        session.scalar(select(func.max(Decision.version)).where(Decision.item_id == item.id)) or 0
    )
    if version != inputs.expected_version:
        raise AppError(409, "VERSION_CONFLICT", "Decision changed; refresh before saving")
    units = 0 if inputs.action == "rejected" else item.allocated_units
    if inputs.action == "adjusted":
        if inputs.final_units is None or not inputs.reason.strip():
            raise AppError(400, "INVALID_DECISION", "Adjustment requires units and reason")
        units = inputs.final_units
    explanation = item.explanation
    if units and (units % explanation["pack_size"] or units < explanation["minimum_order_units"]):
        raise AppError(400, "PACK_CONSTRAINT", "Quantity must respect pack size and minimum order")
    if run.budget is not None:
        total = Decimal(units) * Decimal(explanation["unit_cost"])
        for other in session.scalars(
            select(RecommendationItem).where(
                RecommendationItem.run_id == run.id, RecommendationItem.id != item.id
            )
        ):
            last = session.scalar(
                select(Decision)
                .where(Decision.item_id == other.id)
                .order_by(Decision.version.desc())
                .limit(1)
            )
            planned = last.final_units if last else other.allocated_units
            total += Decimal(planned) * Decimal(other.explanation["unit_cost"])
        if total > run.budget:
            raise AppError(400, "BUDGET_EXCEEDED", "Create a new plan with a revised budget")
    decision = Decision(
        item_id=item.id,
        action=inputs.action,
        final_units=units,
        reason=inputs.reason,
        version=version + 1,
    )
    session.add(decision)
    session.flush()
    return decision
