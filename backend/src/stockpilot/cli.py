import argparse
import json
import time
from datetime import date
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

import numpy as np
import pandas as pd
from sqlalchemy import select

from stockpilot.api.schemas import RecommendationInput
from stockpilot.db.models import DailySale, Dataset, ForecastRun, InventoryItem, Job, Snapshot
from stockpilot.db.repositories import latest, products
from stockpilot.db.session import SessionFactory
from stockpilot.domain.assistant.retrieval import index_documents
from stockpilot.domain.ingestion.retail_adapter import convert, fetch
from stockpilot.domain.inventory.backtest import historical_backtest
from stockpilot.services.imports import apply_import, preview
from stockpilot.services.recommendations import create_recommendations, operational_items
from stockpilot.services.synthetic import seed_demo
from stockpilot.worker.queue import enqueue


def wait(identifier: str, timeout: int = 600) -> str:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        with SessionFactory() as session:
            job = session.get(Job, identifier)
            if job is None:
                raise RuntimeError("Job not found")
            print(f"{job.status}: {job.stage}", flush=True)
            if job.status == "succeeded":
                if job.result_id is None:
                    raise RuntimeError("Completed job has no result")
                return job.result_id
            if job.status == "failed":
                raise RuntimeError(job.error)
        time.sleep(2)
    raise TimeoutError("Job did not finish within 600 seconds; check worker logs")


def demo() -> None:
    with SessionFactory.begin() as session:
        dataset = seed_demo(session)
        identifier = dataset.id
        index_documents(session, Path("../docs/policies"))
        existing = latest(session, ForecastRun, identifier)
        job = (
            enqueue(
                session,
                identifier,
                "forecast",
                {"horizon": 42, "cutoff_date": dataset.as_of_date.isoformat()},
            )
            if not existing
            else None
        )
        job_id = job.id if job else None
    forecast_id = wait(job_id) if job_id else existing.id
    with SessionFactory.begin() as session:
        from stockpilot.db.models import RecommendationRun

        run = session.scalar(
            select(RecommendationRun).where(RecommendationRun.forecast_run_id == forecast_id)
        )
        if not run:
            snapshot = latest(session, Snapshot, identifier)
            run_id = create_recommendations(
                session,
                identifier,
                RecommendationInput(forecast_run_id=forecast_id, snapshot_id=snapshot.id),
            )
        else:
            run_id = run.id
    print(
        json.dumps(
            {
                "dataset_id": identifier,
                "forecast_run_id": forecast_id,
                "recommendation_run_id": run_id,
            }
        )
    )


def train_retail() -> None:
    raw = Path("../data/raw/online_retail_II.xlsx")
    canonical = Path("../data/processed/retail.csv")
    if not raw.exists():
        raise FileNotFoundError("Run fetch-retail explicitly first")
    print("Converting UCI worksheets", flush=True)
    manifest = convert(raw, canonical)
    print(f"Validating {manifest['canonical_rows']} canonical rows", flush=True)
    with SessionFactory.begin() as session:
        dataset = session.get(
            Dataset, str(uuid5(NAMESPACE_URL, f"stockpilot/uci/{manifest['checksum']}"))
        )
        if not dataset:
            dataset = Dataset(
                id=str(uuid5(NAMESPACE_URL, f"stockpilot/uci/{manifest['checksum']}")),
                name="UCI Online Retail II · historical",
                mode="historical",
                as_of_date=date(2009, 12, 1),
                provenance={
                    "source": "Chen, D. (2012) · UCI Online Retail II",
                    "license": "CC BY 4.0",
                    "doi": "10.24432/C5CG6D",
                    "adapter": manifest,
                    "operational_fields": "simulated",
                },
            )
            session.add(dataset)
            session.flush()
        # CLI adapter has its separate 100 MiB limit; HTTP remains at 10 MiB.
        from stockpilot.config import settings

        previous_limit = settings.max_csv_bytes
        settings.max_csv_bytes = canonical.stat().st_size
        try:
            batch = preview(session, dataset.id, canonical.read_bytes(), "sales", {})
        finally:
            settings.max_csv_bytes = previous_limit
        excluded = [e["row"] for e in batch.report["errors"]]
        print(
            f"Importing {batch.report['valid']} valid rows; excluding {len(excluded)} invalid rows",
            flush=True,
        )
        apply_import(session, batch.id, excluded, complete=False)
        print("Daily aggregation complete; preparing simulated operations", flush=True)
        snapshot = latest(session, Snapshot, dataset.id)
        if not snapshot:
            from decimal import Decimal

            snapshot = Snapshot(
                dataset_id=dataset.id,
                as_of_date=dataset.as_of_date,
                version=1,
                origin="simulated UCI operations",
            )
            session.add(snapshot)
            session.flush()
            for number, product in enumerate(
                [p for p in products(session, dataset.id) if p.active]
            ):
                recent = session.scalars(
                    select(DailySale.units)
                    .where(DailySale.product_id == product.id)
                    .order_by(DailySale.day.desc())
                    .limit(28)
                ).all()
                session.add(
                    InventoryItem(
                        snapshot_id=snapshot.id,
                        product_id=product.id,
                        supplier_code=f"SIM-{1 + number % 4}",
                        on_hand=int(np.mean(recent) * 5),
                        reserved=0,
                        unit_cost=Decimal("2.50"),
                        lead_time_days=7,
                        pack_size=6,
                        minimum_order_units=12,
                        holding_cost=Decimal(".015"),
                        stockout_penalty=Decimal("2.00"),
                    )
                )
        job = enqueue(
            session,
            dataset.id,
            "forecast",
            {"horizon": 42, "cutoff_date": dataset.as_of_date.isoformat()},
        )
        job_id, dataset_id, snapshot_id = job.id, dataset.id, snapshot.id
    forecast_id = wait(job_id)
    with SessionFactory.begin() as session:
        result = create_recommendations(
            session,
            dataset_id,
            RecommendationInput(forecast_run_id=forecast_id, snapshot_id=snapshot_id),
        )
        print(result)


