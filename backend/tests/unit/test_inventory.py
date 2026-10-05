from decimal import Decimal

import numpy as np
import pytest

from stockpilot.domain.inventory.allocation import allocate
from stockpilot.domain.inventory.replenishment import (
    arrival_risk,
    chronological_losses,
    purchase,
    recommend,
)
from stockpilot.domain.inventory.simulation import simulate


def item():
    return {
        "product_id": "p",
        "sku": "00001",
        "on_hand": 30,
        "reserved": 5,
        "unit_cost": "2.50",
        "pack_size": 12,
        "minimum_order_units": 24,
        "lead_time_days": 3,
        "holding_cost": ".01",
        "stockout_penalty": "2",
        "paths": np.full((3, 42), 10.0),
        "central": np.full(42, 10.0),
        "arrivals": {5: 20},
        "moving_average": 10,
    }


def test_contractual_example_and_zero_with_moq():
    result = purchase(100, 30, 5, 20, 12, 24, Decimal("2.50"))
    assert result["position"] == 45
    assert result["raw"] == 55
    assert result["requested_units"] == 60
    assert result["cost"] == "150.00"
    assert purchase(40, 30, 5, 20, 12, 24, Decimal("2.50"))["requested_units"] == 0


def test_horizon_insufficient_late_inbound_and_risk():
    i = item()
    with pytest.raises(ValueError, match="horizon"):
        recommend(i["paths"][:, :3], i["central"][:3], i, {}, 0.95)
    result = recommend(i["paths"], i["central"], i, {20: 1000}, 0.95)
    assert result["eligible_inbound"] == 0
    assert result["risk"] == 1
    late = recommend(i["paths"], i["central"], i, {8: 1000}, 0.95)
    assert late["requested_units"] == 0
    assert late["arrival_warning"] is True
    assert late["first_arrival_day"] == 8
    assert late["risk_before_first_arrival"] == 1


def test_arrival_risk_reflects_allocated_purchase_or_no_inbound():
    paths = np.full((3, 10), 10.0)
    first, risk = arrival_risk(paths, 25, {8: 100}, 0, 3, 10)
    assert first == 8 and risk == 1
    first, risk = arrival_risk(paths, 25, {8: 100}, 60, 3, 10)
    assert first == 3 and risk == 0
    first, risk = arrival_risk(paths, 25, {}, 0, 3, 10)
    assert first is None and risk == 1


def test_budget_zero_unaffordable_moq_and_decimal_invariant():
    i = item()
    i.update(available=25, requested_units=96, risk=1)
    assert allocate([i], Decimal(0))["p"] == 0
    assert allocate([i], Decimal("59.99"))["p"] == 0
    units = allocate([i], Decimal("75.00"))["p"]
    assert Decimal(units) * Decimal(i["unit_cost"]) <= Decimal("75.00")
    assert units % 12 == 0


def test_exact_arrivals_conservation_no_negative_and_identical_demand():
    i = item()
    first = simulate([i], 1.2, 2, 14, 0.95, Decimal("200"))
    second = simulate([i], 1.2, 2, 14, 0.95, Decimal("200"))
    assert first == second
    demand = None
    for policy, output in first["policies"].items():
        rows = output["daily"]
        assert all(r["stock"] >= 0 and r["demand"] == r["served"] + r["lost"] for r in rows)
        current = [r["demand"] for r in rows]
        if demand is None:
            demand = current
        assert current == demand
        if policy == "no_purchase":
            served = sum(r["served"] for r in rows)
            assert 25 + 20 == served + rows[-1]["stock"]
            assert rows[5]["stock"] == 0  # inbound delayed from day 5 to day 7
    loss = chronological_losses(np.full((1, 3), 10.0), 0, {3: 20})
    assert loss[0] == 20


def test_zero_demand_fill_rate_is_null_and_final_pipeline_kept():
    i = item()
    i.update(paths=np.zeros((1, 42)), central=np.zeros(42), moving_average=0, arrivals={30: 100})
    result = simulate([i], 1, 0, 14, 0.95, None)
    assert result["policies"]["no_purchase"]["metrics"]["fill_rate"] is None
    assert result["policies"]["no_purchase"]["metrics"]["final_pipeline"]["mean"] == 100
