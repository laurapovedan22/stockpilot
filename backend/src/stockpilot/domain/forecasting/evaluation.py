import numpy as np


def metrics(actual: np.ndarray, predicted: np.ndarray) -> dict:
    error = predicted - actual
    denominator = float(actual.sum())
    return {
        "mae": float(np.mean(np.abs(error))),
        "rmse": float(np.sqrt(np.mean(error**2))),
        "wape": float(np.abs(error).sum() / denominator) if denominator else None,
        "bias": float(error.sum() / denominator) if denominator else None,
        "denominator": denominator,
        "absolute_error": float(np.abs(error).sum()),
        "null_reason": None if denominator else "Total observed demand is zero",
    }


def choose_model(validation: dict[str, dict]) -> str:
    return min(
        validation,
        key=lambda key: (
            validation[key]["wape"] if validation[key]["wape"] is not None else float("inf"),
            validation[key]["mae"],
            key,
        ),
    )
