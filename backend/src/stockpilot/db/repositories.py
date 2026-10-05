from typing import Any
from uuid import UUID

from sqlalchemy import inspect, select
from sqlalchemy.orm import Session

from stockpilot.api.errors import AppError
from stockpilot.db.models import (
    Dataset,
    ForecastRun,
    InventoryItem,
    Product,
    RecommendationItem,
    RecommendationRun,
    Snapshot,
)


def get(session: Session, model, identifier: str):
    try:
        UUID(identifier)
    except (ValueError, TypeError, AttributeError) as exc:
        raise AppError(404, "NOT_FOUND", "Resource not found") from exc
    row = session.get(model, identifier)
    if row is None:
        raise AppError(404, "NOT_FOUND", "Resource not found")
    return row


def dataset_for(session: Session, row) -> str:
    if hasattr(row, "dataset_id"):
        return row.dataset_id
    if isinstance(row, InventoryItem):
        return get(session, Snapshot, row.snapshot_id).dataset_id
    if isinstance(row, RecommendationRun):
        return get(session, ForecastRun, row.forecast_run_id).dataset_id
    if isinstance(row, RecommendationItem):
        return dataset_for(session, get(session, RecommendationRun, row.run_id))
    raise AppError(400, "INVALID_RESOURCE", "Cannot resolve resource dataset")


def scoped(session: Session, model, identifier: str, dataset_id: str):
    get(session, Dataset, dataset_id)
    row = get(session, model, identifier)
    if dataset_for(session, row) != dataset_id:
        raise AppError(404, "NOT_FOUND", "Resource not found in selected dataset")
    return row


def serialize(row) -> dict[str, Any]:
    return {column.key: getattr(row, column.key) for column in inspect(row).mapper.column_attrs}


def latest(session: Session, model, dataset_id: str):
    return session.scalar(
        select(model)
        .where(model.dataset_id == dataset_id)
        .order_by(model.created_at.desc())
        .limit(1)
    )


def products(session: Session, dataset_id: str) -> list[Product]:
    return list(
        session.scalars(
            select(Product).where(Product.dataset_id == dataset_id).order_by(Product.sku)
        )
    )
