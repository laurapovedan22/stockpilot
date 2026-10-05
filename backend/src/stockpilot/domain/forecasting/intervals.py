import numpy as np


def trajectories(
    central: np.ndarray, residuals: np.ndarray, seed: int, count: int = 200
) -> np.ndarray | None:
    if residuals.size < 28:
        return None
    rng = np.random.default_rng(seed)
    blocks = [
        row[start : start + 7]
        for row in np.atleast_2d(residuals)
        for start in range(0, len(row) - 6)
    ]
    if not blocks:
        return None
    error = np.concatenate(
        [
            np.asarray(blocks)[rng.integers(0, len(blocks), count)]
            for _ in range((len(central) + 6) // 7)
        ],
        axis=1,
    )[:, : len(central)]
    return np.maximum(0, central[None, :] + error)


def envelope(central: np.ndarray, residuals: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    lower, upper = np.quantile(residuals, [0.05, 0.95], axis=0)
    lower = np.resize(lower, len(central))
    upper = np.resize(upper, len(central))
    return np.maximum(0, np.minimum(central, central + lower)), np.maximum(central, central + upper)
