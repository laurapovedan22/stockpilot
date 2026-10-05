from decimal import Decimal

import numpy as np
import pandas as pd

from stockpilot.domain.forecasting.baselines import predict
from stockpilot.domain.forecasting.training import forecast
from stockpilot.domain.inventory.simulation import simulate


def historical_backtest(
    series: dict[str, pd.Series],
    items: list[dict],
    horizon: int = 28,
    budget: Decimal | None = None,
) -> dict:
    """Rolling baselines with frozen operation snapshots. Forecast each review using t-1."""
    if horizon > 56 or horizon < 7:
        raise ValueError("Backtest horizon must be 7–56 days")
    if not series or not items or any(value.empty for value in series.values()):
        raise ValueError("Backtest requires products with non-empty historical demand")
    if any(item["product_id"] not in series for item in items):
        raise ValueError("Every backtest product requires a historical demand series")
    end = min(value.index[-1] for value in series.values())
    start = end - pd.Timedelta(days=horizon - 1)
    selected = []
    for item in items:
        observed = series[item["product_id"]].loc[start:end].to_numpy()
        history = series[item["product_id"]].loc[: start - pd.Timedelta(days=1)]
        if len(history) < 365 or len(observed) != horizon:
            raise ValueError("Insufficient historical backtest coverage")
        # Simulator's policy uses a forecast tape frozen before every day's demand.
        tape: list[float] = []
        for day in range(0, horizon, 7):
            review = start + pd.Timedelta(days=day)
            before = series[item["product_id"]].loc[: review - pd.Timedelta(days=1)].to_numpy()
            tape.extend(predict(before, min(7, horizon - day), "seasonal_naive"))
        selected.append(
            {
                **item,
                "central": np.asarray(tape),
                "paths": np.tile(observed, (1, 1)),
                "moving_average": float(history.iloc[-28:].mean()),
            }
        )
    rolling = {}
    manifests = []
    for day in range(1, horizon + 1, 7):
        cutoff = start + pd.Timedelta(days=day - 2)
        past = {key: value.loc[:cutoff] for key, value in series.items()}
        result = forecast(past, 42)
        rolling[day] = {
            key: {**result["points"][key], "paths": result["paths"][key]} for key in past
        }
        manifests.append(
            {
                "review_day": day,
                "cutoff": cutoff.date().isoformat(),
                "selected_model": result["model"],
                "checksum": result["checksum"],
            }
        )
    result = simulate(
        selected,
        1,
        0,
        horizon,
        0.95,
        budget,
        historical=True,
        series=series,
        start=start,
        rolling=rolling,
    )
    result["rolling_manifests"] = manifests
    return result
