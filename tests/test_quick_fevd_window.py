"""Regression tests for quick-mode rolling FEVD window selection."""

from __future__ import annotations

import unittest

import pandas as pd
from unittest.mock import patch

from src.paper_replication import (
    PAPER_ROLLING_WINDOW,
    _resolve_fevd_rolling_window,
    _rolling_var_fevd,
)


class QuickFevdWindowTests(unittest.TestCase):
    def test_quick_estimation_window_is_not_clipped_to_local_cache(self) -> None:
        from app import streamlit_app as app

        start, end = app.requested_quick_estimation_window("2024-01-02")

        self.assertEqual(end, pd.Timestamp("2024-01-01"))
        self.assertEqual(len(pd.bdate_range(start, end)), app.QUICK_ESTIMATION_TRADING_DAYS)
        self.assertLess(start, pd.Timestamp("2024-01-02"))

    def test_professional_mode_keeps_fixed_paper_window(self) -> None:
        dates = pd.Series(pd.bdate_range("2024-01-01", periods=100))

        actual = _resolve_fevd_rolling_window(
            dates,
            event_start=dates.iloc[90],
            event_end=dates.iloc[-1],
            lag=2,
            n_vars=13,
            adaptive=False,
        )

        self.assertEqual(actual, PAPER_ROLLING_WINDOW)

    def test_quick_mode_uses_longest_feasible_window_at_event_start(self) -> None:
        dates = pd.Series(pd.bdate_range("2024-01-01", periods=100))

        actual = _resolve_fevd_rolling_window(
            dates,
            event_start=dates.iloc[90],
            event_end=dates.iloc[-1],
            lag=2,
            n_vars=13,
            adaptive=True,
        )

        self.assertEqual(actual, 91)

    def test_quick_mode_does_not_expand_beyond_paper_window(self) -> None:
        dates = pd.Series(pd.bdate_range("2024-01-01", periods=180))

        actual = _resolve_fevd_rolling_window(
            dates,
            event_start=dates.iloc[150],
            event_end=dates.iloc[-1],
            lag=2,
            n_vars=13,
            adaptive=True,
        )

        self.assertEqual(actual, PAPER_ROLLING_WINDOW)

    def test_quick_mode_reports_actionable_shortfall(self) -> None:
        dates = pd.Series(pd.bdate_range("2024-01-01", periods=18))

        with self.assertRaisesRegex(ValueError, "too few aligned observations"):
            _resolve_fevd_rolling_window(
                dates,
                event_start=dates.iloc[10],
                event_end=dates.iloc[-1],
                lag=2,
                n_vars=13,
                adaptive=True,
            )

    def test_adaptive_window_produces_every_event_date(self) -> None:
        dates = pd.Series(pd.bdate_range("2024-01-01", periods=100))
        values = pd.DataFrame(
            {
                "target": range(100),
                "driver": [value * 0.5 + (value % 7) for value in range(100)],
            }
        ).to_numpy(dtype=float)
        event_start = dates.iloc[90]
        event_end = dates.iloc[-1]
        rolling_window = _resolve_fevd_rolling_window(
            dates,
            event_start=event_start,
            event_end=event_end,
            lag=1,
            n_vars=2,
            adaptive=True,
        )

        result_dates, _ = _rolling_var_fevd(
            dates,
            values,
            lag=1,
            rolling_window=rolling_window,
            horizon=3,
            event_start=event_start,
            event_end=event_end,
        )

        self.assertEqual(result_dates.tolist(), dates.iloc[90:].tolist())

    def test_quick_quality_filter_drops_low_coverage_variable(self) -> None:
        from app import streamlit_app as app

        quality = pd.DataFrame(
            {
                "Variable": ["OVX", "CrudeStocks"],
                "Coverage": [0.95, 0.2053],
                "Action": ["Kept", "Kept"],
            }
        )
        with patch.object(app, "load_excel_if_exists", return_value=quality):
            kept, dropped = app.quality_filtered_explanatory_variables(
                ["OVX", "CrudeStocks"],
                ["Brent"],
                minimum_coverage=0.60,
            )

        self.assertEqual(kept, ["OVX"])
        self.assertEqual(dropped, ["CrudeStocks"])

    def test_pool_quality_filter_can_enforce_coverage_only_for_quick_mode(self) -> None:
        from src.variable_pool import quality_filter_variables

        data = pd.DataFrame(
            {
                "Date": pd.bdate_range("2024-01-01", periods=10),
                "Sparse": [1.0, 2.0, None, None, None, None, None, None, None, None],
            }
        )
        professional_kept, _ = quality_filter_variables(
            data,
            ["Sparse"],
            min_coverage=0.60,
            max_stale_days=3650,
            drop_below_coverage=False,
        )
        quick_kept, quick_report = quality_filter_variables(
            data,
            ["Sparse"],
            min_coverage=0.60,
            max_stale_days=3650,
            drop_below_coverage=True,
        )

        self.assertEqual(professional_kept, ["Sparse"])
        self.assertEqual(quick_kept, [])
        self.assertEqual(quick_report.loc[0, "Action"], "Dropped_quality_filter")
        self.assertIn("coverage_below_threshold", quick_report.loc[0, "Reason"])


if __name__ == "__main__":
    unittest.main()
