from __future__ import annotations

import inspect
from types import SimpleNamespace

import numpy as np
import pandas as pd

from app import executive_dashboard as dashboard
from src.price_forecast import _split_conformal_radius, run_brent_price_forecast


def _synthetic_brent(rows: int = 240) -> pd.DataFrame:
    dates = pd.bdate_range("2025-01-02", periods=rows)
    x = np.arange(rows, dtype=float)
    values = 78.0 + 0.018 * x + 2.0 * np.sin(x / 15.0) + 0.55 * np.sin(x / 3.1)
    return pd.DataFrame({"Date": dates, "Brent": values})


def test_interval_calibration_and_evaluation_are_reported_separately() -> None:
    result = run_brent_price_forecast(_synthetic_brent(), horizon=10, max_history=240)
    metrics = result.metrics

    assert metrics["CalibrationObservations"] == 20
    assert metrics["ValidationObservations"] == 20
    assert metrics["PredictionIntervalMethod"] == "chronological split calibration and evaluation"
    assert metrics["ValidationStartDate"] <= metrics["ValidationEndDate"]
    coverages = [float(metrics[f"ValidationCoverage{level}Percent"]) for level in (50, 80, 95)]
    assert all(0.0 <= value <= 100.0 for value in coverages)
    assert coverages == sorted(coverages)
    assert np.isfinite(float(metrics["ValidationSkillPercent"]))


def test_split_conformal_radius_uses_finite_sample_order_statistic() -> None:
    errors = np.array([1.0, -2.0, 4.0, np.nan])

    assert _split_conformal_radius(errors, 50) == 2.0
    assert _split_conformal_radius(errors, 95) == 4.0


def test_monthly_chart_ends_observed_path_on_true_as_of_date() -> None:
    history = pd.DataFrame(
        {
            "Date": pd.to_datetime(["2026-07-31", "2026-08-12", "2026-08-14"]),
            "Actual": [91.0, 92.0, 93.0],
        }
    )
    forecast = pd.DataFrame(
        {
            "Date": pd.to_datetime(["2026-08-17", "2026-08-31"]),
            "PointForecast": [93.5, 94.0],
            "Lower50": [92.0, 92.5],
            "Upper50": [95.0, 95.5],
            "Lower80": [90.0, 90.5],
            "Upper80": [97.0, 97.5],
            "Lower95": [88.0, 88.5],
            "Upper95": [99.0, 99.5],
        }
    )
    result = SimpleNamespace(
        history=history,
        forecast=forecast,
        metrics={"AsOfDate": "2026-08-14"},
    )

    figure = dashboard._main_forecast_figure(result, "monthly", lambda _en, zh: zh)
    traces = {trace.name: trace for trace in figure.data if trace.name}

    assert pd.Timestamp(traces["实际价格"].x[-1]) == pd.Timestamp("2026-08-14")
    assert pd.Timestamp(traces["多层波动合成预测"].x[0]) == pd.Timestamp("2026-08-14")
    assert {"50%经验区间", "80%经验区间", "95%经验区间"}.issubset(traces)


def test_slider_defaults_are_clamped_and_aligned_to_step() -> None:
    assert dashboard._quantize_slider_default(0.46) == 0.45
    assert dashboard._quantize_slider_default(0.98) == 1.0
    for raw in (-0.2, 0.03, 0.46, 0.98, 1.3):
        value = dashboard._quantize_slider_default(raw)
        assert 0.0 <= value <= 1.0
        assert np.isclose(value / 0.05, round(value / 0.05))


def test_refresh_is_one_shot_and_legacy_renderer_is_removed() -> None:
    renderer = inspect.getsource(dashboard.render_decision_dashboard)
    cache_loader = inspect.getsource(dashboard._cached_price_bundle)

    assert "story_data_revision" in renderer
    assert "_force_refresh=bool(refresh)" in renderer
    assert "story_refresh_token" in renderer  # Old browser state is explicitly discarded.
    assert "refresh_token > 0" not in renderer + cache_loader
    assert not hasattr(dashboard, "_render_legacy_decision_dashboard")


def test_procurement_story_connects_full_cost_and_policy_comparison() -> None:
    renderer = inspect.getsource(dashboard.render_decision_dashboard)

    for key in (
        "story_quality_differential",
        "story_freight",
        "story_taxes",
        "story_other_unit_cost",
        "story_option_style",
        "story_variation_margin_days",
    ):
        assert key in renderer
    assert "compare_buyer_hedge_strategies(" in renderer
    assert "_strategy_comparison_figure" in renderer
    assert "_liquidity_stress_figure" in renderer
    assert "_cost_waterfall_figure" in renderer
