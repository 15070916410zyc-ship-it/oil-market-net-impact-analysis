"""Decision cockpit UI built on top of the existing research forecast."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict
import re
from typing import Any, Callable

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.data_governance import aggregate_time_series
from src.decision_support import (
    build_buyer_hedge_scenarios,
    build_investment_decision,
    compare_buyer_hedge_strategies,
    recommend_buyer_hedge,
)
from src.research_store import ResearchStore


UiText = Callable[[str, str], str]
ThemeFunction = Callable[[Any], Any]
PLOT_CONFIG = {
    "scrollZoom": True,
    "displaylogo": False,
    "responsive": True,
    "modeBarButtonsToRemove": ["lasso2d"],
    "toImageButtonOptions": {"format": "png", "scale": 2},
}


def _quantize_slider_default(
    value: float,
    *,
    step: float = 0.05,
    minimum: float = 0.0,
    maximum: float = 1.0,
) -> float:
    """Clamp a computed default to a valid Streamlit slider tick."""
    clipped = min(max(float(value), minimum), maximum)
    ticks = int(np.floor((clipped - minimum) / step + 0.5))
    return float(round(minimum + ticks * step, 10))


def _story_database_url() -> str:
    try:
        return str(st.secrets.get("DATABASE_URL", "") or "").strip()
    except Exception:  # pragma: no cover - local secrets are optional.
        return ""


def _load_price_series(target: str, history_months: int, *, force_refresh: bool) -> pd.DataFrame:
    from src.data_fetcher import RAW_CACHE_FILES, SERIES_SOURCES, fetch_series_with_fallback

    end = pd.Timestamp.today().normalize()
    start = (end - pd.DateOffset(months=int(history_months))).normalize()
    data = fetch_series_with_fallback(
        target,
        SERIES_SOURCES[target],
        start.strftime("%Y-%m-%d"),
        end.strftime("%Y-%m-%d"),
        RAW_CACHE_FILES[target],
        force_refresh=force_refresh,
    )
    if data.empty or target not in data or data[target].notna().sum() < 180:
        raise ValueError(f"No sufficiently current {target} series is available.")
    return data


def _anchored_forecast_view(history_view: pd.DataFrame, forecast_view: pd.DataFrame) -> pd.DataFrame:
    """Join future paths to the last observed price without altering model output."""
    if history_view.empty or forecast_view.empty:
        return forecast_view.copy()
    last_observation = history_view.iloc[-1]
    anchor: dict[str, object] = {"Date": last_observation["Date"]}
    for column in forecast_view.columns:
        if column == "Date":
            continue
        if column == "PointForecast" or re.fullmatch(r"(?:Lower|Upper)\d+", str(column)):
            anchor[column] = float(last_observation["Price"])
        else:
            anchor[column] = np.nan
    return pd.concat([pd.DataFrame([anchor]), forecast_view], ignore_index=True)


def _main_forecast_figure(result: Any, frequency: str, ui_text: UiText) -> go.Figure:
    history = result.history.rename(columns={"Actual": "Price"})
    forecast = result.forecast.copy()
    history_view = aggregate_time_series(history, frequency, methods={"Price": "last"})
    if str(frequency).lower() == "monthly" and not history_view.empty:
        # A partial current month must end on the actual as-of date, rather than
        # appearing to contain observations from a future month-end.
        history_view.loc[history_view.index[-1], "Date"] = pd.to_datetime(history["Date"]).max()
    forecast_view = aggregate_time_series(
        forecast,
        frequency,
        methods={column: "last" for column in forecast.columns if column != "Date"},
    )
    forecast_view = forecast_view.drop_duplicates(subset=["Date"], keep="last").sort_values("Date")
    forecast_view = _anchored_forecast_view(history_view, forecast_view)
    figure = go.Figure()
    figure.add_trace(
        go.Scatter(
            x=history_view["Date"],
            y=history_view["Price"],
            mode="lines",
            name=ui_text("Observed", "实际价格"),
            line=dict(color="#354554", width=2.2),
            connectgaps=True,
            hovertemplate="%{x|%Y-%m-%d}<br>$%{y:,.2f}<extra></extra>",
        )
    )
    if not forecast_view.empty:
        interval_colors = {
            50: ("#B57D4F", "rgba(181, 125, 79, 0.18)"),
            80: ("#3F8074", "rgba(63, 128, 116, 0.14)"),
            95: ("#718DA3", "rgba(113, 141, 163, 0.10)"),
        }
        available_intervals = [
            level
            for level in (95, 80, 50)
            if f"Lower{level}" in forecast_view and f"Upper{level}" in forecast_view
        ]
        for level in available_intervals:
            line_color, fill_color = interval_colors[level]
            lower_column = f"Lower{level}"
            upper_column = f"Upper{level}"
            figure.add_trace(
                go.Scatter(
                    x=forecast_view["Date"],
                    y=forecast_view[upper_column],
                    mode="lines",
                    line=dict(color=line_color, width=0.8),
                    hoverinfo="skip",
                    showlegend=False,
                )
            )
            figure.add_trace(
                go.Scatter(
                    x=forecast_view["Date"],
                    y=forecast_view[lower_column],
                    mode="lines",
                    name=ui_text(f"{level}% empirical range", f"{level}%经验区间"),
                    fill="tonexty",
                    fillcolor=fill_color,
                    line=dict(color=line_color, width=0.8),
                    customdata=forecast_view[[lower_column, upper_column]].to_numpy(),
                    hovertemplate=(
                        "%{x|%Y-%m-%d}<br>"
                        + ui_text("Lower", "下界")
                        + ": $%{customdata[0]:,.2f}<br>"
                        + ui_text("Upper", "上界")
                        + ": $%{customdata[1]:,.2f}<extra></extra>"
                    ),
                )
            )
        figure.add_trace(
            go.Scatter(
                x=forecast_view["Date"],
                y=forecast_view["PointForecast"],
                mode="lines+markers",
                name=ui_text("Multi-rhythm forecast", "多层波动合成预测"),
                line=dict(color="#356B65", width=3),
                marker=dict(size=5, color="#6F9189"),
                connectgaps=True,
                hovertemplate="%{x|%Y-%m-%d}<br>$%{y:,.2f}<extra></extra>",
            )
        )
        figure.add_vline(
            x=pd.to_datetime(history_view["Date"]).max(),
            line_color="rgba(53, 69, 84, 0.34)",
            line_width=1,
            line_dash="dot",
        )
    figure.update_layout(
        title=dict(text=ui_text("Observed path and forecast ranges", "实际走势与预测区间"), x=0),
        height=590,
        margin=dict(l=12, r=12, t=72, b=12),
        hovermode="x unified",
        dragmode="pan",
        legend=dict(orientation="h", y=1.04, x=0, traceorder="normal"),
        yaxis_title=ui_text("USD / barrel", "美元/桶"),
        uirevision=f"executive-{frequency}-{result.metrics.get('AsOfDate')}",
    )
    figure.update_xaxes(
        rangeslider=dict(visible=True, thickness=0.08, bgcolor="#EEF1ED"),
        rangeselector=dict(
            buttons=[
                dict(count=1, label="1M", step="month", stepmode="backward"),
                dict(count=6, label="6M", step="month", stepmode="backward"),
                dict(count=1, label="1Y", step="year", stepmode="backward"),
                dict(step="all", label=ui_text("All", "全部")),
            ]
        ),
    )
    return figure


def _hedge_figure(scenarios: pd.DataFrame, ui_text: UiText, *, currency: str = "USD") -> go.Figure:
    labels = scenarios["ScenarioZH"] if ui_text("en", "zh") == "zh" else scenarios["Scenario"]
    use_cny = currency.upper() == "CNY" and "NetCostCNY" in scenarios
    physical_column = "PhysicalCostCNY" if use_cny else "PhysicalCost"
    net_column = "NetCostCNY" if use_cny else "NetCost"
    budget_column = "BudgetCostCNY" if use_cny else "BudgetCost"
    money_prefix = "¥" if use_cny else "$"
    figure = go.Figure()
    figure.add_trace(
        go.Bar(
            x=labels,
            y=scenarios[physical_column],
            name=ui_text("Unhedged physical cost", "未套保采购成本"),
            marker_color="#5A6870",
            hovertemplate=f"%{{x}}<br>{money_prefix}%{{y:,.0f}}<extra></extra>",
        )
    )
    figure.add_trace(
        go.Bar(
            x=labels,
            y=scenarios[net_column],
            name=ui_text("Net cost after hedge", "套保后净成本"),
            marker_color="#356B65",
            hovertemplate=f"%{{x}}<br>{money_prefix}%{{y:,.0f}}<extra></extra>",
        )
    )
    figure.add_trace(
        go.Scatter(
            x=labels,
            y=scenarios[budget_column],
            mode="lines",
            name=ui_text("Budget", "预算"),
            line=dict(color="#354554", width=2, dash="dash"),
            hovertemplate=f"%{{x}}<br>{money_prefix}%{{y:,.0f}}<extra></extra>",
        )
    )
    figure.update_layout(
        title=dict(text=ui_text("Procurement cost under forecast scenarios", "预测情景下的采购成本"), x=0),
        height=420,
        margin=dict(l=12, r=12, t=64, b=12),
        barmode="group",
        hovermode="x unified",
        yaxis_title=ui_text("CNY", "人民币") if use_cny else ui_text("USD", "美元"),
        legend=dict(orientation="h", y=1.03),
    )
    return figure


def _strategy_comparison_figure(comparison: pd.DataFrame, ui_text: UiText) -> go.Figure:
    """Compare effective unit cost across policies on the same five scenarios."""
    figure = go.Figure()
    colors = ("#63727B", "#24796D", "#6EAFC6", "#E8B45B", "#8A78A8")
    is_zh = ui_text("en", "zh") == "zh"
    for color, (_, frame) in zip(colors, comparison.groupby("Strategy", sort=False)):
        label = str(frame["StrategyZH"].iloc[0] if is_zh else frame["Strategy"].iloc[0])
        scenario_labels = frame["ScenarioZH"] if is_zh else frame["Scenario"]
        figure.add_trace(
            go.Scatter(
                x=scenario_labels,
                y=frame["EffectiveUnitCostCNY"],
                mode="lines+markers",
                name=label,
                line=dict(color=color, width=2.4),
                marker=dict(size=7),
                customdata=frame[["BudgetVarianceCNY", "LiquidityRequirementCNY"]].to_numpy(),
                hovertemplate=(
                    "%{x}<br>"
                    + ui_text("Unit cost", "折算单桶成本")
                    + ": ¥%{y:,.2f}<br>"
                    + ui_text("Variance vs budget", "相对预算偏差")
                    + ": ¥%{customdata[0]:+,.0f}<br>"
                    + ui_text("Liquidity required", "资金占用")
                    + ": ¥%{customdata[1]:,.0f}<extra></extra>"
                ),
            )
        )
    figure.update_layout(
        title=dict(text=ui_text("Cost paths across five hedge policies", "五种套保策略的成本路径"), x=0),
        height=470,
        margin=dict(l=18, r=18, t=72, b=18),
        hovermode="x unified",
        yaxis_title=ui_text("Effective cost (CNY / barrel)", "折算成本（人民币/桶）"),
        xaxis_title=None,
        legend=dict(orientation="h", y=1.03),
    )
    return figure


def _liquidity_stress_figure(comparison: pd.DataFrame, ui_text: UiText) -> go.Figure:
    """Show each policy's worst modeled cash requirement and triggering scenario."""
    peak_indices = comparison.groupby("Strategy", sort=False)["LiquidityRequirementCNY"].idxmax()
    peak = comparison.loc[peak_indices].copy().sort_values("LiquidityRequirementCNY")
    is_zh = ui_text("en", "zh") == "zh"
    labels = peak["StrategyZH"] if is_zh else peak["Strategy"]
    scenarios = peak["ScenarioZH"] if is_zh else peak["Scenario"]
    figure = go.Figure(
        go.Bar(
            x=peak["LiquidityRequirementCNY"],
            y=labels,
            orientation="h",
            marker_color="#6EAFC6",
            customdata=np.column_stack([scenarios, peak["LiquidityToBudgetRatio"]]),
            hovertemplate=(
                "%{y}<br>¥%{x:,.0f}<br>"
                + ui_text("Stress scenario", "压力情景")
                + ": %{customdata[0]}<br>"
                + ui_text("Share of budget", "占预算比例")
                + ": %{customdata[1]:.1%}<extra></extra>"
            ),
        )
    )
    figure.update_layout(
        title=dict(text=ui_text("Peak modeled liquidity need", "各策略峰值资金占用"), x=0),
        height=470,
        margin=dict(l=18, r=18, t=72, b=18),
        xaxis_title=ui_text("CNY", "人民币"),
        yaxis_title=None,
    )
    return figure


