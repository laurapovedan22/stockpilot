import math
from decimal import Decimal

import numpy as np

from stockpilot.domain.inventory.replenishment import chronological_losses


def allocate(items: list[dict], budget: Decimal | None) -> dict[str, int]:
    allocation = {item["product_id"]: 0 for item in items}
    if budget is None:
        return {item["product_id"]: item["requested_units"] for item in items}
    if budget < 0:
        raise ValueError("Budget cannot be negative")
    remaining = budget
    loss_cache: dict[tuple[str, int], float] = {}

    def expected_loss(item: dict, units: int) -> float:
        key = (item["product_id"], units)
        if key not in loss_cache:
            losses = chronological_losses(
                item["paths"], item["available"], item["arrivals"], units, item["lead_time_days"]
            )
            loss_cache[key] = float(np.mean(losses))
        return loss_cache[key]

    while True:
        candidates = []
        for item in items:
            key = item["product_id"]
            units = allocation[key]
            pack = item["pack_size"]
            block = (
                pack if units else pack * math.ceil(max(pack, item["minimum_order_units"]) / pack)
            )
            cost = Decimal(item["unit_cost"]) * block
            if cost <= 0:
                raise ValueError("Budget allocation requires positive unit costs")
            if units + block > item["requested_units"] or cost > remaining:
                continue
            benefit = expected_loss(item, units) - expected_loss(item, units + block)
            if benefit > 0:
                candidates.append(
                    (benefit / float(cost), item.get("risk") or 0, item["sku"], key, block, cost)
                )
        if not candidates:
            return allocation
        selected = sorted(candidates, key=lambda x: (-x[0], -x[1], x[2]))[0]
        allocation[selected[3]] += selected[4]
        remaining -= selected[5]
