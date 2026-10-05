import numpy as np
import pandas as pd

from stockpilot.domain.forecasting.baselines import predict
from stockpilot.domain.forecasting.evaluation import choose_model, metrics
from stockpilot.domain.forecasting.features import feature_row, recursive, training_rows
from stockpilot.domain.forecasting.intervals import envelope, trajectories
from stockpilot.domain.forecasting.training import forecast


def test_seasonal_multihorizon_repeats_last_available_week():
    assert predict(np.arange(14), 21, "seasonal_naive").tolist() == list(range(7, 14)) * 3


def test_metrics_zero_denominator_and_weighted_aggregation():
    assert metrics(np.zeros(2), np.ones(2))["wape"] is None
    result = metrics(np.asarray([1, 100]), np.asarray([2, 100]))
    assert result["wape"] == 1 / 101
    assert result["bias"] == 1 / 101


def test_model_selection_never_accepts_test_metrics():
    validation = {"seasonal_naive": {"wape": 0.1, "mae": 1}, "xgboost": {"wape": 0.2, "mae": 0.8}}
    assert choose_model(validation) == "seasonal_naive"


def test_global_candidate_selection_is_independent_of_holdout_values():
    dates = pd.date_range("2022-01-01", periods=520)
    values = pd.Series(np.resize(np.arange(1, 8), 520), index=dates, dtype=float)
    changed = values.copy()
    changed.iloc[-28:] = 500
    first = forecast({"p": values}, 28)
    second = forecast({"p": changed}, 28)
    assert "xgboost" in first["metrics"]["validation"]
    assert first["model"] == second["model"]
    assert first["metrics"]["validation"] == second["metrics"]["validation"]
    assert first["metrics"]["test"] != second["metrics"]["test"]


def test_future_mutation_does_not_change_features_or_operational_forecast():
    dates = pd.date_range("2022-01-01", periods=520)
    values = pd.Series(np.resize(np.arange(1, 8), 520), index=dates, dtype=float)
    changed = values.copy()
    changed.iloc[400:] = 99999
    codes = {"p": 0}
    before = training_rows({"p": values.iloc[:400]}, codes, dates[0])
    after = training_rows({"p": changed.iloc[:400]}, codes, dates[0])
    np.testing.assert_array_equal(before[0], after[0])
    first = forecast({"p": values.iloc[:400]}, 28)
    second = forecast({"p": changed.iloc[:400]}, 28)
    np.testing.assert_array_equal(first["points"]["p"]["central"], second["points"]["p"]["central"])


def test_recursive_features_consume_previous_prediction():
    class EchoLag:
        def predict(self, x):
            return x[:, 5] + 1

    series = pd.Series(np.ones(80), index=pd.date_range("2024-01-01", periods=80))
    np.testing.assert_array_equal(recursive(EchoLag(), series, 3, 0, series.index[0]), [2, 3, 4])
    row = feature_row(list(range(56)), series.index[-1], 0, series.index[0])
    assert row[5:9] == [55, 49, 42, 28]


def test_signed_interval_envelope_and_block_reproducibility():
    central = np.arange(1, 29, dtype=float)
    residuals = np.tile(np.arange(1, 29), (3, 1))
    lower, upper = envelope(central, residuals)
    assert np.all(lower <= central)
    assert np.all(central <= upper)
    np.testing.assert_array_equal(
        trajectories(central, residuals, 42), trajectories(central, residuals, 42)
    )
    assert trajectories(central, np.ones(10), 42) is None
