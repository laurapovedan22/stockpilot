import hashlib
from datetime import date

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder
from xgboost import XGBRegressor

from stockpilot.domain.forecasting.baselines import predict
from stockpilot.domain.forecasting.evaluation import choose_model, metrics
from stockpilot.domain.forecasting.features import recursive, training_rows
from stockpilot.domain.forecasting.intervals import envelope, trajectories

MODELS = ("seasonal_naive", "moving_average", "xgboost")


def fit(series: dict[str, pd.Series], codes: dict[str, int], origin: pd.Timestamp, seed: int):
    x, y = training_rows(series, codes, origin)
    model = Pipeline(
        [
            (
                "encoding",
                ColumnTransformer(
                    [("product", OneHotEncoder(handle_unknown="ignore"), [0])],
                    remainder="passthrough",
                ),
            ),
            (
                "model",
                XGBRegressor(
                    n_estimators=100,
                    max_depth=3,
                    learning_rate=0.07,
                    objective="reg:squarederror",
                    random_state=seed,
                    n_jobs=1,
                ),
            ),
        ]
    )
    model.fit(x, y)
    return model


def forecast(series: dict[str, pd.Series], horizon: int, seed: int = 42) -> dict:
    if not series:
        raise ValueError("No eligible products")
    cutoff = min(value.index[-1] for value in series.values())
    series = {key: value.loc[:cutoff] for key, value in series.items()}
    codes = {key: i for i, key in enumerate(sorted(series))}
    origin = min(value.index[0] for value in series.values())
    enough = all(len(value) >= 477 for value in series.values())
    available = MODELS if enough else MODELS[:2]
    folds = []
    residual_store: dict[str, dict[str, list[np.ndarray]]] = {
        model: {key: [] for key in series} for model in available
    }
    actual_store: dict[str, list[np.ndarray]] = {model: [] for model in available}
    pred_store: dict[str, list[np.ndarray]] = {model: [] for model in available}
    test_start = cutoff - pd.Timedelta(days=27)
    for fold, weeks_back in enumerate((3, 2, 1), 1):
        start = test_start - pd.Timedelta(days=28 * weeks_back)
        train = {key: value.loc[: start - pd.Timedelta(days=1)] for key, value in series.items()}
        if min(len(value) for value in train.values()) < 365:
            continue
        fitted = fit(train, codes, origin, seed) if "xgboost" in available else None
        for model in available:
            actuals, predictions = [], []
            for key, values in train.items():
                actual = series[key].loc[start : start + pd.Timedelta(days=27)].to_numpy()
                predicted = (
                    recursive(fitted, values, 28, codes[key], origin)
                    if model == "xgboost"
                    else predict(values.to_numpy(), 28, model)
                )
                residual_store[model][key].append(actual - predicted)
                actuals.append(actual)
                predictions.append(predicted)
                folds.append(
                    {
                        "fold": str(fold),
                        "product_id": key,
                        "model": model,
                        "metrics": metrics(actual, predicted),
                        "start": start.date().isoformat(),
                        "end": (start + pd.Timedelta(days=27)).date().isoformat(),
                        "train_days": len(values),
                    }
                )
            actual_store[model].append(np.concatenate(actuals))
            pred_store[model].append(np.concatenate(predictions))
    validation = {
        model: metrics(np.concatenate(actual_store[model]), np.concatenate(pred_store[model]))
        for model in available
        if actual_store[model]
    }
    chosen = choose_model(validation) if validation else "moving_average"
    own_residuals = {key: np.asarray(rows) for key, rows in residual_store[chosen].items()}
    nonempty = [array for array in own_residuals.values() if array.size]
    pooled = np.concatenate(nonempty, axis=0) if nonempty else np.empty((0, 28))
    calibration = {key: rows if len(rows) >= 10 else pooled for key, rows in own_residuals.items()}
    test_metrics: dict = {}
    if min(len(value) for value in series.values()) >= 56:
        train_test = {
            key: value.loc[: test_start - pd.Timedelta(days=1)] for key, value in series.items()
        }
        fitted_test = fit(train_test, codes, origin, seed) if chosen == "xgboost" else None
        actuals, predictions, coverages = [], [], []
        for key, values in train_test.items():
            actual = series[key].loc[test_start:].to_numpy()
            predicted = (
                recursive(fitted_test, values, 28, codes[key], origin)
                if chosen == "xgboost"
                else predict(values.to_numpy(), 28, chosen)
            )
            actuals.append(actual)
            predictions.append(predicted)
            residuals = calibration[key]
            if residuals.size:
                test_lower, test_upper = envelope(predicted, residuals)
                coverages.extend(((actual >= test_lower) & (actual <= test_upper)).tolist())
            folds.append(
                {
                    "fold": "test",
                    "product_id": key,
                    "model": chosen,
                    "metrics": metrics(actual, predicted),
                    "start": test_start.date().isoformat(),
                    "end": cutoff.date().isoformat(),
                    "train_days": len(values),
                }
            )
        test_metrics = metrics(np.concatenate(actuals), np.concatenate(predictions))
        test_metrics["coverage_90"] = float(np.mean(coverages)) if coverages else None
    fitted_operational = fit(series, codes, origin, seed) if chosen == "xgboost" else None
    points, paths = {}, {}
    for key, values in series.items():
        central = (
            recursive(fitted_operational, values, horizon, codes[key], origin)
            if chosen == "xgboost"
            else predict(values.to_numpy(), horizon, chosen)
        )
        residuals = calibration[key]
        lower, upper = envelope(central, residuals) if residuals.size else (None, None)
        path_residuals = own_residuals[key] if own_residuals[key].size >= 28 else pooled
        paths[key] = (
            trajectories(central, path_residuals, seed + codes[key])
            if path_residuals.size
            else None
        )
        points[key] = {"central": central, "lower": lower, "upper": upper}
    digest = hashlib.sha256()
    for key in sorted(series):
        digest.update(key.encode())
        digest.update(series[key].to_csv().encode())
    return {
        "model": chosen,
        "points": points,
        "paths": paths,
        "folds": folds,
        "metrics": {
            "validation": validation,
            "test": test_metrics,
            "calibration_samples_per_product": {k: int(v.size) for k, v in calibration.items()},
            "calibration_scope": {
                k: "product" if len(own_residuals[k]) >= 10 else "grouped" for k in series
            },
            "warnings": []
            if enough
            else ["Insufficient history for global candidate; baselines only"],
            "interval_method": "Signed horizon residual quantiles (product with >=10 sequences, grouped otherwise), central envelope; seven-day product blocks with grouped fallback",
        },
        "checksum": digest.hexdigest(),
        "operation_model": fitted_operational,
        "evaluation_model": locals().get("fitted_test"),
        "cutoff": date.fromisoformat(cutoff.date().isoformat()),
    }
