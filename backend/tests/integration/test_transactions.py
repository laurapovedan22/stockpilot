from datetime import timedelta

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import DBAPIError

from stockpilot.api.errors import AppError
from stockpilot.db.models import (
    Decision,
    ForecastRun,
    Product,
    RecommendationItem,
    RecommendationRun,
    Sale,
    Snapshot,
    utcnow,
)
from stockpilot.db.repositories import scoped
from stockpilot.services.imports import apply_import, preview, validate_confirmation
from stockpilot.worker.queue import claim, enqueue

pytestmark = pytest.mark.integration
HEADER = "external_row_id,invoice_id,product_sku,description,quantity,unit_price,invoice_datetime,country\n"


def test_import_idempotent_and_invalid_rows_never_partially_write(db, dataset):
    bad = (
        HEADER
        + "a,I,00012,Mug,3,2.5,2024-01-01T12:00:00,UK\n"
        + "b,I,00012,Mug,1.5,2.5,2024-01-01T12:00:00,UK\n"
    ).encode()
    batch = preview(db, dataset.id, bad, "sales", {})
    with pytest.raises(AppError):
        validate_confirmation(batch, [])
    assert db.scalar(select(func.count()).select_from(Sale)) == 0
    apply_import(db, batch.id, [3], True)
    db.flush()
    assert db.scalar(select(func.count()).select_from(Sale)) == 1
    assert preview(db, dataset.id, bad, "sales", {}).id == batch.id
    apply_import(db, batch.id, [3], True)
    assert db.scalar(select(func.count()).select_from(Sale)) == 1
    assert db.scalar(select(Product.sku)) == "00012"


def test_cross_dataset_resource_not_found(db, dataset):
    with pytest.raises(AppError) as error:
        scoped(db, Product, "missing", dataset.id)
    assert error.value.status == 404


def test_return_only_product_has_no_daily_demand_and_does_not_break_import(db, dataset):
    content = (HEADER + "r,C1,00012,Returned mug,-3,2.5,2024-01-01T12:00:00,UK\n").encode()
    batch = preview(db, dataset.id, content, "sales", {})
    apply_import(db, batch.id, [], True)
    assert db.scalar(select(func.count()).select_from(Sale)) == 1
    assert db.scalar(select(Product.active)) is False
    assert batch.status == "succeeded"


def test_queue_reclaims_interrupted_job_and_limits_attempts(db, dataset):
    job = enqueue(db, dataset.id, "scenario", {"example": 1})
    assert enqueue(db, dataset.id, "scenario", {"example": 1}).id == job.id
    first = claim(db)
    assert first.id == job.id and first.attempts == 1
    first.lease_until = utcnow() - timedelta(seconds=1)
    db.flush()
    second = claim(db)
    assert second.id == job.id and second.attempts == 2
    second.lease_until = utcnow() - timedelta(seconds=1)
    db.flush()
    assert claim(db) is None
    db.refresh(job)
    assert job.status == "failed"


def test_one_mutating_job_per_dataset(db, dataset):
    enqueue(db, dataset.id, "forecast", {"horizon": 28})
    with pytest.raises(AppError, match="already active"):
        enqueue(db, dataset.id, "import", {"batch_id": "x"})


def test_decisions_append_only_database_guard(db, dataset):
    product = Product(dataset_id=dataset.id, sku="00012", description="Mug")
    snapshot = Snapshot(
        dataset_id=dataset.id, as_of_date=dataset.as_of_date, version=1, origin="fixture"
    )
    forecast = ForecastRun(
        dataset_id=dataset.id,
        cutoff_date=dataset.as_of_date,
        horizon=42,
        model="moving_average",
        metrics={},
        checksum="fixture",
        artifact_path="fixture",
    )
    db.add_all([product, snapshot, forecast])
    db.flush()
    run = RecommendationRun(forecast_run_id=forecast.id, snapshot_id=snapshot.id, policy={})
    db.add(run)
    db.flush()
    item = RecommendationItem(
        run_id=run.id,
        product_id=product.id,
        requested_units=12,
        allocated_units=12,
        cost=30,
        explanation={},
    )
    db.add(item)
    db.flush()
    decision = Decision(
        item_id=item.id, action="accepted", final_units=12, reason="fixture", version=1
    )
    db.add(decision)
    db.flush()
    with pytest.raises(DBAPIError), db.begin_nested():
        db.execute(
            text("UPDATE decisions SET reason = 'changed' WHERE id = :id"), {"id": decision.id}
        )
