from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy import func, or_, select

from stockpilot.api.dependencies import DB, local_only, new_session_token, session_hash
from stockpilot.api.errors import AppError
from stockpilot.api.schemas import DatasetInput, InventoryInput
from stockpilot.config import settings
from stockpilot.db.models import (
    DailySale,
    Dataset,
    ForecastRun,
    ImportBatch,
    Inbound,
    InventoryItem,
    Product,
    RecommendationItem,
    RecommendationRun,
    ScenarioRun,
    Snapshot,
    utcnow,
)
from stockpilot.db.repositories import get, latest, scoped, serialize
from stockpilot.services.inventory import edit_inventory

router = APIRouter()


@router.post("/session")
def create_session(request: Request, response: Response):
    token = request.cookies.get("stockpilot_session", "")
    try:
        valid = len(token) == 64 and len(bytes.fromhex(token)) == 32
    except ValueError:
        valid = False
    if not valid:
        response.set_cookie(
            "stockpilot_session",
            new_session_token(),
            httponly=True,
            samesite="strict",
            max_age=86400,
            secure=request.url.scheme == "https",
        )
    return {"mode": settings.app_mode}


@router.get("/datasets")
def datasets(db: DB, page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=100)):
    rows = db.scalars(
        select(Dataset).order_by(Dataset.created_at).offset((page - 1) * page_size).limit(page_size)
    ).all()
    return {
        "items": [serialize(row) for row in rows],
        "total": db.scalar(select(func.count()).select_from(Dataset)),
        "page": page,
        "page_size": page_size,
        "app_mode": settings.app_mode,
    }


@router.post("/datasets", status_code=201, dependencies=[Depends(local_only)])
def create_dataset(inputs: DatasetInput, db: DB):
    if not inputs.name.strip() or not inputs.source.strip():
        raise AppError(400, "INVALID_DATASET", "Dataset name and source cannot be blank")
    dataset = Dataset(
        name=inputs.name.strip(),
        mode="historical",
        currency=inputs.currency,
        timezone=inputs.timezone,
        as_of_date=inputs.as_of_date,
        provenance={
            "source": inputs.source.strip(),
            "license": "User-supplied; verify permissions",
            "operations": "Not imported",
        },
    )
    db.add(dataset)
    db.commit()
    return serialize(dataset)


@router.get("/datasets/{dataset_id}/summary")
def summary(dataset_id: str, db: DB, request: Request):
    dataset = get(db, Dataset, dataset_id)
    forecast = latest(db, ForecastRun, dataset_id)
    snapshot = latest(db, Snapshot, dataset_id)
    run = (
        db.scalar(
            select(RecommendationRun)
            .where(RecommendationRun.forecast_run_id == forecast.id)
            .order_by(RecommendationRun.created_at.desc())
            .limit(1)
        )
        if forecast
        else None
    )
    items = (
        db.scalars(select(RecommendationItem).where(RecommendationItem.run_id == run.id)).all()
        if run
        else []
    )
    owner = session_hash(request)
    scenario = (
        db.scalar(
            select(ScenarioRun)
            .where(
                ScenarioRun.base_run_id == run.id,
                ScenarioRun.owner_hash == owner,
                or_(ScenarioRun.expires_at.is_(None), ScenarioRun.expires_at > utcnow()),
            )
            .order_by(ScenarioRun.created_at.desc())
            .limit(1)
        )
        if run
        else None
    )
    safe_forecast = (
        {k: v for k, v in serialize(forecast).items() if k != "artifact_path"} if forecast else None
    )
    return {
        "dataset": serialize(dataset),
        "active_products": db.scalar(
            select(func.count())
            .select_from(Product)
            .where(Product.dataset_id == dataset_id, Product.active.is_(True))
        ),
        "high_risk_products": sum(i.risk is not None and i.risk >= 0.5 for i in items),
        "recommended_cost": str(sum(i.cost for i in items)) if run else None,
        "forecast_run": safe_forecast,
        "snapshot": serialize(snapshot) if snapshot else None,
        "recommendation_run": serialize(run) if run else None,
        "last_scenario": serialize(scenario) if scenario else None,
        "risk_items": [
            serialize(i) for i in sorted(items, key=lambda i: float(i.risk or 0), reverse=True)[:5]
        ],
        "quality": [
            {k: v for k, v in serialize(b).items() if k != "path"}
            | {"report": {k: v for k, v in b.report.items() if k != "rows"}}
            for b in db.scalars(
                select(ImportBatch)
                .where(ImportBatch.dataset_id == dataset_id)
                .order_by(ImportBatch.created_at.desc())
                .limit(10)
            )
        ],
    }