def _cost_waterfall_figure(stress: pd.Series, ui_text: UiText) -> go.Figure:
    """Reconcile the selected plan's upper-stress physical and hedge cash flows."""
    settlement_fx = float(stress["SettlementFXRate"])
    labels = [
        ui_text("Physical purchase", "实货采购"),
        ui_text("Futures offset", "期货对冲"),
        ui_text("Option payoff", "期权赔付"),
        ui_text("Option premium", "期权费"),
        ui_text("Funding and fees", "资金成本与费用"),
        ui_text("Net procurement cost", "净采购成本"),
    ]
    values = [
        float(stress["PhysicalCostCNY"]),
        -float(stress["FuturesPnL"]) * settlement_fx,
        -float(stress["OptionPayoff"]) * settlement_fx,
        float(stress["OptionPremium"]) * settlement_fx,
        float(stress["FundingAndFeesCNY"]),
        float(stress["NetCostCNY"]),
    ]
    figure = go.Figure(
        go.Waterfall(
            x=labels,
            y=values,
            measure=["absolute", "relative", "relative", "relative", "relative", "total"],
            connector=dict(line=dict(color="rgba(53,69,84,0.26)")),
            increasing=dict(marker=dict(color="#E8B45B")),
            decreasing=dict(marker=dict(color="#24796D")),
            totals=dict(marker=dict(color="#354554")),
            hovertemplate="%{x}<br>¥%{y:+,.0f}<extra></extra>",
        )
    )
    figure.add_hline(
        y=float(stress["BudgetCostCNY"]),
        line_color="#8A78A8",
        line_dash="dot",
        line_width=1.5,
    )
    figure.update_layout(
        title=dict(text=ui_text("95% upper-stress cost bridge", "95% 上界压力情景成本拆解"), x=0),
        height=470,
        margin=dict(l=18, r=18, t=72, b=18),
        yaxis_title=ui_text("CNY", "人民币"),
        showlegend=False,
    )
    return figure


