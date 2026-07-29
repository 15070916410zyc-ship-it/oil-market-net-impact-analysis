from __future__ import annotations

import unittest

import numpy as np
import pandas as pd

from src.crisis_warning import prepare_warning_features
from src.quick_analysis import (
    QUICK_ESTIMATION_TRADING_DAYS,
    automatic_estimation_window,
    build_channel_contribution_summary,
    build_quick_imf_summary,
    group_variables,
)


class QuickModeTests(unittest.TestCase):
    def test_automatic_window_is_contiguous_and_fixed_length(self) -> None:
        start, end = automatic_estimation_window("2024-01-08")
        self.assertEqual(end, pd.Timestamp("2024-01-05"))
        self.assertEqual(len(pd.bdate_range(start, end)), QUICK_ESTIMATION_TRADING_DAYS)

    def test_variables_are_grouped_once_across_five_channels(self) -> None:
        variables = ["OVX", "Brent", "Gasoline", "ShanghaiSC", "Copper", "Custom"]
        grouped = group_variables(variables)
        self.assertEqual(list(grouped), ["IMF1", "IMF2", "IMF3", "IMF4", "IMF5"])
        flattened = [item for values in grouped.values() for item in values]
        self.assertCountEqual(flattened, variables)
        self.assertEqual(grouped["IMF1"], ["OVX", "Custom"])

    def test_quick_imf_summary_uses_paper_interpretations(self) -> None:
        stats = pd.DataFrame({"Target": ["Brent"] * 5, "IMF": [f"IMF{i}" for i in range(1, 6)]})
        summary = build_quick_imf_summary(stats, "zh")
        self.assertEqual(summary["Channel"].tolist(), ["投机", "OPEC+ 产量公告", "库存", "供给", "需求"])

    def test_channel_contributions_are_complete_and_normalized(self) -> None:
        contribution = pd.DataFrame(
            {
                "Target": ["Brent", "Brent"],
                "ExternalVariable": ["OVX", "Copper"],
                "ExternalRelativeWeightPercent": [25.0, 75.0],
            }
        )
        summary = build_channel_contribution_summary(contribution, "en")
        self.assertEqual(len(summary), 5)
        self.assertAlmostEqual(float(summary["WeightPercent"].sum()), 100.0)


class WarningModeTests(unittest.TestCase):
    def test_warning_features_use_expanding_labels_and_h5_target(self) -> None:
        dates = pd.bdate_range("2015-01-01", periods=900)
        rng = np.random.default_rng(42)
        returns = rng.normal(0.0002, 0.012, len(dates))
        returns[700:720] += 0.045
        price = 60 * np.exp(np.cumsum(returns))
        data = pd.DataFrame(
            {
                "Date": dates,
                "Brent": price,
                "WTI": price * (1 + rng.normal(0, 0.01, len(dates))),
                "OVX": 30 + rng.normal(0, 3, len(dates)),
                "VIX": 20 + rng.normal(0, 2, len(dates)),
            }
        )
        frame, features, catalog = prepare_warning_features(data)
        self.assertIn("target_h5", frame.columns)
        self.assertIn("rv20", features)
        self.assertFalse(catalog.empty)


if __name__ == "__main__":
    unittest.main()
