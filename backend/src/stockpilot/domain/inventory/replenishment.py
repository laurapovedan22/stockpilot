import math
from decimal import Decimal

import numpy as np


def purchase(
    target: float, on_hand: int, reserved: int, inbound: int, pack: int, moq: int, cost: Decimal
) -> dict:
    if reserved > on_hand or min(reserved, on_hand, inbound, moq) < 0 or pack < 1:
        raise ValueError("Invalid inventory")
    available = on_hand - reserved
    position = available + inbound
    raw = max(0, math.ceil(target - position))
    units = pack * math.ceil(max(raw, moq) / pack) if raw else 0
    if units > 2**31 - 1:
        raise ValueError("Requested purchase exceeds supported 32-bit units")
    return {
        "target": target,
        "on_hand": on_hand,
        "reserved": reserved,
        "available": available,
        "eligible_inbound": inbound,
        "position": position,
        "raw": raw,
        "pack_size": pack,
        "minimum_order_units": moq,
        "requested_units": units,
        "unit_cost": str(cost),
        "cost": str((units * cost).quantize(Decimal("0.01"))),
    }


def chronological_losses(
    paths: np.ndarray, available: int, arrivals: dict[int, int], units: int = 0, lead: int = 1
) -> np.ndarray:
    stock = np.full(len(paths), float(available))
    lost = np.zeros(len(paths))
    for day in range(paths.shape[1]):
        stock += arrivals.get(day + 1, 0) + (units if day + 1 == lead else 0)
        demand = np.floor(paths[:, day] + 0.5)
        served = np.minimum(stock, demand)
        lost += demand - served
        stock -= served
    return lost


def arrival_risk(
    paths: np.ndarray, available: int, arrivals: dict[int, int], units: int, lead: int, period: int
) -> tuple[int | None, float]:
    pending_days = [
        day for day, quantity in arrivals.items() if quantity > 0 and 1 <= day <= period
    ]
    if units > 0:
        pending_days.append(lead)
    first = min(pending_days) if pending_days else None
    before = min(period, first - 1) if first is not None else period
    losses = chronological_losses(paths[:, :before], available, arrivals)
    return first, float(np.mean(losses > 0))


def recommend(
    paths: np.ndarray | None,
    central: np.ndarray,
    item: dict,
    arrivals: dict[int, int],
    service: float,
    review: int = 7,
) -> dict:
    period = item["lead_time_days"] + review
    if period > len(central):
        raise ValueError(f"Protection period {period} exceeds forecast horizon {len(central)}")
    target = (
        float(np.quantile(paths[:, :period].sum(axis=1), service))
        if paths is not None
        else float(central[:period].sum() * 1.15)
    )
    eligible = sum(units for day, units in arrivals.items() if 1 <= day <= period)
    result = purchase(
        target,
        item["on_hand"],
        item["reserved"],
        eligible,
        item["pack_size"],
        item["minimum_order_units"],
        Decimal(item["unit_cost"]),
    )
    result.update(
        {
            "lead_time_days": item["lead_time_days"],
            "review_days": review,
            "protection_days": period,
            "service_level": service,
            "method": "empirical trajectories"
            if paths is not None
            else "deterministic 15% buffer; risk unavailable",
            "trajectory_count": len(paths) if paths is not None else 0,
        }
    )
    if paths is not None:
        loss = chronological_losses(paths[:, :period], result["available"], arrivals)
        after = chronological_losses(
            paths[:, :period],
            result["available"],
            arrivals,
            result["requested_units"],
            item["lead_time_days"],
        )
        first_arrival, before_arrival = arrival_risk(
            paths,
            result["available"],
            arrivals,
            result["requested_units"],
            item["lead_time_days"],
            period,
        )
        result.update(
            {
                "risk": float(np.mean(loss > 0)),
                "risk_after": float(np.mean(after > 0)),
                "expected_lost_units": float(np.mean(loss)),
                "first_arrival_day": first_arrival,
                "risk_before_first_arrival": before_arrival,
                "arrival_warning": before_arrival > 0,
            }
        )
    else:
        result.update({"risk": None, "risk_after": None, "arrival_warning": None})
    return result