FACTOR_LABELS_ZH = {
    "OVX": "原油波动率",
    "VIX": "美股风险情绪",
    "DollarIndex": "美元指数",
    "TNote10Y": "美国十年期利率",
    "Gold": "黄金",
    "Copper": "铜价",
    "NaturalGas": "天然气",
    "CrudeStocks": "美国原油库存",
    "GPRD": "地缘政治风险",
}
DECISION_FACTOR_NAMES = (
    "OVX",
    "VIX",
    "DollarIndex",
    "TNote10Y",
    "Gold",
    "Copper",
    "NaturalGas",
    "CrudeStocks",
    "GPRD",
)


def _factor_associations(frame: pd.DataFrame, target: str) -> pd.DataFrame:
    """Estimate recent non-causal price associations for plain-language display."""
    if frame.empty or target not in frame:
        return pd.DataFrame()
    from src.quick_analysis import VARIABLE_ECONOMIC_CATEGORIES, variable_economic_category

    aligned = frame.copy().sort_values("Date").drop_duplicates("Date", keep="last")
    numeric = aligned.drop(columns=["Date"], errors="ignore").apply(pd.to_numeric, errors="coerce")
    returns = numeric.pct_change(fill_method=None).replace([np.inf, -np.inf], np.nan)
    rows: list[dict[str, Any]] = []
    for variable in numeric.columns:
        if variable == target:
            continue
        pair = returns[[target, variable]].dropna().tail(252)
        levels = numeric[variable].dropna()
        if len(pair) < 80 or len(levels) < 21:
            continue
        variance = float(pair[variable].var(ddof=0))
        beta = 0.0 if variance <= 1e-12 else float(pair[target].cov(pair[variable]) / variance)
        recent_change = float(levels.iloc[-1] / levels.iloc[-21] - 1.0) if levels.iloc[-21] else 0.0
        estimated_effect = float(np.clip(beta * recent_change * 100.0, -20.0, 20.0))
        correlation = float(pair[target].corr(pair[variable]))
        category = variable_economic_category(variable)
        category_zh = VARIABLE_ECONOMIC_CATEGORIES[category]["label_zh"]
        rows.append(
            {
                "Variable": variable,
                "LabelZH": FACTOR_LABELS_ZH.get(variable, variable),
                "CategoryZH": category_zh,
                "Correlation": correlation,
                "RecentChangePercent": recent_change * 100.0,
                "EstimatedEffectPercent": estimated_effect,
            }
        )
    output = pd.DataFrame(rows)
    if output.empty:
        return output
    return output.assign(Strength=output["EstimatedEffectPercent"].abs()).sort_values(
        "Strength", ascending=False
    ).head(7)


def _model_ready_factors(
    factor_names: tuple[str, ...],
    start: pd.Timestamp,
    end: pd.Timestamp,
) -> pd.DataFrame:
    """Load built-in factor columns once, so the first view is not network-bound."""
    try:
        from src.variable_pool import MODEL_READY_PATH

        frame = pd.read_excel(MODEL_READY_PATH)
    except Exception:  # noqa: BLE001 - online/cache sources remain available.
        return pd.DataFrame(columns=["Date", *factor_names])
    if "Date" not in frame:
        return pd.DataFrame(columns=["Date", *factor_names])
    frame["Date"] = pd.to_datetime(frame["Date"], errors="coerce")
    frame = frame.loc[frame["Date"].between(start, end)].copy()
    available = [name for name in factor_names if name in frame and frame[name].notna().any()]
    return frame[["Date", *available]].dropna(subset=["Date"])


def _built_in_factor_status(name: str, series: pd.DataFrame) -> dict[str, Any]:
    values = pd.to_numeric(series[name], errors="coerce")
    valid = series.loc[values.notna(), "Date"]
    return {
        "Variable": name,
        "AutoDownload": False,
        "ActualSource": "model_ready_data.xlsx",
        "Status": "LoadedBuiltIn",
        "LatestDate": valid.max() if not valid.empty else pd.NaT,
        "MissingCount": int(values.isna().sum()),
        "Coverage": float(values.notna().mean()) if len(values) else 0.0,
        "Note": "Loaded the verified built-in research series without waiting for a network request.",
    }


def _fresh_cached_factor_status(name: str, series: pd.DataFrame, cache_file: str) -> dict[str, Any]:
    values = pd.to_numeric(series[name], errors="coerce")
    valid = series.loc[values.notna(), "Date"]
    return {
        "Variable": name,
        "AutoDownload": True,
        "ActualSource": f"cache:{cache_file}",
        "Status": "LoadedFreshCache",
        "LatestDate": valid.max() if not valid.empty else pd.NaT,
        "MissingCount": int(values.isna().sum()),
        "Coverage": float(values.notna().mean()) if len(values) else 0.0,
        "Note": "Loaded a fresh local series while the decision view opened; manual refresh still checks the online source.",
    }


def _load_decision_context(
    price: pd.DataFrame,
    target: str,
    history_months: int,
    *,
    force_refresh: bool,
) -> dict[str, Any]:
    """Load factor context and the risk state concurrently after the price view."""
    from src.crisis_regime import run_markov_crisis_forecast
    from src.variable_pool import (
        _fetch_registry_variable,
        _load_variable_cache,
        load_variable_registry,
    )

    end = pd.Timestamp.today().normalize()
    start = (end - pd.DateOffset(months=int(history_months))).normalize()
    registry = {entry["name"]: entry for entry in load_variable_registry()}
    merged = price[["Date", target]].copy()
    statuses_by_name: dict[str, dict[str, Any]] = {}
    built_in = _model_ready_factors(DECISION_FACTOR_NAMES, start, end)
    remote_names: list[str] = []
    for name in DECISION_FACTOR_NAMES:
        entry = registry.get(name)
        if not entry:
            continue
        cached = pd.DataFrame()
        cache_file = str(entry.get("cache_file", "") or "").strip()
        if cache_file and not force_refresh:
            cached = _load_variable_cache(
                cache_file,
                name,
                start.strftime("%Y-%m-%d"),
                end.strftime("%Y-%m-%d"),
            )
        cached_latest = (
            pd.to_datetime(cached["Date"], errors="coerce").max()
            if not cached.empty and "Date" in cached and name in cached
            else pd.NaT
        )
        cache_is_fresh = (
            pd.notna(cached_latest)
            and (end - pd.Timestamp(cached_latest).normalize()).days <= 14
            and cached[name].notna().sum() >= 80
        )
        built_in_latest = (
            pd.to_datetime(built_in.loc[built_in[name].notna(), "Date"], errors="coerce").max()
            if name in built_in and built_in[name].notna().any()
            else pd.NaT
        )
        built_in_is_fresh = (
            pd.notna(built_in_latest)
            and (end - pd.Timestamp(built_in_latest).normalize()).days <= 7
            and built_in[name].notna().sum() >= 80
        )
        if cache_is_fresh:
            local_series = cached[["Date", name]].copy()
            merged = merged.merge(local_series, on="Date", how="outer")
            statuses_by_name[name] = _fresh_cached_factor_status(
                name,
                local_series,
                cache_file,
            )
        elif built_in_is_fresh and not force_refresh:
            local_series = built_in[["Date", name]].copy()
            merged = merged.merge(local_series, on="Date", how="outer")
            statuses_by_name[name] = _built_in_factor_status(name, local_series)
        elif not bool(entry.get("auto_download", False)) and name in built_in:
            local_series = built_in[["Date", name]].copy()
            merged = merged.merge(local_series, on="Date", how="outer")
            statuses_by_name[name] = _built_in_factor_status(name, local_series)
        else:
            remote_names.append(name)

    regime = None
    max_workers = min(6, max(1, len(remote_names) + 1))
    with ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="decision-context") as executor:
        regime_future = executor.submit(
            run_markov_crisis_forecast,
            price,
            price_column=target,
            horizon=5,
        )
        factor_futures = {
            executor.submit(
                _fetch_registry_variable,
                registry[name],
                start_date=start.strftime("%Y-%m-%d"),
                end_date=end.strftime("%Y-%m-%d"),
                force_refresh=force_refresh,
            ): name
            for name in remote_names
        }
        for future in as_completed(factor_futures):
            name = factor_futures[future]
            try:
                series, status = future.result()
            except Exception as exc:  # noqa: BLE001 - one factor cannot hide the decision view.
                series = pd.DataFrame(columns=["Date", name])
                status = {
                    "Variable": name,
                    "ActualSource": "unavailable",
                    "Status": "Failed",
                    "Note": str(exc),
                }
            statuses_by_name[name] = status
            if not series.empty and name in series:
                merged = merged.merge(series[["Date", name]], on="Date", how="outer")
        try:
            regime = regime_future.result()
        except Exception:  # noqa: BLE001 - the price forecast remains useful by itself.
            regime = None

    merged = merged.sort_values("Date")
    statuses = [
        statuses_by_name[name]
        for name in DECISION_FACTOR_NAMES
        if name in statuses_by_name
    ]
    return {
        "regime": regime,
        "factors": _factor_associations(merged, target),
        "source_status": statuses,
    }


