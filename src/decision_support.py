"""Decision-oriented views derived from the existing five-IMF forecast.

This module does not replace the research models.  It converts their existing
forecast and validation outputs into bounded research signals and transparent
enterprise procurement-cost scenarios.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class InvestmentDecision:
    label: str
    label_zh: str
    score: float
    position_low: float
    position_high: float
    confidence: str
    confidence_zh: str
    invalidation_price: float
    gated: bool
    gate_reason: str
    gate_reason_zh: str


@dataclass(frozen=True)
class HedgeRecommendation:
    hedge_ratio: float
    futures_share: float
    options_share: float
    rationale: str
    rationale_zh: str


def _final_interval(forecast: pd.DataFrame, level: int = 80) -> tuple[float, float]:
    if forecast.empty:
        raise ValueError("Forecast data is empty.")
    lower = f"Lower{level}"
    upper = f"Upper{level}"
    if lower not in forecast or upper not in forecast:
        raise ValueError(f"Forecast does not contain the {level}% interval.")
    row = forecast.iloc[-1]
    return float(row[lower]), float(row[upper])


def build_investment_decision(result: Any, *, high_volatility_probability: float = 0.0) -> InvestmentDecision:
    """Convert validated forecast outputs into a bounded, non-execution signal."""
    metrics = result.metrics
    latest = float(metrics["LatestPrice"])
    projected_change = float(metrics["ProjectedChangePercent"])
    accuracy = float(metrics["DirectionalAccuracyPercent"])
    lower, upper = _final_interval(result.forecast, 80)
    interval_width_pct = max(0.0, (upper - lower) / max(abs(latest), 1e-9) * 100.0)
    accuracy_edge = np.clip((accuracy - 50.0) / 20.0, -1.0, 1.0)
    direction = np.tanh(projected_change / 5.0)
    uncertainty_penalty = np.clip(interval_width_pct / 30.0, 0.0, 1.0)
    regime_penalty = np.clip(float(high_volatility_probability), 0.0, 1.0)
    score = float(np.clip(0.62 * direction + 0.28 * accuracy_edge - 0.07 * uncertainty_penalty - 0.15 * regime_penalty, -1.0, 1.0))

    gated = accuracy < 50.0 or interval_width_pct > 40.0
    if accuracy < 50.0:
        gate_reason = "Out-of-sample directional accuracy is below the release threshold."
        gate_reason_zh = "样本外方向准确率低于信号发布门槛。"
    elif interval_width_pct > 40.0:
        gate_reason = "The empirical forecast interval is too wide for a position signal."
        gate_reason_zh = "预测区间过宽，当前不建议给出仓位区间。"
    else:
        gate_reason = "Validation and interval-width gates passed."
        gate_reason_zh = "验证指标和区间宽度门槛均已通过。"

    if gated or abs(score) < 0.16:
        label, label_zh = "Neutral / observe", "中性 / 观望"
    elif score >= 0.58:
        label, label_zh = "Strong bullish research signal", "看多信号较强"
    elif score > 0:
        label, label_zh = "Cautious bullish research signal", "谨慎看多"
    elif score <= -0.58:
        label, label_zh = "Strong bearish research signal", "看空信号较强"
    else:
        label, label_zh = "Cautious bearish research signal", "谨慎看空"

    max_position = 0.0 if gated else min(0.35, abs(score) * 0.35)
    low_position = 0.0 if max_position == 0 else max(0.05, max_position * 0.55)
    if accuracy >= 62.0 and interval_width_pct <= 18.0:
        confidence, confidence_zh = "High", "较高"
    elif accuracy >= 54.0 and interval_width_pct <= 30.0:
        confidence, confidence_zh = "Medium", "中等"
    else:
        confidence, confidence_zh = "Low", "较低"
    invalidation = lower if score >= 0 else upper
    return InvestmentDecision(
        label=label,
        label_zh=label_zh,
        score=score,
        position_low=float(low_position),
        position_high=float(max_position),
        confidence=confidence,
        confidence_zh=confidence_zh,
        invalidation_price=float(invalidation),
        gated=gated,
        gate_reason=gate_reason,
        gate_reason_zh=gate_reason_zh,
    )


def recommend_buyer_hedge(result: Any, *, high_volatility_probability: float = 0.0) -> HedgeRecommendation:
    """Recommend a policy-bounded buyer hedge mix from forecast uncertainty."""
    metrics = result.metrics
    latest = float(metrics["LatestPrice"])
    projected_change = float(metrics["ProjectedChangePercent"])
    lower, upper = _final_interval(result.forecast, 80)
    width = (upper - lower) / max(abs(latest), 1e-9)
    upside_pressure = np.clip(projected_change / 12.0, -0.25, 0.35)
    uncertainty = np.clip(width / 0.35, 0.0, 1.0)
    regime = np.clip(float(high_volatility_probability), 0.0, 1.0)
    ratio = float(np.clip(0.45 + upside_pressure + 0.12 * regime, 0.30, 0.85))
    options_share = float(np.clip(0.15 + 0.35 * uncertainty + 0.20 * regime, 0.15, 0.60))
    futures_share = float(max(0.0, 1.0 - options_share))
    return HedgeRecommendation(
        hedge_ratio=ratio,
        futures_share=futures_share,
        options_share=options_share,
        rationale="Use more options when the interval or high-volatility probability is wide; use futures for the more certain layer.",
        rationale_zh="预测区间或高波动概率越高，越偏向使用期权；确定性较高的敞口由期货锁定。",
    )


def build_buyer_hedge_scenarios(
    result: Any,
    *,
    exposure_volume: float,
    budget_price: float,
    contract_size: float = 1_000.0,
    hedge_ratio: float | None = None,
    futures_share: float | None = None,
    option_strike: float | None = None,
    option_premium: float = 0.0,
) -> pd.DataFrame:
    """Calculate reconciled physical-cost and derivative-offset scenarios."""
    if exposure_volume <= 0 or contract_size <= 0:
        raise ValueError("Exposure volume and contract size must be positive.")
    recommendation = recommend_buyer_hedge(result)
    ratio = recommendation.hedge_ratio if hedge_ratio is None else float(np.clip(hedge_ratio, 0.0, 1.0))
    futures_fraction = recommendation.futures_share if futures_share is None else float(np.clip(futures_share, 0.0, 1.0))
    latest = float(result.metrics["LatestPrice"])
    strike = latest if option_strike is None else float(option_strike)
    lower80, upper80 = _final_interval(result.forecast, 80)
    lower95, upper95 = _final_interval(result.forecast, 95)
    point = float(result.forecast.iloc[-1]["PointForecast"])
    scenario_prices = [
        ("95% lower", "95%下界", lower95),
        ("80% lower", "80%下界", lower80),
        ("Model path", "模型中位路径", point),
        ("80% upper", "80%上界", upper80),
        ("95% upper", "95%上界", upper95),
    ]
    hedged_units = exposure_volume * ratio
    futures_units = hedged_units * futures_fraction
    option_units = hedged_units - futures_units
    contracts = int(round(hedged_units / contract_size))
    rows: list[dict[str, Any]] = []
    for scenario, scenario_zh, price in scenario_prices:
        physical_cost = exposure_volume * price
        futures_pnl = futures_units * (price - latest)
        option_payoff = option_units * max(price - strike, 0.0)
        premium_cost = option_units * max(float(option_premium), 0.0)
        derivative_offset = futures_pnl + option_payoff - premium_cost
        net_cost = physical_cost - futures_pnl - option_payoff + premium_cost
        rows.append(
            {
                "Scenario": scenario,
                "ScenarioZH": scenario_zh,
                "OilPrice": price,
                "PhysicalCost": physical_cost,
                "FuturesPnL": futures_pnl,
                "OptionPayoff": option_payoff,
                "OptionPremium": premium_cost,
                "DerivativeOffset": derivative_offset,
                "NetCost": net_cost,
                "BudgetCost": exposure_volume * budget_price,
                "BudgetVariance": net_cost - exposure_volume * budget_price,
                "HedgeRatio": ratio,
                "Contracts": contracts,
            }
        )
    return pd.DataFrame(rows)
