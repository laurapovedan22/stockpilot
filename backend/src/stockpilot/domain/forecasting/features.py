import numpy as np
import pandas as pd


def feature_row(
    history: list[float], day: pd.Timestamp, product_code: int, origin: pd.Timestamp
) -> list[float]:
    """History stops at t-1, including during recursive prediction."""
    result = [
        float(product_code),
        float(day.dayofweek),
        float(day.month),
        float(day.dayofweek >= 5),
        float((day - origin).days),
    ]
    result += [history[-lag] for lag in (1, 7, 14, 28)]
    for window in (7, 28, 56):
        result.extend([float(np.mean(history[-window:])), float(np.std(history[-window:]))])
    return result


def training_rows(
    series: dict[str, pd.Series], codes: dict[str, int], origin: pd.Timestamp
) -> tuple[np.ndarray, np.ndarray]:
    features, targets = [], []
    for key, values in series.items():
        history = values.to_list()
        for position in range(56, len(history)):
            features.append(
                feature_row(history[:position], values.index[position], codes[key], origin)
            )
            targets.append(history[position])
    return np.asarray(features), np.asarray(targets)


def recursive(
    model, values: pd.Series, horizon: int, code: int, origin: pd.Timestamp
) -> np.ndarray:
    history = values.to_list()
    output = []
    for step in range(1, horizon + 1):
        day = values.index[-1] + pd.Timedelta(days=step)
        value = max(
            0.0, float(model.predict(np.asarray([feature_row(history, day, code, origin)]))[0])
        )
        output.append(value)
        history.append(value)
    return np.asarray(output)