@st.cache_data(ttl=6 * 60 * 60, max_entries=24, show_spinner=False)
def _cached_price_bundle(
    target: str,
    horizon: int,
    history_months: int,
    data_revision: int,
    _force_refresh: bool = False,
) -> dict[str, Any]:
    from src.price_forecast import run_oil_price_forecast

    del data_revision  # The revision is intentionally part of the cache key.
    price = _load_price_series(target, history_months, force_refresh=_force_refresh)
    result = run_oil_price_forecast(
        price,
        price_column=target,
        horizon=int(horizon),
        max_history=max(500, int(history_months) * 23),
    )
    return {
        "result": result,
        "price": price,
    }


@st.cache_data(ttl=6 * 60 * 60, max_entries=12, show_spinner=False)
def _cached_decision_context(
    target: str,
    history_months: int,
    data_revision: int,
    _price: pd.DataFrame,
    _force_refresh: bool = False,
) -> dict[str, Any]:
    del data_revision  # The revision is intentionally part of the cache key.
    return _load_decision_context(
        _price,
        target,
        history_months,
        force_refresh=_force_refresh,
    )


def _factor_figure(factors: pd.DataFrame, ui_text: UiText) -> go.Figure:
    display = factors.sort_values("EstimatedEffectPercent")
    labels = display["LabelZH"] if ui_text("en", "zh") == "zh" else display["Variable"]
    colors = ["#356B65" if value >= 0 else "#88939A" for value in display["EstimatedEffectPercent"]]
    figure = go.Figure(
        go.Bar(
            x=display["EstimatedEffectPercent"],
            y=labels,
            orientation="h",
            marker_color=colors,
            customdata=display[["CategoryZH", "Correlation", "RecentChangePercent"]].to_numpy(),
            hovertemplate=(
                "%{y}<br>"
                + ui_text("Estimated linked effect", "估算关联影响")
                + ": %{x:+.2f}%<br>"
                + ui_text("Recent change", "该因素近期变化")
                + ": %{customdata[2]:+.2f}%<br>"
                + ui_text("Correlation", "同期相关度")
                + ": %{customdata[1]:+.2f}<extra></extra>"
            ),
        )
    )
    figure.add_vline(x=0, line_color="#BFC5C0", line_width=1)
    figure.update_layout(
        title=dict(text=ui_text("Factors linked to the recent oil move", "近期与油价变化关联较强的因素"), x=0),
        height=480,
        margin=dict(l=18, r=18, t=72, b=18),
        xaxis_title=ui_text("Estimated linked effect on the recent move (%)", "对近期油价变化的估算关联影响（%）"),
        yaxis_title=None,
    )
    return figure


def _imf_story_figure(result: Any, ui_text: UiText) -> go.Figure:
    final_date = result.components["Date"].max()
    frame = result.components.loc[result.components["Date"].eq(final_date)].copy()
    total = max(float(frame["Forecast"].abs().sum()), 1e-12)
    frame["Share"] = frame["Forecast"].abs() / total * 100.0
    frame["Label"] = frame["ChannelZH"] if ui_text("en", "zh") == "zh" else frame["ChannelEN"]
    figure = go.Figure(
        go.Bar(
            x=frame["IMF"],
            y=frame["Share"],
            marker_color=["#2F625D", "#4D7773", "#73908C", "#9AABA6", "#C4CDC8"],
            customdata=frame[["Label", "Forecast"]].to_numpy(),
            text=frame["Label"],
            textposition="outside",
            hovertemplate="%{x}<br>%{customdata[0]}<br>%{y:.1f}%<extra></extra>",
        )
    )
    figure.update_layout(
        title=dict(text=ui_text("How the five rhythms compose the terminal forecast", "五层节奏如何构成期末预测"), x=0),
        height=470,
        margin=dict(l=18, r=18, t=72, b=18),
        yaxis_title=ui_text("Absolute composition share (%)", "模型绝对构成占比（%）"),
        xaxis_title=None,
    )
    return figure


def _risk_figure(regime: Any, ui_text: UiText) -> go.Figure:
    history = regime.probability_history.tail(320)
    figure = go.Figure()
    figure.add_trace(
        go.Scatter(
            x=history["Date"],
            y=history["CrisisRegimeProbability"],
            mode="lines",
            line=dict(color="#356B65", width=2.4),
            fill="tozeroy",
            fillcolor="rgba(53,107,101,0.10)",
            name=ui_text("High-volatility state", "高波动状态"),
            hovertemplate="%{x|%Y-%m-%d}<br>%{y:.1f}%<extra></extra>",
        )
    )
    figure.add_hrect(y0=70, y1=100, fillcolor="rgba(115,80,58,0.07)", line_width=0)
    figure.update_layout(
        title=dict(text=ui_text("Oil high-volatility state", "油价高波动状态变化"), x=0),
        height=450,
        margin=dict(l=18, r=18, t=72, b=18),
        yaxis=dict(title=ui_text("Model probability (%)", "模型概率（%）"), range=[0, 100]),
        xaxis_title=None,
        hovermode="x unified",
    )
    return figure


