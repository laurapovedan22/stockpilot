import hashlib
import json
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from typing import Any
from uuid import NAMESPACE_URL, uuid5
from zoneinfo import ZoneInfo

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from stockpilot.db.models import (
    DailySale,
    Dataset,
    Inbound,
    InventoryItem,
    Product,
    Sale,
    Snapshot,
    Supplier,
)

CONFIG: dict[str, Any] = {
    "seed": 42,
    "products": 20,
    "days": 730,
    "as_of_date": "2025-12-31",
    "currency": "GBP",
    "timezone": "Europe/London",
    "generator_version": "1.0",
}
NAMES = [
    "Ceramic mug",
    "Linen notebook",
    "Desk organiser",
    "Cotton tote",
    "Glass carafe",
    "Brass bookmark",
    "Travel pouch",
    "Wool coaster",
    "Candle holder",
    "Photo frame",
    "Gift ribbon",
    "Enamel pin",
    "Greeting card",
    "Tea infuser",
    "Storage tin",
    "Paper lantern",
    "Canvas apron",
    "Wooden tray",
    "Pocket mirror",
    "Decorative vase",
]


def seed_demo(session: Session) -> Dataset:
    existing = session.scalar(
        select(Dataset).where(Dataset.id == str(uuid5(NAMESPACE_URL, "stockpilot/synthetic/v1/42")))
    )
    if existing:
        return existing
    rng = np.random.default_rng(CONFIG["seed"])
    cutoff = date.fromisoformat(str(CONFIG["as_of_date"]))
    dataset = Dataset(
        id=str(uuid5(NAMESPACE_URL, "stockpilot/synthetic/v1/42")),
        name="Synthetic demo · seed 42",
        mode="synthetic",
        currency="GBP",
        timezone="Europe/London",
        as_of_date=cutoff,
        seed=42,
        provenance={
            "source": "StockPilot synthetic generator",
            "license": "MIT",
            "config": CONFIG,
            "operational_fields": "simulated",
        },
    )
    session.add(dataset)
    session.flush()
    for number in range(4):
        session.add(
            Supplier(
                dataset_id=dataset.id,
                code=f"SIM-{number + 1}",
                name=f"Fictional supplier {number + 1}",
            )
        )
    snapshot = Snapshot(dataset_id=dataset.id, as_of_date=cutoff, version=1, origin="synthetic")
    session.add(snapshot)
    session.flush()
    digest = hashlib.sha256(json.dumps(CONFIG, sort_keys=True).encode())
    start = cutoff - timedelta(days=729)
    for number, name in enumerate(NAMES, 1):
        product = Product(
            id=str(uuid5(NAMESPACE_URL, f"{dataset.id}/DEMO-{number:03d}")),
            dataset_id=dataset.id,
            sku=f"DEMO-{number:03d}",
            description=name,
            provenance={
                "sales": "synthetic",
                "operations": "simulated",
                "intermittent": number % 5 == 0,
            },
        )
        session.add(product)
        session.flush()
        base = 4 + number * 1.5
        values = []
        for step in range(730):
            day = start + timedelta(days=step)
            mean = base * (1 + 0.28 * np.sin(2 * np.pi * day.weekday() / 7)) * (1 + 0.00035 * step)
            units = int(rng.poisson(mean))
            if number % 5 == 0 and rng.random() < 0.65:
                units = 0
            if step == 0:
                units = max(units, 1)
            values.append(units)
            session.add(DailySale(product_id=product.id, day=day, units=units))
            session.add(
                Sale(
                    dataset_id=dataset.id,
                    product_id=product.id,
                    external_row_id=f"{product.sku}-{day}",
                    invoice_id=f"SIM-{day}-{number}",
                    invoice_datetime=datetime.combine(
                        day, time(12), tzinfo=ZoneInfo("Europe/London")
                    ),
                    day=day,
                    quantity=units,
                    unit_price=Decimal("5.00") + number,
                    cancellation=False,
                    country="United Kingdom",
                )
            )
        digest.update(np.asarray(values, dtype=np.int64).tobytes())
        session.add(
            InventoryItem(
                snapshot_id=snapshot.id,
                product_id=product.id,
                supplier_code=f"SIM-{1 + (number - 1) % 4}",
                on_hand=int(base * (2 + number % 12)),
                reserved=number % 4,
                unit_cost=Decimal("1.25") + Decimal(number) / 4,
                lead_time_days=2 + number % 12,
                pack_size=6 if number % 2 else 12,
                minimum_order_units=12,
                holding_cost=Decimal("0.015"),
                stockout_penalty=Decimal("2.00"),
            )
        )
        if number % 3 == 0:
            session.add(
                Inbound(
                    snapshot_id=snapshot.id,
                    product_id=product.id,
                    external_order_id=f"SIM-PO-{number}",
                    quantity=24,
                    arrival=cutoff + timedelta(days=5 + number % 9),
                )
            )
    dataset.provenance = {**dataset.provenance, "checksum": digest.hexdigest()}
    session.flush()
    return dataset
