from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from stockpilot.db.models import (
    ForecastPoint,
    ForecastRun,
    InventoryItem,
    Product,
    RecommendationItem,
    RecommendationRun,
    Snapshot,
)
from stockpilot.db.repositories import latest, serialize
from stockpilot.domain.assistant.retrieval import search_policy
from stockpilot.services.access import owned_scenario


class Arguments(BaseModel):
    model_config = ConfigDict(extra="forbid")
    identifier: str | None = Field(default=None, max_length=80)
    query: str | None = Field(default=None, max_length=500)


ToolName = Literal[
    "get_product",
    "get_inventory",
    "get_forecast",
    "get_recommendation_explanation",
    "get_scenario_result",
    "preview_scenario",
    "search_policy",
]


def invoke(
    session: Session,
    dataset_id: str,
    name: ToolName,
    arguments: Arguments,
    owner_hash: str | None = None,
) -> dict:
    if name == "search_policy":
        return {"sources": search_policy(session, arguments.query or "")}
    if name == "preview_scenario":
        return {
            "message": "Open Scenario lab to review inputs and explicitly run the simulation.",
            "route": "/scenarios",
        }
    if name == "get_scenario_result":
        scenario = owned_scenario(session, arguments.identifier or "", dataset_id, owner_hash)
        return {"result": serialize(scenario), "reference": {"type": "scenario", "id": scenario.id}}
    product = session.scalar(
        select(Product).where(Product.dataset_id == dataset_id, Product.sku == arguments.identifier)
    )
    if not product:
        return {"unavailable": "Product not found in selected dataset"}
    if name == "get_product":
        return {"product": serialize(product), "reference": {"type": "product", "id": product.id}}
    if name == "get_inventory":
        snapshot = latest(session, Snapshot, dataset_id)
        inventory_item = (
            session.scalar(
                select(InventoryItem).where(
                    InventoryItem.snapshot_id == snapshot.id, InventoryItem.product_id == product.id
                )
            )
            if snapshot
            else None
        )
        return {
            "inventory": serialize(inventory_item) if inventory_item else None,
            "reference": {"type": "snapshot", "id": snapshot.id, "version": snapshot.version}
            if snapshot
            else None,
        }
    forecast = latest(session, ForecastRun, dataset_id)
    if not forecast:
        return {"unavailable": "No forecast exists"}
    if name == "get_forecast":
        points = session.scalars(
            select(ForecastPoint)
            .where(ForecastPoint.run_id == forecast.id, ForecastPoint.product_id == product.id)
            .order_by(ForecastPoint.day)
        ).all()
        return {
            "points": [serialize(p) for p in points],
            "reference": {
                "type": "forecast",
                "id": forecast.id,
                "version": forecast.id,
                "date": forecast.cutoff_date.isoformat(),
            },
        }
    if name == "get_recommendation_explanation":
        item = session.scalar(
            select(RecommendationItem)
            .join(RecommendationRun)
            .where(
                RecommendationRun.forecast_run_id == forecast.id,
                RecommendationItem.product_id == product.id,
            )
            .order_by(RecommendationRun.created_at.desc())
            .limit(1)
        )
        return {
            "explanation": item.explanation if item else None,
            "reference": {"type": "recommendation", "id": item.id, "version": item.run_id}
            if item
            else None,
        }
    raise ValueError("Tool not allowlisted")