def backtest(dataset_id: str) -> None:
    with SessionFactory() as session:
        from stockpilot.config import settings
        from stockpilot.db.repositories import get

        dataset = get(session, Dataset, dataset_id)
        forecast = latest(session, ForecastRun, dataset_id)
        snapshot = latest(session, Snapshot, dataset_id)
        if forecast is None or snapshot is None:
            raise ValueError(
                "Prepare a forecast and inventory snapshot before running the backtest"
            )
        items = operational_items(session, forecast, snapshot)
        series = {}
        eligible = []
        selection_cutoff = pd.Timestamp(dataset.as_of_date) - pd.Timedelta(days=140)
        for product in products(session, dataset_id):
            rows = session.scalars(
                select(DailySale)
                .where(DailySale.product_id == product.id, DailySale.day <= dataset.as_of_date)
                .order_by(DailySale.day)
            ).all()
            values = pd.Series(
                [r.units for r in rows], index=pd.to_datetime([r.day for r in rows]), dtype=float
            )
            selection = values.loc[:selection_cutoff]
            if len(selection) >= 365 and int((selection > 0).sum()) >= 90:
                eligible.append((float(selection.sum()), product.sku, product.id, values))
        selected = sorted(eligible, key=lambda entry: (-entry[0], entry[1]))[:20]
        existing = {item["product_id"]: item for item in items}
        operations = []
        for _, sku, identifier, values in selected:
            series[identifier] = values
            history = values.loc[: pd.Timestamp(dataset.as_of_date) - pd.Timedelta(days=28)]
            if identifier in existing:
                operation = existing[identifier]
            else:
                operation = {
                    "product_id": identifier,
                    "sku": sku,
                    "on_hand": int(history.iloc[-28:].mean() * 5),
                    "reserved": 0,
                    "unit_cost": "2.50",
                    "lead_time_days": 7,
                    "pack_size": 6,
                    "minimum_order_units": 12,
                    "holding_cost": ".015",
                    "stockout_penalty": "2.00",
                    "arrivals": {},
                }
            operations.append(operation)
        result = historical_backtest(series, operations)
        result["manifest"] = {
            "dataset_id": dataset_id,
            "as_of_date": dataset.as_of_date.isoformat(),
            "selection_cutoff": selection_cutoff.date().isoformat(),
            "product_skus": [row[1] for row in selected],
            "operation_origin": "Frozen current snapshot or explicit simulated fallback; not historical observations",
            "seed": 42,
        }
    output = Path(settings.artifact_dir) / f"backtest-{dataset_id}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(output)


def main() -> None:
    parser = argparse.ArgumentParser(description="StockPilot reproducible operations")
    parser.add_argument(
        "command", choices=["seed-demo", "demo", "fetch-retail", "train-retail", "backtest"]
    )
    parser.add_argument("--dataset-id")
    args = parser.parse_args()
    if args.command == "seed-demo":
        with SessionFactory.begin() as session:
            print(seed_demo(session).id)
            index_documents(session, Path("../docs/policies"))
    elif args.command == "demo":
        demo()
    elif args.command == "fetch-retail":
        print(fetch(Path("../data/raw")))
    elif args.command == "train-retail":
        train_retail()
    elif args.command == "backtest":
        if not args.dataset_id:
            parser.error("--dataset-id is required for backtest")
        backtest(args.dataset_id)


if __name__ == "__main__":
    main()
