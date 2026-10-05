import math
from decimal import Decimal

import numpy as np

from stockpilot.domain.inventory.allocation import allocate
from stockpilot.domain.inventory.replenishment import chronological_losses

POLICIES = ("no_purchase", "moving_average", "selected_model")


def simulate(
    items: list[dict],
    demand_multiplier: float,
    delay: int,
    horizon: int,
    service: float,
    budget: Decimal | None,
    review: int = 7,
    historical: bool = False,
    series: dict | None = None,
    start=None,
    rolling: dict | None = None,
) -> dict:
    """Identical rounded demand per path/policy. Arrival, review, demand, holding."""
    if not items or horizon < 1 or review < 1:
        raise ValueError("Simulation requires products and positive horizon/review")
    if historical and (series is None or start is None):
        raise ValueError("Historical simulation requires dated observed histories")
    for item in items:
        if (
            item["paths"] is None
            or item["paths"].ndim != 2
            or item["paths"].shape[1] < horizon
            or len(item["paths"]) == 0
        ):
            raise ValueError("Demand trajectories do not cover the simulation horizon")
        if not np.all(np.isfinite(item["paths"])) or np.any(item["paths"] < 0):
            raise ValueError("Demand trajectories must be finite and non-negative")
        if item["on_hand"] < item["reserved"]:
            raise ValueError("Reserved inventory exceeds on-hand units")
    count = min(len(item["paths"]) for item in items)
    result = {}
    for policy in POLICIES:
        totals, representative = [], []
        for trajectory in range(count):
            stocks = {i["product_id"]: i["on_hand"] - i["reserved"] for i in items}
            pipeline = {
                i["product_id"]: {day + delay: units for day, units in i["arrivals"].items()}
                for i in items
            }
            served_total = demand_total = lost_total = stock_total = stockout_days = 0.0
            purchase_cost = holding_cost = penalty = Decimal(0)
            for day in range(1, horizon + 1):
                opening = dict(stocks)
                received = {i["product_id"]: 0 for i in items}
                purchased = {i["product_id"]: 0 for i in items}
                for item in items:
                    key = item["product_id"]
                    received[key] = pipeline[key].pop(day, 0)
                    stocks[key] += received[key]
                if (day - 1) % review == 0 and policy != "no_purchase":
                    candidates = []
                    for item in items:
                        key = item["product_id"]
                        lead = item["lead_time_days"] + delay
                        period = lead + review
                        offset = day - 1
                        if historical:
                            assert series is not None
                            import pandas as pd

                            from stockpilot.domain.forecasting.baselines import predict

                            before = (
                                series[key].loc[: start + pd.Timedelta(days=day - 2)].to_numpy()
                            )
                            if policy == "selected_model" and rolling is not None:
                                prediction = rolling[day][key]
                                future = prediction["central"][:period]
                                calibrated = (
                                    prediction["paths"][:, :period]
                                    if prediction["paths"] is not None
                                    else np.tile(future, (200, 1))
                                )
                            else:
                                future = predict(before, period, "moving_average")
                                calibrated = np.tile(future, (200, 1))
                        else:
                            forecast = (
                                item["central"]
                                if policy == "selected_model"
                                else np.full(len(item["central"]), item["moving_average"])
                            )
                            positions = np.minimum(
                                np.arange(offset, offset + period), len(forecast) - 1
                            )
                            future = forecast[positions] * demand_multiplier
                            calibrated = (
                                item["paths"][:, positions] * demand_multiplier
                                if policy == "selected_model"
                                else np.tile(future, (count, 1))
                            )
                        target = float(np.quantile(calibrated.sum(axis=1), service))
                        inbound = sum(
                            u for arrival, u in pipeline[key].items() if arrival <= day + period - 1
                        )
                        raw = max(0, math.ceil(target - stocks[key] - inbound))
                        units = (
                            item["pack_size"]
                            * math.ceil(max(raw, item["minimum_order_units"]) / item["pack_size"])
                            if raw
                            else 0
                        )
                        arrivals = {arrival - day + 1: u for arrival, u in pipeline[key].items()}
                        risk = float(
                            np.mean(chronological_losses(calibrated, stocks[key], arrivals) > 0)
                        )
                        candidates.append(
                            {
                                **item,
                                "available": stocks[key],
                                "requested_units": units,
                                "lead_time_days": lead + 1,
                                "arrivals": arrivals,
                                "paths": calibrated,
                                "risk": risk,
                            }
                        )
                    allocations = allocate(candidates, budget)
                    for item in items:
                        key = item["product_id"]
                        quantity = allocations[key]
                        if quantity:
                            purchased[key] = quantity
                            arrival = day + item["lead_time_days"] + delay
                            pipeline[key][arrival] = pipeline[key].get(arrival, 0) + quantity
                            purchase_cost += Decimal(item["unit_cost"]) * quantity
                for item in items:
                    key = item["product_id"]
                    demand = int(
                        np.floor(item["paths"][trajectory, day - 1] * demand_multiplier + 0.5)
                    )
                    served = min(stocks[key], demand)
                    lost = demand - served
                    stocks[key] -= served
                    daily_holding = Decimal(item["holding_cost"]) * stocks[key]
                    daily_penalty = Decimal(item["stockout_penalty"]) * lost
                    served_total += served
                    demand_total += demand
                    lost_total += lost
                    stock_total += stocks[key]
                    stockout_days += int(lost > 0)
                    holding_cost += daily_holding
                    penalty += daily_penalty
                    if trajectory == 0:
                        representative.append(
                            {
                                "product_id": key,
                                "day": day,
                                "demand": demand,
                                "served": served,
                                "lost": lost,
                                "stock": stocks[key],
                                "opening_stock": opening[key],
                                "received_units": received[key],
                                "purchased_units": purchased[key],
                                "pipeline_units": sum(pipeline[key].values()),
                                "purchase_cost": str(Decimal(item["unit_cost"]) * purchased[key]),
                                "holding_cost": str(daily_holding),
                                "penalty": str(daily_penalty),
                            }
                        )
            totals.append(
                {
                    "fill_rate": served_total / demand_total if demand_total else None,
                    "lost_units": lost_total,
                    "stockout_product_days": stockout_days,
                    "average_stock": stock_total / horizon / len(items),
                    "purchase_cost": float(purchase_cost),
                    "holding_cost": float(holding_cost),
                    "loss_penalty": float(penalty),
                    "operating_cost": float(holding_cost + penalty),
                    "final_stock": sum(stocks.values()),
                    "final_pipeline": sum(sum(p.values()) for p in pipeline.values()),
                }
            )
        summary = {}
        for metric in totals[0]:
            values = [row[metric] for row in totals if row[metric] is not None]
            summary[metric] = (
                {
                    "mean": float(np.mean(values)),
                    "p10": float(np.quantile(values, 0.1)),
                    "p90": float(np.quantile(values, 0.9)),
                }
                if values
                else None
            )
        result[policy] = {"metrics": summary, "daily": representative}
    return {
        "policies": result,
        "trajectory_count": count,
        "assumptions": [
            "Historical sales proxy with simulated operations; rolling-origin model selection at each review"
            if historical
            else "Projected/simulated, not observed losses",
            "Forecast beyond available horizon holds final daily value constant",
            "Demand rounds half up",
            "Delay affects inbound and new orders",
            "Budget applies per review",
            "Daily records show trajectory 0",
            "Purchase costs reported separately; terminal inventory retains value",
        ],
    }
