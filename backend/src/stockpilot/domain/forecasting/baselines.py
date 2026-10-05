import numpy as np


def predict(values: np.ndarray, horizon: int, model: str) -> np.ndarray:
    if len(values) == 0:
        raise ValueError("No observed demand")
    if model == "seasonal_naive":
        return np.resize(values[-7:], horizon).astype(float)
    if model == "moving_average":
        return np.full(horizon, np.mean(values[-28:]))
    raise ValueError("Unknown baseline")
