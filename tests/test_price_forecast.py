from __future__ import annotations

import numpy as np
import pandas as pd
import unittest

from src.price_forecast import (
    PREDICTION_INTERVAL_LEVELS,
    run_brent_price_forecast,
    run_oil_price_forecast,
)


def synthetic_brent(rows: int = 420) -> pd.DataFrame:
    dates = pd.bdate_range("2024-01-02", periods=rows)
    x = np.arange(rows, dtype=float)
    price = 76.0 + 0.025 * x + 2.4 * np.sin(x / 17.0) + 0.7 * np.sin(x / 3.2)
    return pd.DataFrame({"Date": dates, "Brent": price})


def synthetic_wti(rows: int = 420) -> pd.DataFrame:
    data = synthetic_brent(rows).rename(columns={"Brent": "WTI"})
    data["WTI"] = data["WTI"] - 4.25
    return data


class PriceForecastTests(unittest.TestCase):
    def test_forecast_returns_five_imfs_and_requested_horizon(self) -> None:
        result = run_brent_price_forecast(synthetic_brent(), horizon=10, max_history=420)

        self.assertEqual(len(result.forecast), 10)
        expected_columns = ["Date", "PointForecast"] + [
            f"{bound}{level}"
            for level in PREDICTION_INTERVAL_LEVELS
            for bound in ("Lower", "Upper")
        ]
        self.assertEqual(list(result.forecast.columns), expected_columns)
        self.assertTrue(result.forecast[expected_columns[1:]].notna().all().all())
        for level in PREDICTION_INTERVAL_LEVELS:
            self.assertTrue((result.forecast[f"Lower{level}"] < result.forecast[f"Upper{level}"]).all())
            self.assertTrue((result.forecast[f"Lower{level}"] <= result.forecast["PointForecast"]).all())
            self.assertTrue((result.forecast["PointForecast"] <= result.forecast[f"Upper{level}"]).all())
        for narrower, wider in zip(PREDICTION_INTERVAL_LEVELS, PREDICTION_INTERVAL_LEVELS[1:]):
            self.assertTrue(
                (result.forecast[f"Lower{wider}"] <= result.forecast[f"Lower{narrower}"]).all()
            )
            self.assertTrue(
                (result.forecast[f"Upper{narrower}"] <= result.forecast[f"Upper{wider}"]).all()
            )
        self.assertEqual(result.model_summary["IMF"].tolist(), ["IMF1", "IMF2", "IMF3", "IMF4", "IMF5"])
        self.assertEqual(result.model_summary.loc[0, "Model"], "BPNN")
        self.assertEqual(set(result.model_summary.loc[1:, "Model"]), {"AR-Ridge"})
        self.assertEqual(result.components["Date"].nunique(), 10)
        self.assertEqual(len(result.components), 50)

    def test_validation_metrics_are_finite_and_future_dates_follow_history(self) -> None:
        result = run_brent_price_forecast(synthetic_brent(), horizon=5, max_history=360)

        self.assertGreaterEqual(float(result.metrics["ValidationMAE"]), 0)
        self.assertGreaterEqual(float(result.metrics["ValidationRMSE"]), 0)
        self.assertGreaterEqual(float(result.metrics["DirectionalAccuracyPercent"]), 0)
        self.assertLessEqual(float(result.metrics["DirectionalAccuracyPercent"]), 100)
        self.assertGreater(result.forecast["Date"].min(), result.history["Date"].max())

    def test_forecast_rejects_short_series(self) -> None:
        with self.assertRaisesRegex(ValueError, "180"):
            run_brent_price_forecast(synthetic_brent(120), horizon=5)

    def test_generic_forecast_supports_wti_target(self) -> None:
        result = run_oil_price_forecast(
            synthetic_wti(), price_column="WTI", horizon=5, max_history=360
        )

        self.assertEqual(result.metrics["Target"], "WTI")
        self.assertEqual(len(result.forecast), 5)
        self.assertEqual(result.history.columns.tolist(), ["Date", "Actual"])