@router.get("/datasets/{dataset_id}/products")
def list_products(
    dataset_id: str,
    db: DB,
    q: str = Query("", max_length=120),
    active: bool | None = None,
    supplier: str | None = None,
    risk: Literal["low", "medium", "high"] | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
):
    get(db, Dataset, dataset_id)
    statement = select(Product).where(Product.dataset_id == dataset_id)
    if active is not None:
        statement = statement.where(Product.active.is_(active))
    if q:
        escaped = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        statement = statement.where(
            or_(
                Product.sku.ilike(f"%{escaped}%", escape="\\"),
                Product.description.ilike(f"%{escaped}%", escape="\\"),
            )
        )
    if supplier:
        snapshot = latest(db, Snapshot, dataset_id)
        if snapshot:
            statement = statement.join(InventoryItem).where(
                InventoryItem.snapshot_id == snapshot.id, InventoryItem.supplier_code == supplier
            )
    if risk:
        forecast = latest(db, ForecastRun, dataset_id)
        run = (
            db.scalar(
                select(RecommendationRun)
                .where(RecommendationRun.forecast_run_id == forecast.id)
                .order_by(RecommendationRun.created_at.desc())
                .limit(1)
            )
            if forecast
            else None
        )
        if not run:
            return {"items": [], "total": 0, "page": page, "page_size": page_size}
        statement = statement.join(RecommendationItem).where(RecommendationItem.run_id == run.id)
        statement = (
            statement.where(RecommendationItem.risk >= 0.5)
            if risk == "high"
            else statement.where(RecommendationItem.risk < 0.2)
            if risk == "low"
            else statement.where(RecommendationItem.risk >= 0.2, RecommendationItem.risk < 0.5)
        )
    total = db.scalar(select(func.count()).select_from(statement.subquery()))
    rows = db.scalars(
        statement.order_by(Product.sku).offset((page - 1) * page_size).limit(page_size)
    ).all()
    return {
        "items": [serialize(p) for p in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/products/{identifier}")
def product(identifier: str, dataset_id: str, db: DB):
    row = scoped(db, Product, identifier, dataset_id)
    snapshot = latest(db, Snapshot, dataset_id)
    inventory = (
        db.scalar(
            select(InventoryItem).where(
                InventoryItem.snapshot_id == snapshot.id, InventoryItem.product_id == identifier
            )
        )
        if snapshot
        else None
    )
    orders = (
        db.scalars(
            select(Inbound).where(
                Inbound.snapshot_id == snapshot.id, Inbound.product_id == identifier
            )
        ).all()
        if snapshot
        else []
    )
    return {
        **serialize(row),
        "inventory": serialize(inventory) if inventory else None,
        "inbound": [serialize(o) for o in orders],
    }


@router.get("/products/{identifier}/sales")
def sales(
    identifier: str, dataset_id: str, db: DB, start: date | None = None, end: date | None = None
):
    scoped(db, Product, identifier, dataset_id)
    if start and end and start > end:
        raise AppError(400, "INVALID_RANGE", "Start must precede end")
    query = select(DailySale).where(DailySale.product_id == identifier)
    if start:
        query = query.where(DailySale.day >= start)
    if end:
        query = query.where(DailySale.day <= end)
    return {"items": [serialize(row) for row in db.scalars(query.order_by(DailySale.day)).all()]}


@router.get("/datasets/{dataset_id}/inventory")
def inventory(dataset_id: str, db: DB):
    get(db, Dataset, dataset_id)
    snapshot = latest(db, Snapshot, dataset_id)
    return {
        "snapshot": serialize(snapshot) if snapshot else None,
        "items": [
            serialize(row)
            for row in db.scalars(
                select(InventoryItem).where(InventoryItem.snapshot_id == snapshot.id)
            )
        ]
        if snapshot
        else [],
        "inbound": [
            serialize(row)
            for row in db.scalars(select(Inbound).where(Inbound.snapshot_id == snapshot.id))
        ]
        if snapshot
        else [],
    }


@router.patch("/inventory/{identifier}", dependencies=[Depends(local_only)])
def update_inventory(identifier: str, dataset_id: str, inputs: InventoryInput, db: DB):
    result = edit_inventory(db, identifier, dataset_id, inputs)
    db.commit()
    return serialize(result)


@router.get("/datasets/{dataset_id}/methodology")
def methodology(dataset_id: str, db: DB):
    dataset = get(db, Dataset, dataset_id)
    return {
        "dataset": serialize(dataset),
        "author": "Laura Poveda Nicolás",
        "assumptions": [
            "Recorded positive sales are a demand proxy; lost demand is not observed",
            "Zero-filled dates only inside observed catalog coverage",
            "Operational fields are synthetic/simulated in prepared demos",
            "Global temporal validation: three expanding 28-day folds; 28-day final holdout",
            "Model chosen on validation WAPE, MAE tie-break; test does not select model",
            "Intervals: signed residual envelope; seven-day bootstrap trajectories",
            "Inventory: lost sales, no backorders, one warehouse and currency",
            "Simulated purchase costs are separate from holding and stockout penalties",
            "No purchase is transmitted to a supplier",
        ],
        "references": [
            {
                "title": "UCI Online Retail II · Chen (2012) · CC BY 4.0",
                "url": "https://doi.org/10.24432/C5CG6D",
            },
            {"title": "Project methodology", "url": "/about"},
        ],
    }
