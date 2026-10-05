import hashlib
import json
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import uuid4

import pandas as pd
from sqlalchemy import delete, func, insert, select
from sqlalchemy.orm import Session

from stockpilot.api.errors import AppError
from stockpilot.config import settings
from stockpilot.db.models import (
    DailySale,
    Dataset,
    ImportBatch,
    Inbound,
    InventoryItem,
    Product,
    Sale,
    Snapshot,
    utcnow,
)
from stockpilot.db.repositories import get, latest, products
from stockpilot.domain.forecasting.aggregation import daily_series
from stockpilot.domain.ingestion.validation import validate_csv


def preview(
    session: Session, dataset_id: str, content: bytes, kind: str, mapping: dict
) -> ImportBatch:
    dataset = get(session, Dataset, dataset_id)
    if len(content) > settings.max_csv_bytes:
        raise AppError(413, "FILE_TOO_LARGE", "CSV exceeds configured size limit")
    checksum = hashlib.sha256(content).hexdigest()
    key = hashlib.sha256(
        (dataset_id + kind + checksum + json.dumps(mapping, sort_keys=True)).encode()
    ).hexdigest()
    existing = session.scalar(
        select(ImportBatch).where(ImportBatch.dataset_id == dataset_id, ImportBatch.key == key)
    )
    if existing and (existing.status != "preview" or existing.expires_at > utcnow()):
        return existing
    existing_ids = (
        set(session.scalars(select(Sale.external_row_id).where(Sale.dataset_id == dataset_id)))
        if kind == "sales"
        else set()
    )
    try:
        report = validate_csv(
            content, kind, mapping, dataset.currency, dataset.timezone, existing_ids
        )
    except (ValueError, UnicodeError) as exc:
        raise AppError(400, "INVALID_CSV", str(exc)) from exc
    if kind != "sales":
        skus = {p.sku for p in products(session, dataset_id)}
        for row in report["rows"]:
            if row["values"]["product_sku"] not in skus:
                report["errors"].append(
                    {"row": row["row"], "message": "Unknown product SKU; import sales first"}
                )
        invalid = {error["row"] for error in report["errors"]}
        report["valid"] = sum(row["row"] not in invalid for row in report["rows"])
    folder = Path(settings.upload_dir).resolve()
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{uuid4()}.csv"
    path.write_bytes(content)
    report["rows"] = report["rows"][:25]
    if existing:
        batch = existing
        batch.path, batch.report, batch.expires_at = (
            str(path),
            report,
            utcnow() + timedelta(hours=24),
        )
    else:
        batch = ImportBatch(
            dataset_id=dataset_id,
            kind=kind,
            checksum=checksum,
            key=key,
            mapping=mapping,
            path=str(path),
            report=report,
            expires_at=utcnow() + timedelta(hours=24),
        )
        session.add(batch)
    session.flush()
    return batch


def validate_confirmation(batch: ImportBatch, excluded: list[int]) -> None:
    if batch.status == "succeeded":
        return
    if batch.expires_at <= utcnow():
        raise AppError(409, "PREVIEW_EXPIRED", "Preview expired; upload the file again")
    missing = [row for row in batch.report["errors"] if row["row"] not in excluded]
    if missing:
        raise AppError(
            400,
            "INVALID_IMPORT",
            "Explicitly exclude all invalid rows before confirmation",
            missing,
        )


