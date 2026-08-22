"""Decision-oriented views derived from the existing five-IMF forecast.

This module does not replace the research models.  It converts their existing
forecast and validation outputs into bounded research signals and transparent
enterprise procurement-cost scenarios.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

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


@dataclass(frozen=True)
class HedgeStage:
    """One procurement tranche in a staged buyer hedge.

    ``volume_share`` is a fraction of the physical purchase volume.  Prices are
    USD per physical unit and premiums are USD per option-covered unit.  A
    staged plan deliberately rounds futures contracts per tranche, which makes
    its execution and liquidity profile visible instead of assuming a
    fractional contract can be traded.
    """

    volume_share: float
    hedge_ratio: float
    futures_share: float = 1.0
    futures_entry_price: float | None = None
    option_style: str = "call"
    option_strike: float | None = None
    collar_floor: float | None = None
    option_premium: float = 0.0
    collar_put_premium: float = 0.0


@dataclass(frozen=True)
class HedgeStrategy:
    """A deterministic hedge-policy input; it is not an execution instruction.

    ``option_style`` is ``"none"``, ``"call"`` or ``"collar"``.  A buyer
    collar is modelled as a purchased call and a written put: it protects a
    price rise above ``option_strike`` but creates a payout below
    ``collar_floor``.  All inputs must be supplied by the caller or by the
    validated forecast result; this module never obtains market data.
    """

    name: str
    hedge_ratio: float = 0.0
    futures_share: float = 0.0
    option_style: str = "none"
    option_strike: float | None = None
    collar_floor: float | None = None
    option_premium: float = 0.0
    collar_put_premium: float = 0.0
    stages: tuple[HedgeStage, ...] = ()


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


def _finite_number(value: float, name: str, *, nonnegative: bool = False) -> float:
    """Return a finite scalar and reject impossible cost inputs early."""
    number = float(value)
    if not np.isfinite(number):
        raise ValueError(f"{name} must be finite.")
    if nonnegative and number < 0:
        raise ValueError(f"{name} cannot be negative.")
    return number


def _validate_option_terms(
    *,
    option_style: str,
    strike: float,
    collar_floor: float | None,
    option_premium: float,
    collar_put_premium: float,
) -> str:
    style = option_style.lower().strip()
    if style not in {"none", "call", "collar"}:
        raise ValueError("Option style must be 'none', 'call', or 'collar'.")
    _finite_number(strike, "Option strike", nonnegative=True)
    _finite_number(option_premium, "Option premium", nonnegative=True)
    _finite_number(collar_put_premium, "Collar put premium", nonnegative=True)
    if style == "collar":
        if collar_floor is None:
            raise ValueError("A collar requires collar_floor.")
        floor = _finite_number(collar_floor, "Collar floor", nonnegative=True)
        if floor > strike:
            raise ValueError("Collar floor cannot exceed the call strike.")
    return style


def _strategy_from_mapping(value: HedgeStrategy | Mapping[str, Any]) -> HedgeStrategy:
    if isinstance(value, HedgeStrategy):
        return value
    if not isinstance(value, Mapping):
        raise TypeError("Each strategy must be a HedgeStrategy or mapping.")
    raw = dict(value)
    stages = raw.get("stages", ())
    raw["stages"] = tuple(
        stage if isinstance(stage, HedgeStage) else HedgeStage(**dict(stage)) for stage in stages
    )
    return HedgeStrategy(**raw)


def _validate_strategy(strategy: HedgeStrategy) -> None:
    if not strategy.name.strip():
        raise ValueError("Strategy name cannot be empty.")
    for name, value in (("Hedge ratio", strategy.hedge_ratio), ("Futures share", strategy.futures_share)):
        number = _finite_number(value, name, nonnegative=True)
        if number > 1:
            raise ValueError(f"{name} must be between 0 and 1.")
    _finite_number(strategy.option_premium, "Option premium", nonnegative=True)
    _finite_number(strategy.collar_put_premium, "Collar put premium", nonnegative=True)
    if strategy.stages:
        total_share = 0.0
        for stage in strategy.stages:
            _finite_number(stage.volume_share, "Stage volume share", nonnegative=True)
            if stage.volume_share <= 0:
                raise ValueError("Stage volume share must be positive.")
            for name, value in (("Stage hedge ratio", stage.hedge_ratio), ("Stage futures share", stage.futures_share)):
                number = _finite_number(value, name, nonnegative=True)
                if number > 1:
                    raise ValueError(f"{name} must be between 0 and 1.")
            total_share += stage.volume_share
        if not np.isclose(total_share, 1.0, rtol=0.0, atol=1e-9):
            raise ValueError("Staged strategy volume shares must sum to 1.")


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
    budget_basis: float = 0.0,
    purchase_basis: float = 0.0,
    budget_fx_rate: float = 1.0,
    settlement_fx_rate: float = 1.0,
    futures_entry_price: float | None = None,
    margin_rate: float = 0.0,
    annual_funding_rate: float = 0.0,
    holding_days: int = 0,
    futures_fee_per_contract: float = 0.0,
    quality_differential_per_unit: float = 0.0,
    freight_per_unit: float = 0.0,
    taxes_per_unit: float = 0.0,
    other_unit_cost: float = 0.0,
    budget_quality_differential_per_unit: float = 0.0,
    budget_freight_per_unit: float = 0.0,
    budget_taxes_per_unit: float = 0.0,
    budget_other_unit_cost: float = 0.0,
    option_style: str = "call",
    collar_floor: float | None = None,
    collar_put_premium: float = 0.0,
    variation_margin_days: int | None = None,
) -> pd.DataFrame:
    """Calculate reconciled physical, derivative, basis, FX and funding scenarios.

    Every USD price/cost input is per physical unit unless marked per contract.
    ``quality_differential_per_unit`` may be negative (a discount); freight,
    tax, and other costs cannot.  Local-cost columns use the supplied CNY per
    USD rates.  Initial and variation margin are liquidity requirements; only
    their funding cost enters net procurement cost.  The result is a scenario
    analysis based solely on the supplied forecast, not live market data.
    """
    if _finite_number(exposure_volume, "Exposure volume") <= 0 or _finite_number(contract_size, "Contract size") <= 0:
        raise ValueError("Exposure volume and contract size must be positive.")
    if _finite_number(budget_fx_rate, "Budget FX rate") <= 0 or _finite_number(settlement_fx_rate, "Settlement FX rate") <= 0:
        raise ValueError("Budget and settlement FX rates must be positive.")
    if holding_days < 0:
        raise ValueError("Holding days cannot be negative.")
    if variation_margin_days is None:
        variation_margin_days = holding_days
    if variation_margin_days < 0:
        raise ValueError("Variation margin days cannot be negative.")
    for name, value, nonnegative in (
        ("Budget price", budget_price, False),
        ("Budget basis", budget_basis, False),
        ("Purchase basis", purchase_basis, False),
        ("Futures fee per contract", futures_fee_per_contract, True),
        ("Margin rate", margin_rate, True),
        ("Annual funding rate", annual_funding_rate, True),
        ("Quality differential", quality_differential_per_unit, False),
        ("Freight", freight_per_unit, True),
        ("Taxes", taxes_per_unit, True),
        ("Other unit cost", other_unit_cost, True),
        ("Budget quality differential", budget_quality_differential_per_unit, False),
        ("Budget freight", budget_freight_per_unit, True),
        ("Budget taxes", budget_taxes_per_unit, True),
        ("Budget other unit cost", budget_other_unit_cost, True),
    ):
        _finite_number(value, name, nonnegative=nonnegative)
    recommendation = recommend_buyer_hedge(result)
    ratio = recommendation.hedge_ratio if hedge_ratio is None else float(np.clip(hedge_ratio, 0.0, 1.0))
    futures_fraction = recommendation.futures_share if futures_share is None else float(np.clip(futures_share, 0.0, 1.0))
    latest = float(result.metrics["LatestPrice"])
    futures_entry = latest if futures_entry_price is None else float(futures_entry_price)
    strike = latest if option_strike is None else float(option_strike)
    style = _validate_option_terms(
        option_style=option_style,
        strike=strike,
        collar_floor=collar_floor,
        option_premium=option_premium,
        collar_put_premium=collar_put_premium,
    )
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
    futures_contracts = int(round(futures_units / contract_size))
    effective_futures_units = futures_contracts * contract_size
    initial_margin = abs(effective_futures_units * futures_entry) * max(float(margin_rate), 0.0)
    initial_margin_funding_cost = initial_margin * max(float(annual_funding_rate), 0.0) * int(holding_days) / 365.0
    transaction_cost = futures_contracts * max(float(futures_fee_per_contract), 0.0)
    budget_unit_price = (
        float(budget_price)
        + float(budget_basis)
        + float(budget_quality_differential_per_unit)
        + float(budget_freight_per_unit)
        + float(budget_taxes_per_unit)
        + float(budget_other_unit_cost)
    )
    budget_cost = exposure_volume * budget_unit_price
    rows: list[dict[str, Any]] = []
    for scenario, scenario_zh, price in scenario_prices:
        physical_unit_price = (
            price
            + float(purchase_basis)
            + float(quality_differential_per_unit)
            + float(freight_per_unit)
            + float(taxes_per_unit)
            + float(other_unit_cost)
        )
        physical_cost = exposure_volume * physical_unit_price
        futures_pnl = effective_futures_units * (price - futures_entry)
        call_payoff = option_units * max(price - strike, 0.0) if style in {"call", "collar"} else 0.0
        written_put_payout = option_units * max(float(collar_floor) - price, 0.0) if style == "collar" else 0.0
        option_payoff = call_payoff - written_put_payout
        premium_cost = option_units * (
            max(float(option_premium), 0.0) - (max(float(collar_put_premium), 0.0) if style == "collar" else 0.0)
        )
        variation_margin_posted = max(-futures_pnl, 0.0)
        variation_margin_received = max(futures_pnl, 0.0)
        variation_margin_funding_cost = (
            variation_margin_posted * max(float(annual_funding_rate), 0.0) * int(variation_margin_days) / 365.0
        )
        margin_funding_cost = initial_margin_funding_cost + variation_margin_funding_cost
        derivative_offset = futures_pnl + option_payoff - premium_cost - transaction_cost - margin_funding_cost
        net_cost = physical_cost - futures_pnl - option_payoff + premium_cost + transaction_cost + margin_funding_cost
        physical_cost_local = physical_cost * float(settlement_fx_rate)
        net_cost_local = net_cost * float(settlement_fx_rate)
        budget_cost_local = budget_cost * float(budget_fx_rate)
        fx_impact_local = net_cost * (float(settlement_fx_rate) - float(budget_fx_rate))
        rows.append(
            {
                "Scenario": scenario,
                "ScenarioZH": scenario_zh,
                "OilPrice": price,
                "PurchaseBasis": float(purchase_basis),
                "QualityDifferentialPerUnit": float(quality_differential_per_unit),
                "FreightPerUnit": float(freight_per_unit),
                "TaxesPerUnit": float(taxes_per_unit),
                "OtherUnitCost": float(other_unit_cost),
                "PhysicalUnitPrice": physical_unit_price,
                "PhysicalCost": physical_cost,
                "FuturesPnL": futures_pnl,
                "OptionPayoff": option_payoff,
                "OptionPremium": premium_cost,
                "TransactionCost": transaction_cost,
                "InitialMargin": initial_margin,
                "InitialMarginFundingCost": initial_margin_funding_cost,
                "VariationMarginCashFlow": futures_pnl,
                "VariationMarginPosted": variation_margin_posted,
                "VariationMarginReceived": variation_margin_received,
                "VariationMarginFundingCost": variation_margin_funding_cost,
                "MarginFundingCost": margin_funding_cost,
                "DerivativeOffset": derivative_offset,
                "NetCost": net_cost,
                "BudgetCost": budget_cost,
                "BudgetVariance": net_cost - budget_cost,
                "BudgetDeviation": net_cost - budget_cost,
                "BudgetDeviationPct": (net_cost - budget_cost) / max(abs(budget_cost), 1e-9),
                "BudgetFXRate": float(budget_fx_rate),
                "SettlementFXRate": float(settlement_fx_rate),
                "PhysicalCostCNY": physical_cost_local,
                "NetCostCNY": net_cost_local,
                "BudgetCostCNY": budget_cost_local,
                "BudgetVarianceCNY": net_cost_local - budget_cost_local,
                "FXImpactCNY": fx_impact_local,
                "BasisImpactCNY": exposure_volume
                * (float(purchase_basis) - float(budget_basis))
                * float(settlement_fx_rate),
                "QualityImpactCNY": exposure_volume
                * (float(quality_differential_per_unit) - float(budget_quality_differential_per_unit))
                * float(settlement_fx_rate),
                "FreightImpactCNY": exposure_volume
                * (float(freight_per_unit) - float(budget_freight_per_unit))
                * float(settlement_fx_rate),
                "TaxesImpactCNY": exposure_volume
                * (float(taxes_per_unit) - float(budget_taxes_per_unit))
                * float(settlement_fx_rate),
                "OtherCostImpactCNY": exposure_volume
                * (float(other_unit_cost) - float(budget_other_unit_cost))
                * float(settlement_fx_rate),
                "InitialMarginCNY": initial_margin * float(budget_fx_rate),
                "VariationMarginPostedCNY": variation_margin_posted * float(settlement_fx_rate),
                "VariationMarginReceivedCNY": variation_margin_received * float(settlement_fx_rate),
                "FundingAndFeesCNY": (margin_funding_cost + transaction_cost)
                * float(settlement_fx_rate),
                "LiquidityRequirement": initial_margin
                + variation_margin_posted
                + max(premium_cost, 0.0)
                + transaction_cost,
                "LiquidityRequirementCNY": initial_margin * float(budget_fx_rate)
                + (variation_margin_posted + max(premium_cost, 0.0) + transaction_cost) * float(settlement_fx_rate),
                "LiquidityToBudgetRatio": (
                    initial_margin * float(budget_fx_rate)
                    + (variation_margin_posted + max(premium_cost, 0.0) + transaction_cost) * float(settlement_fx_rate)
                )
                / max(abs(budget_cost_local), 1e-9),
                "EffectiveUnitCostCNY": net_cost_local / exposure_volume,
                "HedgeRatio": ratio,
                "FuturesShare": futures_fraction,
                "OptionStyle": style,
                "Contracts": contracts,
                "FuturesContracts": futures_contracts,
                "EffectiveFuturesUnits": effective_futures_units,
            }
        )
    return pd.DataFrame(rows)


def compare_buyer_hedge_strategies(
    result: Any,
    *,
    exposure_volume: float,
    budget_price: float,
    strategies: Sequence[HedgeStrategy | Mapping[str, Any]] | None = None,
    hedge_ratio: float | None = None,
    futures_share: float | None = None,
    option_strike: float | None = None,
    option_premium: float = 0.0,
    collar_floor: float | None = None,
    collar_put_premium: float = 0.0,
    **procurement_terms: Any,
) -> pd.DataFrame:
    """Compare buyer hedge policies over the same forecast scenarios.

    The returned frame has one row per strategy and forecast scenario.  It
    includes every cost, budget-deviation, and liquidity column emitted by
    :func:`build_buyer_hedge_scenarios`, prefixed by policy metadata.  Pass
    ``HedgeStrategy`` objects (or mappings with the same fields) to make the
    comparison fully explicit.  If omitted, the function provides five
    transparent alternatives: unhedged, futures, options/collar, mixed, and a
    three-tranche futures hedge.  It is a scenario comparator, not a trading
    optimiser or a source of real-time prices.

    ``procurement_terms`` accepts the remaining documented keyword arguments
    of ``build_buyer_hedge_scenarios`` (for example ``purchase_basis``,
    ``settlement_fx_rate``, ``margin_rate``, and ``freight_per_unit``).  A
    staged strategy computes each tranche separately and then adds cash costs
    and margin requirements, retaining the whole-contract rounding of each
    tranche.
    """
    recommendation = recommend_buyer_hedge(result)
    selected_ratio = recommendation.hedge_ratio if hedge_ratio is None else _finite_number(hedge_ratio, "Hedge ratio", nonnegative=True)
    selected_futures_share = recommendation.futures_share if futures_share is None else _finite_number(futures_share, "Futures share", nonnegative=True)
    if selected_ratio > 1 or selected_futures_share > 1:
        raise ValueError("Hedge ratio and futures share must be between 0 and 1.")
    selected_strike = float(result.metrics["LatestPrice"]) if option_strike is None else _finite_number(option_strike, "Option strike", nonnegative=True)

    if strategies is None:
        option_style = "collar" if collar_floor is not None else "call"
        staged_ratios = (
            min(1.0, selected_ratio * 0.65),
            selected_ratio,
            min(1.0, selected_ratio * 1.20),
        )
        selected_strategies = (
            HedgeStrategy(name="Unhedged", option_style="none"),
            HedgeStrategy(name="Futures", hedge_ratio=selected_ratio, futures_share=1.0, option_style="none"),
            HedgeStrategy(
                name="Options / collar",
                hedge_ratio=selected_ratio,
                futures_share=0.0,
                option_style=option_style,
                option_strike=selected_strike,
                collar_floor=collar_floor,
                option_premium=option_premium,
                collar_put_premium=collar_put_premium,
            ),
            HedgeStrategy(
                name="Mixed",
                hedge_ratio=selected_ratio,
                futures_share=selected_futures_share,
                option_style=option_style,
                option_strike=selected_strike,
                collar_floor=collar_floor,
                option_premium=option_premium,
                collar_put_premium=collar_put_premium,
            ),
            HedgeStrategy(
                name="Staged futures",
                option_style="none",
                stages=tuple(
                    HedgeStage(volume_share=share, hedge_ratio=stage_ratio, futures_share=1.0, option_style="none")
                    for share, stage_ratio in zip((0.30, 0.40, 0.30), staged_ratios)
                ),
            ),
        )
    else:
        selected_strategies = tuple(_strategy_from_mapping(strategy) for strategy in strategies)
        if not selected_strategies:
            raise ValueError("At least one strategy is required.")

    labels_zh = {
        "Unhedged": "未套保",
        "Futures": "期货套保",
        "Options / collar": "期权/领口",
        "Mixed": "混合套保",
        "Staged futures": "分批期货套保",
    }
    comparison_frames: list[pd.DataFrame] = []
    for strategy in selected_strategies:
        _validate_strategy(strategy)
        base_terms = dict(procurement_terms)
        base_terms.update(
            exposure_volume=exposure_volume,
            budget_price=budget_price,
            hedge_ratio=strategy.hedge_ratio,
            futures_share=strategy.futures_share,
            option_style=strategy.option_style,
            option_strike=selected_strike if strategy.option_strike is None else strategy.option_strike,
            collar_floor=strategy.collar_floor,
            option_premium=strategy.option_premium,
            collar_put_premium=strategy.collar_put_premium,
        )
        if not strategy.stages:
            strategy_frame = build_buyer_hedge_scenarios(result, **base_terms)
        else:
            stage_frames: list[pd.DataFrame] = []
            for stage in strategy.stages:
                stage_terms = dict(base_terms)
                stage_terms.update(
                    exposure_volume=float(exposure_volume) * stage.volume_share,
                    hedge_ratio=stage.hedge_ratio,
                    futures_share=stage.futures_share,
                    option_style=stage.option_style,
                    option_strike=selected_strike if stage.option_strike is None else stage.option_strike,
                    collar_floor=stage.collar_floor,
                    option_premium=stage.option_premium,
                    collar_put_premium=stage.collar_put_premium,
                )
                if stage.futures_entry_price is not None:
                    stage_terms["futures_entry_price"] = stage.futures_entry_price
                stage_frames.append(build_buyer_hedge_scenarios(result, **stage_terms))
            strategy_frame = _combine_staged_scenarios(stage_frames, strategy.stages, exposure_volume)
        strategy_frame.insert(0, "Strategy", strategy.name)
        strategy_frame.insert(1, "StrategyZH", labels_zh.get(strategy.name, strategy.name))
        strategy_frame.insert(2, "StrategyType", "staged" if strategy.stages else strategy.option_style)
        strategy_frame.insert(3, "IsStaged", bool(strategy.stages))
        comparison_frames.append(strategy_frame)
    return pd.concat(comparison_frames, ignore_index=True)


def _combine_staged_scenarios(
    stage_frames: Sequence[pd.DataFrame], stages: Sequence[HedgeStage], exposure_volume: float
) -> pd.DataFrame:
    """Add cash flows from independently rounded tranches without summing rates."""
    combined = stage_frames[0].copy()
    constant_columns = {
        "OilPrice", "PurchaseBasis", "QualityDifferentialPerUnit", "FreightPerUnit", "TaxesPerUnit",
        "OtherUnitCost", "PhysicalUnitPrice", "BudgetFXRate", "SettlementFXRate", "OptionStyle",
    }
    derived_columns = {"EffectiveUnitCostCNY", "BudgetDeviationPct", "LiquidityToBudgetRatio", "HedgeRatio", "FuturesShare"}
    for column in combined.select_dtypes(include=[np.number]).columns:
        if column not in constant_columns | derived_columns:
            combined[column] = sum(frame[column] for frame in stage_frames)
    combined["HedgeRatio"] = sum(stage.volume_share * stage.hedge_ratio for stage in stages)
    covered_units = sum(stage.volume_share * stage.hedge_ratio for stage in stages)
    futures_covered_units = sum(stage.volume_share * stage.hedge_ratio * stage.futures_share for stage in stages)
    combined["FuturesShare"] = futures_covered_units / covered_units if covered_units else 0.0
    combined["OptionStyle"] = "staged"
    combined["EffectiveUnitCostCNY"] = combined["NetCostCNY"] / float(exposure_volume)
    combined["BudgetDeviationPct"] = combined["BudgetDeviation"] / combined["BudgetCost"].abs().clip(lower=1e-9)
    combined["LiquidityToBudgetRatio"] = combined["LiquidityRequirementCNY"] / combined["BudgetCostCNY"].abs().clip(lower=1e-9)
    return combined