def render_decision_dashboard(ui_text: UiText, apply_theme: ThemeFunction) -> None:
    """Render the latest result first, followed by one continuous decision story."""
    st.markdown(
        f"""
        <section class="decision-hero view-reveal">
          <div>
            <span>{ui_text("LATEST OIL DECISION", "最新油价决策")}</span>
            <h2>{ui_text("What changed, what may follow, what to do now", "发生了什么，接下来怎么看，现在怎么做")}</h2>
            <p>{ui_text("The page uses the latest successful six-hour snapshot and keeps every conclusion tied to an interactive chart.", "页面优先使用最近一次成功结果，并按 6 小时更新。每条判断都对应一张可交互图表。")}</p>
          </div>
        </section>
        """,
        unsafe_allow_html=True,
    )
    controls = st.columns([1.0, 1.0, 1.0, 1.0, 1.05])
    target = controls[0].selectbox(ui_text("Benchmark", "基准品种"), ["Brent", "WTI"], key="story_target")
    horizon = controls[1].selectbox(
        ui_text("Decision horizon", "观察期限"),
        [5, 10, 20, 60],
        index=2,
        format_func=lambda value: ui_text(f"{value} business days", f"{value} 个交易日"),
        key="story_horizon",
    )
    history_months = controls[2].selectbox(
        ui_text("History", "历史样本"),
        [36, 60, 84],
        index=1,
        format_func=lambda value: ui_text(f"{value} months", f"{value} 个月"),
        key="story_history",
    )
    frequency = controls[3].radio(
        ui_text("Chart", "图表频率"),
        ["daily", "monthly"],
        format_func=lambda value: ui_text("Daily", "日度") if value == "daily" else ui_text("Monthly", "月度"),
        horizontal=True,
        key="story_frequency",
    )
    with controls[4]:
        st.write("")
        refresh = st.button(
            ui_text("Refresh latest data", "更新最新数据"),
            type="primary",
            width="stretch",
            key="story_refresh_latest",
        )
    if refresh:
        st.session_state["story_data_revision"] = int(
            st.session_state.get("story_data_revision", 0)
        ) + 1
    data_revision = int(st.session_state.get("story_data_revision", 0))
    # Retire the old sticky token: one manual refresh must not force every later
    # slider, language or cost-input rerun back onto the network.
    st.session_state.pop("story_refresh_token", None)

    price_loading = st.empty()
    price_loading.info(ui_text(
        "Opening the latest successful price view…",
        "正在打开最近一次成功的价格视图…",
    ))
    try:
        price_bundle = _cached_price_bundle(
            target,
            int(horizon),
            int(history_months),
            data_revision,
            _force_refresh=bool(refresh),
        )
    except Exception as exc:  # noqa: BLE001
        price_loading.empty()
        st.error(ui_text("The latest decision view could not be prepared: ", "最新决策视图生成失败：") + str(exc))
        return
    price_loading.empty()

    result = price_bundle["result"]
    price = price_bundle["price"]
    st.session_state["price_forecast_last_result"] = {
        "target": target, "horizon": int(horizon), "history_months": int(history_months), "result": result,
    }
    metrics = result.metrics
    final = result.forecast.iloc[-1]

    st.markdown(ui_text("### Latest price path", "### 最新油价路径"))
    headline_metrics = st.columns(5)
    headline_metrics[0].metric(ui_text("Data through", "数据截止"), str(metrics["AsOfDate"]))
    headline_metrics[1].metric(ui_text("Latest price", "最新价格"), f"${float(metrics['LatestPrice']):,.2f}")
    headline_metrics[2].metric(ui_text("Expected change", "预测期变化"), f"{float(metrics['ProjectedChangePercent']):+.1f}%")
    headline_metrics[3].metric(ui_text("80% range", "80% 期末区间"), f"{float(final['Lower80']):.1f}-{float(final['Upper80']):.1f}")
    headline_metrics[4].metric(
        ui_text("Holdout direction", "样本外方向命中"),
        f"{float(metrics['DirectionalAccuracyPercent']):.1f}%",
    )
    main_figure = _main_forecast_figure(result, frequency, ui_text)
    apply_theme(main_figure)
    st.plotly_chart(main_figure, width="stretch", config=PLOT_CONFIG, key=f"story_main_{target}_{frequency}")
    st.caption(ui_text(
        "The 50% range is the central path, 80% is the planning range, and 95% is the stress range. The bands are calibrated on an earlier block of data and checked on a later, untouched block.",
        "50% 区间用于观察核心路径，80% 区间用于常规计划，95% 区间用于压力准备。区间先用较早一段数据校准，再用之后未参与校准的数据检验。",
    ))

    st.markdown(ui_text("#### How the forecast held up out of sample", "#### 这套预测在样本外表现如何"))
    validation = st.columns(5)
    for column, level in zip(validation[:3], (50, 80, 95)):
        column.metric(
            ui_text(f"{level}% range coverage", f"{level}% 区间覆盖"),
            f"{float(metrics[f'ValidationCoverage{level}Percent']):.1f}%",
        )
    validation[3].metric(
        ui_text("Directional accuracy", "方向命中率"),
        f"{float(metrics['DirectionalAccuracyPercent']):.1f}%",
    )
    validation[4].metric(
        ui_text("MAE vs last-price baseline", "相对持平基线的 MAE 改善"),
        f"{float(metrics['ValidationSkillPercent']):+.1f}%",
    )
    st.caption(ui_text(
        f"Independent evaluation: {metrics['ValidationStartDate']} to {metrics['ValidationEndDate']} ({int(metrics['ValidationObservations'])} observations). A negative baseline improvement means the simple last-price benchmark did better over that window.",
        f"独立评估期：{metrics['ValidationStartDate']} 至 {metrics['ValidationEndDate']}，共 {int(metrics['ValidationObservations'])} 个观测。若相对基线改善为负，表示这段时间内简单的“价格持平”基线表现更好。",
    ))

    context_loading = st.empty()
    context_loading.info(ui_text(
        "The price view is ready. Linking market factors and the risk state…",
        "价格视图已就绪，正在补充市场关联与风险状态…",
    ))
    try:
        context = _cached_decision_context(
            target,
            int(history_months),
            data_revision,
            _price=price,
            _force_refresh=bool(refresh),
        )
    except Exception as exc:  # noqa: BLE001 - retain the already-rendered price result.
        context = {"regime": None, "factors": pd.DataFrame(), "source_status": []}
        st.warning(ui_text(
            "The price forecast is available, but some market context could not be updated: ",
            "价格预测可正常使用，但部分市场背景暂未更新：",
        ) + str(exc))
    context_loading.empty()
    regime = context.get("regime")
    factors = context.get("factors", pd.DataFrame())
    st.session_state["decision_regime_latest"] = regime
    st.session_state["decision_factors_latest"] = factors
    risk_5d = float(regime.probability_5d) if regime is not None else 0.0
    decision = build_investment_decision(result, high_volatility_probability=risk_5d)
    recommendation = recommend_buyer_hedge(result, high_volatility_probability=risk_5d)

    st.markdown(ui_text("### What has moved alongside oil recently", "### 最近哪些变化与油价同行"))
    st.caption(ui_text(
        "These are recent statistical associations, not proven causes. Positive bars moved with oil over the same period; negative bars moved in the opposite direction.",
        "这里展示的是近期统计关联，不等同于因果关系。正值表示同期与油价同向，负值表示同期反向。",
    ))
    if isinstance(factors, pd.DataFrame) and not factors.empty:
        factor_chart = _factor_figure(factors, ui_text)
        apply_theme(factor_chart)
        st.plotly_chart(factor_chart, width="stretch", config=PLOT_CONFIG, key=f"story_factors_{target}")
        strongest = factors.iloc[0]
        st.info(ui_text(
            f"The strongest recent link is {strongest['Variable']}, with an estimated {strongest['EstimatedEffectPercent']:+.2f}% association with the recent oil move.",
            f"近期关联最强的是“{strongest['LabelZH']}”，对这段油价变化的估算关联影响约为 {strongest['EstimatedEffectPercent']:+.2f}%。",
        ))
    else:
        st.info(ui_text("Factor data are being refreshed. The price forecast remains available.", "外部因素数据正在更新，油价预测仍可正常使用。"))

    st.markdown(ui_text("### How five oil-price rhythms shape the path", "### 五层油价节奏怎样构成预测路径"))
    st.caption(ui_text(
        "The five-IMF method separates short trading noise from progressively slower inventory, demand and financial rhythms. The shares below describe model composition, not causal attribution.",
        "五 IMF 方法把短期交易噪声与更慢的库存、需求和金融节奏分开。下图展示的是模型构成，不是因果归因。",
    ))
    imf_chart = _imf_story_figure(result, ui_text)
    apply_theme(imf_chart)
    st.plotly_chart(imf_chart, width="stretch", config=PLOT_CONFIG, key=f"story_imf_{target}")

    st.markdown(ui_text("### What the risk model sees next", "### 接下来需要警惕什么风险"))
    if regime is not None:
        risk_chart = _risk_figure(regime, ui_text)
        apply_theme(risk_chart)
        st.plotly_chart(risk_chart, width="stretch", config=PLOT_CONFIG, key=f"story_risk_{target}")
        risk_cols = st.columns(3)
        risk_cols[0].metric(ui_text("Current high-volatility state", "当前高波动状态概率"), f"{regime.current_probability:.1%}")
        risk_cols[1].metric(ui_text("Next business day", "下一个交易日"), f"{regime.probability_1d:.1%}")
        risk_cols[2].metric(ui_text("Next 5 business days", "未来 5 个交易日"), f"{regime.probability_5d:.1%}")
        st.caption(ui_text(
            "This is the probability of entering an oil-price high-volatility state, not the probability or date of a geopolitical crisis.",
            "这里预测的是油价进入高波动状态的概率，不是某场地缘危机发生的概率或日期。",
        ))
    else:
        st.info(ui_text(
            "The high-volatility state could not be estimated this time. The price ranges and sample-out checks above remain available.",
            "本次未能稳定估计高波动状态；上方价格区间与样本外检验仍可正常使用。",
        ))

    st.markdown(ui_text("### Decision summary", "### 现在怎么做"))
    investment_col, enterprise_col = st.columns(2)
    with investment_col:
        label = decision.label_zh if ui_text("en", "zh") == "zh" else decision.label
        confidence = decision.confidence_zh if ui_text("en", "zh") == "zh" else decision.confidence
        st.markdown(f"#### {ui_text('Investment research', '投资研究建议')}")
        st.metric(ui_text("Current view", "当前判断"), label)
        st.metric(ui_text("Research exposure band", "研究仓位区间"), f"{decision.position_low:.0%}-{decision.position_high:.0%}")
        st.metric(ui_text("Confidence", "把握程度"), confidence)
        st.caption(decision.gate_reason_zh if ui_text("en", "zh") == "zh" else decision.gate_reason)
    with enterprise_col:
        st.markdown(f"#### {ui_text('Procurement and hedge', '采购成本与套保建议')}")
        st.metric(ui_text("Suggested coverage", "建议套保覆盖"), f"{max(0.0, recommendation.hedge_ratio - .08):.0%}-{min(1.0, recommendation.hedge_ratio + .08):.0%}")
        st.metric(ui_text("Futures layer", "期货锁价部分"), f"{recommendation.futures_share:.0%}")
        st.metric(ui_text("Options layer", "期权弹性部分"), f"{recommendation.options_share:.0%}")
        st.caption(recommendation.rationale_zh if ui_text("en", "zh") == "zh" else recommendation.rationale)

    st.markdown(ui_text("#### Procurement cost warning", "#### 采购成本预警测算"))
    exposure = st.columns(4)
    volume = exposure[0].number_input(ui_text("Purchase volume", "采购量（桶）"), min_value=1_000.0, value=300_000.0, step=10_000.0, key="story_volume")
    budget = exposure[1].number_input(
        ui_text("Budget benchmark price", "预算基准价（美元/桶）"),
        min_value=1.0,
        value=float(metrics["LatestPrice"]),
        step=1.0,
        key="story_budget",
        help=ui_text("The benchmark component of the physical purchase budget, before basis.", "实货采购预算中的基准价格部分，不含基差。"),
    )
    ratio = exposure[2].slider(
        ui_text("Hedge coverage", "套保覆盖比例"),
        0.0,
        1.0,
        _quantize_slider_default(recommendation.hedge_ratio),
        0.05,
        key="story_ratio",
    )
    futures_share = exposure[3].slider(
        ui_text("Futures share", "期货占比"),
        0.0,
        1.0,
        _quantize_slider_default(recommendation.futures_share),
        0.05,
        key="story_futures",
    )

    with st.expander(ui_text("Detailed contract and funding assumptions", "详细合同与资金条件"), expanded=True):
        st.caption(ui_text(
            "Basis and FX affect the physical settlement; margin principal is liquidity usage, while only its funding cost enters procurement cost.",
            "基差和汇率影响实货结算；保证金本金属于资金占用，只有保证金资金成本计入采购净成本。",
        ))
        basis_inputs = st.columns(4)
        budget_basis = basis_inputs[0].number_input(
            ui_text("Budget basis (USD/bbl)", "预算基差（美元/桶）"),
            value=0.0,
            step=0.10,
            key="story_budget_basis",
            help=ui_text("Physical budget price minus its benchmark price.", "预算实货价格减去预算基准价。"),
        )
        purchase_basis = basis_inputs[1].number_input(
            ui_text("Expected purchase basis (USD/bbl)", "预计采购基差（美元/桶）"),
            value=0.0,
            step=0.10,
            key="story_purchase_basis",
            help=ui_text("Expected physical purchase price minus the forecast benchmark price.", "预计实货采购价减去预测基准价。"),
        )
        budget_fx = basis_inputs[2].number_input(
            ui_text("Budget FX (CNY/USD)", "预算汇率（人民币/美元）"),
            min_value=0.01,
            value=7.20,
            step=0.01,
            key="story_budget_fx",
        )
        settlement_fx = basis_inputs[3].number_input(
            ui_text("Settlement FX (CNY/USD)", "结算汇率（人民币/美元）"),
            min_value=0.01,
            value=7.20,
            step=0.01,
            key="story_settlement_fx",
        )

        st.caption(ui_text(
            "Physical-contract additions per barrel: a quality discount can be negative; freight, tax and other costs cannot.",
            "以下均按每桶填写：品质折价可为负数，运费、税费和其他成本不能为负。",
        ))
        physical_cost_inputs = st.columns(4)
        quality_differential = physical_cost_inputs[0].number_input(
            ui_text("Quality differential", "品质升贴水（美元/桶）"),
            value=0.0,
            step=0.10,
            key="story_quality_differential",
        )
        freight = physical_cost_inputs[1].number_input(
            ui_text("Freight", "运费（美元/桶）"),
            min_value=0.0,
            value=0.0,
            step=0.10,
            key="story_freight",
        )
        taxes = physical_cost_inputs[2].number_input(
            ui_text("Taxes and duties", "税费（美元/桶）"),
            min_value=0.0,
            value=0.0,
            step=0.10,
            key="story_taxes",
        )
        other_unit_cost = physical_cost_inputs[3].number_input(
            ui_text("Other unit cost", "其他单位成本（美元/桶）"),
            min_value=0.0,
            value=0.0,
            step=0.10,
            key="story_other_unit_cost",
        )
        budget_cost_inputs = st.columns(4)
        budget_quality_differential = budget_cost_inputs[0].number_input(
            ui_text("Budget quality differential", "预算品质升贴水（美元/桶）"),
            value=0.0,
            step=0.10,
            key="story_budget_quality_differential",
        )
        budget_freight = budget_cost_inputs[1].number_input(
            ui_text("Budget freight", "预算运费（美元/桶）"),
            min_value=0.0,
            value=0.0,
            step=0.10,
            key="story_budget_freight",
        )
        budget_taxes = budget_cost_inputs[2].number_input(
            ui_text("Budget taxes and duties", "预算税费（美元/桶）"),
            min_value=0.0,
            value=0.0,
            step=0.10,
            key="story_budget_taxes",
        )
        budget_other_unit_cost = budget_cost_inputs[3].number_input(
            ui_text("Budget other unit cost", "预算其他单位成本（美元/桶）"),
            min_value=0.0,
            value=0.0,
            step=0.10,
            key="story_budget_other_unit_cost",
        )

        derivative_inputs = st.columns(2)
        futures_entry = derivative_inputs[0].number_input(
            ui_text("Futures entry price", "期货建仓价（美元/桶）"),
            min_value=0.01,
            value=float(metrics["LatestPrice"]),
            step=0.10,
            key="story_futures_entry",
        )
        contract_size = derivative_inputs[1].number_input(
            ui_text("Contract size (barrels)", "每手合约规模（桶）"),
            min_value=1.0,
            value=1_000.0,
            step=100.0,
            key="story_contract_size",
            help=ui_text("Futures volume is rounded to whole contracts.", "期货套保量会按整手合约取整。"),
        )
        option_inputs = st.columns(5)
        option_style = option_inputs[0].selectbox(
            ui_text("Option structure", "期权结构"),
            ["call", "collar", "none"],
            format_func=lambda value: {
                "call": ui_text("Protective call", "买入看涨期权"),
                "collar": ui_text("Buyer collar", "买方领口策略"),
                "none": ui_text("No option", "不使用期权"),
            }[value],
            key="story_option_style",
        )
        option_strike = option_inputs[1].number_input(
            ui_text("Call strike (USD/bbl)", "看涨期权执行价（美元/桶）"),
            min_value=0.01,
            value=float(metrics["LatestPrice"]),
            step=0.10,
            key="story_option_strike",
        )
        option_premium = option_inputs[2].number_input(
            ui_text("Call premium (USD/bbl)", "看涨期权费（美元/桶）"),
            min_value=0.0,
            value=2.0,
            step=0.10,
            key="story_option_premium",
        )
        collar_floor = option_inputs[3].number_input(
            ui_text("Collar floor (USD/bbl)", "领口下限（美元/桶）"),
            min_value=0.01,
            value=float(metrics["LatestPrice"]) * 0.90,
            step=0.10,
            disabled=option_style != "collar",
            key="story_collar_floor",
        )
        collar_put_premium = option_inputs[4].number_input(
            ui_text("Written-put premium", "卖出看跌期权费（美元/桶）"),
            min_value=0.0,
            value=0.0,
            step=0.10,
            disabled=option_style != "collar",
            key="story_collar_put_premium",
        )

        funding_inputs = st.columns(5)
        margin_percent = funding_inputs[0].number_input(
            ui_text("Initial margin (%)", "期货保证金比例（%）"),
            min_value=0.0,
            max_value=100.0,
            value=10.0,
            step=0.5,
            key="story_margin_percent",
        )
        funding_percent = funding_inputs[1].number_input(
            ui_text("Annual funding rate (%)", "年化资金成本（%）"),
            min_value=0.0,
            max_value=100.0,
            value=4.0,
            step=0.25,
            key="story_funding_percent",
        )
        holding_days = funding_inputs[2].number_input(
            ui_text("Hedge holding days", "套保持有天数"),
            min_value=0,
            value=max(1, int(horizon)),
            step=1,
            key="story_holding_days",
        )
        variation_margin_days = funding_inputs[3].number_input(
            ui_text("Variation-margin funding days", "变动保证金融资天数"),
            min_value=0,
            value=max(1, int(horizon)),
            step=1,
            key="story_variation_margin_days",
        )
        futures_fee = funding_inputs[4].number_input(
            ui_text("Round-trip fee / contract", "期货每手双边费用（美元）"),
            min_value=0.0,
            value=10.0,
            step=1.0,
            key="story_futures_fee",
        )

    effective_collar_floor = (
        min(float(collar_floor), float(option_strike))
        if option_style == "collar"
        else None
    )
    if option_style == "collar" and float(collar_floor) > float(option_strike):
        st.warning(ui_text(
            "The collar floor cannot exceed the call strike. This run uses the call strike as the floor; lower the floor to create a meaningful collar.",
            "领口下限不能高于看涨期权执行价。本次测算暂按执行价作为下限；请调低下限，才能形成有效领口区间。",
        ))
    selected_option_premium = float(option_premium) if option_style != "none" else 0.0
    scenarios = build_buyer_hedge_scenarios(
        result,
        exposure_volume=float(volume),
        budget_price=float(budget),
        contract_size=float(contract_size),
        hedge_ratio=float(ratio),
        futures_share=float(futures_share),
        option_strike=float(option_strike),
        option_premium=selected_option_premium,
        option_style=str(option_style),
        collar_floor=effective_collar_floor,
        collar_put_premium=float(collar_put_premium) if option_style == "collar" else 0.0,
        budget_basis=float(budget_basis),
        purchase_basis=float(purchase_basis),
        budget_fx_rate=float(budget_fx),
        settlement_fx_rate=float(settlement_fx),
        futures_entry_price=float(futures_entry),
        margin_rate=float(margin_percent) / 100.0,
        annual_funding_rate=float(funding_percent) / 100.0,
        holding_days=int(holding_days),
        variation_margin_days=int(variation_margin_days),
        futures_fee_per_contract=float(futures_fee),
        quality_differential_per_unit=float(quality_differential),
        freight_per_unit=float(freight),
        taxes_per_unit=float(taxes),
        other_unit_cost=float(other_unit_cost),
        budget_quality_differential_per_unit=float(budget_quality_differential),
        budget_freight_per_unit=float(budget_freight),
        budget_taxes_per_unit=float(budget_taxes),
        budget_other_unit_cost=float(budget_other_unit_cost),
    )
    comparison = compare_buyer_hedge_strategies(
        result,
        exposure_volume=float(volume),
        budget_price=float(budget),
        hedge_ratio=float(ratio),
        futures_share=float(futures_share),
        option_strike=float(option_strike),
        option_premium=float(option_premium),
        collar_floor=effective_collar_floor,
        collar_put_premium=float(collar_put_premium) if option_style == "collar" else 0.0,
        contract_size=float(contract_size),
        budget_basis=float(budget_basis),
        purchase_basis=float(purchase_basis),
        budget_fx_rate=float(budget_fx),
        settlement_fx_rate=float(settlement_fx),
        futures_entry_price=float(futures_entry),
        margin_rate=float(margin_percent) / 100.0,
        annual_funding_rate=float(funding_percent) / 100.0,
        holding_days=int(holding_days),
        variation_margin_days=int(variation_margin_days),
        futures_fee_per_contract=float(futures_fee),
        quality_differential_per_unit=float(quality_differential),
        freight_per_unit=float(freight),
        taxes_per_unit=float(taxes),
        other_unit_cost=float(other_unit_cost),
        budget_quality_differential_per_unit=float(budget_quality_differential),
        budget_freight_per_unit=float(budget_freight),
        budget_taxes_per_unit=float(budget_taxes),
        budget_other_unit_cost=float(budget_other_unit_cost),
    )
    st.markdown(ui_text("##### Compare policies before choosing one", "##### 先比较策略，再决定怎么做"))
    st.caption(ui_text(
        "Every policy uses the same oil-price, basis, FX and physical-cost scenarios. Lower cost is not automatically better: the liquidity chart shows the cash buffer each policy may require.",
        "所有策略使用同一组油价、基差、汇率和实货成本情景。成本更低不等于一定更合适，右侧资金占用图用于检查企业能否承受执行过程中的现金压力。",
    ))
    strategy_column, liquidity_column = st.columns([1.65, 1.0])
    with strategy_column:
        strategy_chart = _strategy_comparison_figure(comparison, ui_text)
        apply_theme(strategy_chart)
        st.plotly_chart(
            strategy_chart,
            width="stretch",
            config=PLOT_CONFIG,
            key=f"story_strategy_compare_{target}",
        )
    with liquidity_column:
        liquidity_chart = _liquidity_stress_figure(comparison, ui_text)
        apply_theme(liquidity_chart)
        st.plotly_chart(
            liquidity_chart,
            width="stretch",
            config=PLOT_CONFIG,
            key=f"story_liquidity_compare_{target}",
        )

    stress = scenarios.iloc[-1]
    st.markdown(ui_text("##### Inspect the selected mix", "##### 查看当前组合的成本拆解"))
    selected_path_column, waterfall_column = st.columns([1.25, 1.0])
    with selected_path_column:
        hedge_chart = _hedge_figure(scenarios, ui_text, currency="CNY")
        apply_theme(hedge_chart)
        st.plotly_chart(
            hedge_chart,
            width="stretch",
            config=PLOT_CONFIG,
            key=f"story_hedge_{target}",
        )
    with waterfall_column:
        waterfall = _cost_waterfall_figure(stress, ui_text)
        apply_theme(waterfall)
        st.plotly_chart(
            waterfall,
            width="stretch",
            config=PLOT_CONFIG,
            key=f"story_cost_waterfall_{target}",
        )
    summary = st.columns(4)
    summary[0].metric(ui_text("95% upper net cost", "95%上界净成本"), f"¥{float(stress['NetCostCNY']):,.0f}")
    summary[1].metric(ui_text("Effective unit cost", "折算单桶成本"), f"¥{float(stress['EffectiveUnitCostCNY']):,.2f}")
    summary[2].metric(ui_text("Variance vs budget", "相对预算偏差"), f"¥{float(stress['BudgetVarianceCNY']):+,.0f}")
    summary[3].metric(ui_text("Initial margin required", "初始保证金占用"), f"¥{float(stress['InitialMarginCNY']):,.0f}")
    impact = st.columns(4)
    impact[0].metric(ui_text("Basis-change impact", "基差变化影响"), f"¥{float(stress['BasisImpactCNY']):+,.0f}")
    impact[1].metric(ui_text("FX impact", "汇兑影响"), f"¥{float(stress['FXImpactCNY']):+,.0f}")
    impact[2].metric(ui_text("Funding and fees", "资金成本与手续费"), f"¥{float(stress['FundingAndFeesCNY']):,.0f}")
    impact[3].metric(ui_text("Rounded futures contracts", "取整后期货手数"), f"{int(stress['FuturesContracts']):,}")
    physical_impact = st.columns(5)
    physical_impact[0].metric(ui_text("Quality impact", "品质变化影响"), f"¥{float(stress['QualityImpactCNY']):+,.0f}")
    physical_impact[1].metric(ui_text("Freight impact", "运费变化影响"), f"¥{float(stress['FreightImpactCNY']):+,.0f}")
    physical_impact[2].metric(ui_text("Tax impact", "税费变化影响"), f"¥{float(stress['TaxesImpactCNY']):+,.0f}")
    physical_impact[3].metric(ui_text("Other-cost impact", "其他成本影响"), f"¥{float(stress['OtherCostImpactCNY']):+,.0f}")
    physical_impact[4].metric(ui_text("Variation margin posted", "变动保证金峰值占用"), f"¥{float(stress['VariationMarginPostedCNY']):,.0f}")
    with st.expander(ui_text("Scenario calculation details", "查看各情景计算明细")):
        detail_columns = [
            "ScenarioZH", "OilPrice", "PurchaseBasis", "QualityDifferentialPerUnit",
            "FreightPerUnit", "TaxesPerUnit", "OtherUnitCost", "PhysicalUnitPrice",
            "PhysicalCostCNY", "FuturesPnL", "OptionPayoff", "OptionPremium",
            "InitialMarginCNY", "VariationMarginPostedCNY", "LiquidityRequirementCNY",
            "FundingAndFeesCNY", "NetCostCNY", "BudgetVarianceCNY", "EffectiveUnitCostCNY",
        ]
        st.dataframe(scenarios[detail_columns], width="stretch", hide_index=True)
        st.download_button(
            ui_text("Download strategy comparison", "下载策略对比明细"),
            data=comparison.to_csv(index=False).encode("utf-8-sig"),
            file_name=f"{target.lower()}_hedge_strategy_comparison.csv",
            mime="text/csv",
            width="stretch",
            key="download_story_strategy_comparison",
        )
    st.download_button(
        ui_text("Download detailed cost scenarios", "下载详细成本情景"),
        data=scenarios.to_csv(index=False).encode("utf-8-sig"),
        file_name=f"{target.lower()}_detailed_procurement_scenarios.csv",
        mime="text/csv",
        width="stretch",
        key="download_story_hedge_scenarios",
    )
    st.warning(ui_text(
        "Research calculation only. Confirm contract specifications, tax, brokerage rules, liquidity, variation margin and accounting treatment before execution.",
        "以上为研究测算。实际执行前仍需确认合约规格、税费与经纪规则、流动性、追加保证金安排及会计处理。",
    ))

    # Persistence is deliberately last: a slow or unavailable remote database
    # must never postpone the charts and controls the user came to see.
    snapshot_signature = f"{target}|{horizon}|{history_months}|{metrics['AsOfDate']}"
    if st.session_state.get("story_saved_snapshot") != snapshot_signature:
        try:
            ResearchStore(database_url=_story_database_url() or None).save_snapshot(
                "oil_decision",
                target,
                str(metrics["AsOfDate"]),
                {
                    "parameters": {"horizon": int(horizon), "history_months": int(history_months)},
                    "metrics": dict(metrics),
                    "high_volatility_probability_5d": risk_5d,
                    "investment_decision": asdict(decision),
                    "hedge_recommendation": asdict(recommendation),
                },
            )
            st.session_state["story_saved_snapshot"] = snapshot_signature
        except Exception:  # noqa: BLE001 - persistence cannot hide a successful analysis.
            pass