def apply_import(session: Session, batch_id: str, excluded: list[int], complete: bool) -> str:
    batch = get(session, ImportBatch, batch_id)
    if batch.status == "succeeded":
        return batch.id
    validate_confirmation(batch, excluded)
    dataset = get(session, Dataset, batch.dataset_id)
    has_previous_sales = bool(
        session.scalar(select(func.count()).select_from(Sale).where(Sale.dataset_id == dataset.id))
    )
    content = Path(batch.path).read_bytes()
    if hashlib.sha256(content).hexdigest() != batch.checksum:
        raise ValueError("Preview checksum mismatch")
    existing_ids = (
        set(session.scalars(select(Sale.external_row_id).where(Sale.dataset_id == dataset.id)))
        if batch.kind == "sales"
        else set()
    )
    report = validate_csv(
        content, batch.kind, batch.mapping, dataset.currency, dataset.timezone, existing_ids
    )
    invalid = {row["row"] for row in report["errors"]}
    excluded_set = set(excluded)
    if invalid - excluded_set:
        raise ValueError("Import validation changed; preview again")
    rows = [
        row
        for row in report["rows"]
        if row["row"] not in excluded_set and row["row"] not in invalid
    ]
    catalog = {p.sku: p for p in products(session, dataset.id)}
    previous = latest(session, Snapshot, dataset.id)
    if batch.kind in ("inventory", "inbound"):
        snapshot = Snapshot(
            dataset_id=dataset.id,
            as_of_date=dataset.as_of_date,
            version=previous.version + 1 if previous else 1,
            origin="csv",
        )
        session.add(snapshot)
        session.flush()
        if previous:
            replace_skus = (
                {row["values"]["product_sku"] for row in rows}
                if batch.kind == "inventory"
                else set()
            )
            sku_by_id = {p.id: p.sku for p in catalog.values()}
            for item in session.scalars(
                select(InventoryItem).where(InventoryItem.snapshot_id == previous.id)
            ):
                if sku_by_id[item.product_id] in replace_skus:
                    continue
                values = {
                    k: getattr(item, k)
                    for k in (
                        "product_id",
                        "supplier_code",
                        "on_hand",
                        "reserved",
                        "unit_cost",
                        "lead_time_days",
                        "pack_size",
                        "minimum_order_units",
                        "holding_cost",
                        "stockout_penalty",
                        "provenance",
                    )
                }
                session.add(InventoryItem(snapshot_id=snapshot.id, **values))
            for order in session.scalars(select(Inbound).where(Inbound.snapshot_id == previous.id)):
                session.add(
                    Inbound(
                        snapshot_id=snapshot.id,
                        product_id=order.product_id,
                        external_order_id=order.external_order_id,
                        quantity=order.quantity,
                        arrival=order.arrival,
                    )
                )
    if batch.kind == "sales":
        for entry in rows:
            row = entry["values"]
            sku = row["product_sku"]
            if sku not in catalog:
                catalog[sku] = Product(
                    dataset_id=dataset.id,
                    sku=sku,
                    description=row["description"],
                    active=False,
                    provenance={"sales": "csv", "source_checksum": batch.checksum},
                )
                session.add(catalog[sku])
        session.flush()
    sales_buffer: list[dict[str, Any]] = []
    for entry in rows:
        row = entry["values"]
        sku = row["product_sku"]
        if sku not in catalog:
            raise ValueError("Unknown product")
        product = catalog[sku]
        if batch.kind == "sales":
            sales_buffer.append(
                dict(
                    dataset_id=dataset.id,
                    batch_id=batch.id,
                    product_id=product.id,
                    external_row_id=row["external_row_id"] or f"{batch.key}:{entry['row']}",
                    invoice_id=row["invoice_id"],
                    invoice_datetime=datetime.fromisoformat(row["invoice_datetime"]),
                    day=date.fromisoformat(row["day"]),
                    quantity=int(row["quantity"]),
                    unit_price=Decimal(row["unit_price"]),
                    cancellation=row["cancellation"] == "True",
                    country=row["country"],
                )
            )
            if len(sales_buffer) >= 5000:
                session.execute(insert(Sale), sales_buffer)
                sales_buffer.clear()
        elif batch.kind == "inventory":
            session.add(
                InventoryItem(
                    snapshot_id=snapshot.id,
                    product_id=product.id,
                    supplier_code=row["supplier_code"],
                    on_hand=int(row["on_hand_units"]),
                    reserved=int(row["reserved_units"]),
                    unit_cost=Decimal(row["unit_cost"]),
                    lead_time_days=int(row["lead_time_days"]),
                    pack_size=int(row["pack_size"]),
                    minimum_order_units=int(row["minimum_order_units"]),
                    holding_cost=Decimal(row["holding_cost_per_unit_day"]),
                    stockout_penalty=Decimal(row["stockout_penalty_per_unit"]),
                    provenance="csv",
                )
            )
        else:
            session.add(
                Inbound(
                    snapshot_id=snapshot.id,
                    product_id=product.id,
                    external_order_id=row["external_order_id"],
                    quantity=int(row["quantity_units"]),
                    arrival=date.fromisoformat(row["expected_arrival_date"]),
                )
            )
    if sales_buffer:
        session.execute(insert(Sale), sales_buffer)
    session.flush()
    batch.report = {
        **report,
        "rows": [],
        "confirmed_exclusions": excluded,
        "written": len(rows),
        "last_day_complete": complete,
    }
    if batch.kind == "sales" and rows:
        end = max(date.fromisoformat(row["values"]["day"]) for row in rows)
        if not complete and end.isoformat() == report["max_date"]:
            end -= timedelta(days=1)
        dataset.as_of_date = max(dataset.as_of_date, end) if has_previous_sales else end
        rebuild_daily(session, dataset)
    batch.status = "succeeded"
    return batch.id


def rebuild_daily(session: Session, dataset: Dataset) -> None:
    catalog = products(session, dataset.id)
    selection_cutoff = dataset.as_of_date - timedelta(days=112)
    candidates = []
    incomplete = {
        batch.id: batch.report.get("max_date")
        for batch in session.scalars(
            select(ImportBatch).where(
                ImportBatch.dataset_id == dataset.id, ImportBatch.kind == "sales"
            )
        )
        if batch.report.get("last_day_complete") is False
    }
    for product in catalog:
        transactions = list(
            session.scalars(
                select(Sale).where(Sale.product_id == product.id, Sale.day <= dataset.as_of_date)
            )
        )
        records = [
            {
                "day": t.day,
                "quantity": t.quantity,
                "unit_price": float(t.unit_price),
                "cancellation": t.cancellation,
            }
            for t in transactions
            if t.day.isoformat() != incomplete.get(t.batch_id or "")
        ]
        series = daily_series(records, dataset.as_of_date)
        if (series > 2**31 - 1).any():
            raise ValueError("Aggregated daily units exceed the supported 32-bit range")
        session.execute(delete(DailySale).where(DailySale.product_id == product.id))
        daily_rows = [
            dict(product_id=product.id, day=pd.Timestamp(str(day)).date(), units=int(units))
            for day, units in series.items()
        ]
        if daily_rows:
            session.execute(insert(DailySale), daily_rows)
        selection = series[series.index <= pd.Timestamp(selection_cutoff)]
        if len(selection) >= 365 and int((selection > 0).sum()) >= 90:
            candidates.append((float(selection.sum()), product.sku, product))
        product.active = False
    for _, _, product in sorted(candidates, key=lambda x: (-x[0], x[1]))[:20]:
        product.active = True
    session.flush()
