import json
import os
import platform
import time
from datetime import date, timedelta
from pathlib import Path
from uuid import uuid4

import joblib
import numpy as np
import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from stockpilot.config import settings
from stockpilot.db.models import (
    DailySale,
    Dataset,
    EvaluationResult,
    ForecastPoint,
    ForecastRun,
    Product,
)
from stockpilot.db.repositories import get
from stockpilot.domain.forecasting.training import forecast


def train(session: Session, dataset_id: str, cutoff: str | None, horizon: int) -> str:
    dataset = get(session, Dataset, dataset_id)
    end = date.fromisoformat(cutoff) if cutoff else dataset.as_of_date
    if end > dataset.as_of_date:
        raise ValueError("Cutoff exceeds last complete dataset day")
    catalog = list(session.scalars(select(Product).where(Product.dataset_id == dataset_id)))
    candidates = []
    for product in catalog:
        rows = list(
            session.scalars(
                select(DailySale)
                .where(DailySale.product_id == product.id, DailySale.day <= end)
                .order_by(DailySale.day)
            )
        )
        if rows:
            values = pd.Series(
                [r.units for r in rows], index=pd.to_datetime([r.day for r in rows]), dtype=float
            )
            selection = values[values.index <= pd.Timestamp(end - timedelta(days=112))]
            if len(selection) >= 365 and int((selection > 0).sum()) >= 90:
                candidates.append((float(selection.sum()), product.sku, product.id, values))
    series = {
        key: values for _, _, key, values in sorted(candidates, key=lambda c: (-c[0], c[1]))[:20]
    }
    started = time.monotonic()
    result = forecast(series, horizon, settings.random_seed)
    run_id = str(uuid4())
    folder = Path(settings.artifact_dir).resolve() / run_id
    folder.mkdir(parents=True)
    path = folder / "trajectories.npz"
    temp = folder / "trajectories.tmp.npz"
    np.savez_compressed(
        temp, **{key: value for key, value in result["paths"].items() if value is not None}
    )
    os.replace(temp, path)
    for name in ("operation_model", "evaluation_model"):
        if result[name] is not None:
            joblib.dump(result[name], folder / f"{name}.joblib")
    manifest = {
        "dataset_id": dataset_id,
        "cutoff": end.isoformat(),
        "seed": settings.random_seed,
        "checksum": result["checksum"],
        "model": result["model"],
        "horizon": horizon,
        "elapsed_seconds": time.monotonic() - started,
        "hardware": {
            "platform": platform.platform(),
            "processor": platform.processor(),
            "machine": platform.machine(),
            "logical_cpus": os.cpu_count(),
        },
        "python": platform.python_version(),
        "commit": os.environ.get("GIT_COMMIT", "unversioned"),
        "products": len(series),
        "rows": sum(len(v) for v in series.values()),
        "metrics": result["metrics"],
    }
    (folder / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    run = ForecastRun(
        id=run_id,
        dataset_id=dataset_id,
        cutoff_date=end,
        horizon=horizon,
        model=result["model"],
        metrics={**result["metrics"], "manifest": manifest},
        checksum=result["checksum"],
        artifact_path=str(path),
    )
    session.add(run)
    session.flush()
    for product_id, values in result["points"].items():
        for step in range(horizon):
            session.add(
                ForecastPoint(
                    run_id=run_id,
                    product_id=product_id,
                    day=end + timedelta(days=step + 1),
                    yhat=float(values["central"][step]),
                    lower=float(values["lower"][step]) if values["lower"] is not None else None,
                    upper=float(values["upper"][step]) if values["upper"] is not None else None,
                )
            )
    for fold in result["folds"]:
        session.add(
            EvaluationResult(
                run_id=run_id,
                fold=fold["fold"],
                product_id=fold["product_id"],
                model=fold["model"],
                metrics={
                    **fold["metrics"],
                    "start": fold["start"],
                    "end": fold["end"],
                    "train_days": fold["train_days"],
                },
            )
        )
    return run.id


def load_paths(run: ForecastRun) -> dict[str, np.ndarray]:
    root = Path(settings.artifact_dir).resolve()
    path = Path(run.artifact_path).resolve()
    if not path.is_relative_to(root) or path.name != "trajectories.npz":
        raise ValueError("Untrusted artifact path")
    with np.load(path, allow_pickle=False) as data:
        return {key: data[key] for key in data.files}
