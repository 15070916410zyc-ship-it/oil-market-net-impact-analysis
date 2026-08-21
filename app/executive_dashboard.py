"""Decision cockpit UI built on top of the existing research forecast."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any, Callable

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.data_governance import aggregate_time_series
from src.decision_support import (
    build_buyer_hedge_scenarios,
    build_investment_decision,
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


def _story_database_url() -> str:
    try:
        return str(st.secrets.get("DATABASE_URL", "") or "").strip()
    except Exception:  # pragma: no cover - local secrets are optional.
        return ""


def _high_volatility_probability() -> float:
    payload = st.session_state.get("warning_last_result")
    if not isinstance(payload, dict):
        return 0.0
    regime = payload.get("regime_forecast")
    if regime is None:
        return 0.0
    value = getattr(regime, "probability_5d", 0.0)
    value = float(value)
    return value / 100.0 if value > 1.0 else value


def _run_forecast(target: str, horizon: int, history_months: int) -> Any:
    from src.data_fetcher import RAW_CACHE_FILES, SERIES_SOURCES, fetch_series_with_fallback
    from src.price_forecast import run_oil_price_forecast

    end = pd.Timestamp.today().normalize()
    start = (end - pd.DateOffset(months=int(history_months))).normalize()
    data = fetch_series_with_fallback(
        target,
        SERIES_SOURCES[target],
        start.strftime("%Y-%m-%d"),
        end.strftime("%Y-%m-%d"),
        RAW_CACHE_FILES[target],
        force_refresh=True,
    )
    if data.empty or target not in data or data[target].notna().sum() < 180:
        raise ValueError(f"No sufficiently current {target} series is available.")
    result = run_oil_price_forecast(
        data,
        price_column=target,
        horizon=int(horizon),
        max_history=max(180, int(history_months) * 23),
    )
    st.session_state["price_forecast_last_result"] = {
        "target": target,
        "horizon": int(horizon),
        "history_months": int(history_months),
        "result": result,
    }
    return result


def _forecast_result(target: str, horizon: int, history_months: int) -> Any | None:
    payload = st.session_state.get("price_forecast_last_result")
    if not isinstance(payload, dict):
        return None
    if (
        payload.get("target") != target
        or int(payload.get("horizon", -1)) != int(horizon)
        or int(payload.get("history_months", -1)) != int(history_months)
    ):
        return None
    return payload.get("result")


def _main_forecast_figure(result: Any, frequency: str, ui_text: UiText) -> go.Figure:
    history = result.history.rename(columns={"Actual": "Price"})
    forecast = result.forecast.copy()
    history_view = aggregate_time_series(history, frequency, methods={"Price": "last"})
    forecast_view = aggregate_time_series(
        forecast,
        frequency,
        methods={column: "last" for column in forecast.columns if column != "Date"},
    )
    figure = go.Figure()
    figure.add_trace(
        go.Scatter(
            x=history_view["Date"],
            y=history_view["Price"],
            mode="lines",
            name=ui_text("Observed", "实际价格"),
            line=dict(color="#354554", width=2.2),
            hovertemplate="%{x|%Y-%m-%d}<br>$%{y:,.2f}<extra></extra>",
        )
    )
    if not forecast_view.empty:
        figure.add_trace(
            go.Scatter(
                x=forecast_view["Date"],
                y=forecast_view["Upper80"],
                mode="lines",
                line=dict(color="rgba(53,107,101,0.24)", width=1),
                hoverinfo="skip",
                showlegend=False,
            )
        )
        figure.add_trace(
            go.Scatter(
                x=forecast_view["Date"],
                y=forecast_view["Lower80"],
                mode="lines",
                name=ui_text("80% empirical range", "80%经验区间"),
                fill="tonexty",
                fillcolor="rgba(53,107,101,0.12)",
                line=dict(color="rgba(53,107,101,0.38)", width=1),
                customdata=forecast_view[["Lower80", "Upper80"]].to_numpy(),
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
            name=ui_text("Five-IMF forecast", "五个 IMF 分量预测"),
                line=dict(color="#356B65", width=3),
                marker=dict(size=5, color="#6F9189"),
                hovertemplate="%{x|%Y-%m-%d}<br>$%{y:,.2f}<extra></extra>",
            )
        )
    figure.update_layout(
        title=dict(text=ui_text("Market path & decision range", "市场路径与决策区间"), x=0),
        height=590,
        margin=dict(l=12, r=12, t=72, b=12),
        hovermode="x unified",
        dragmode="pan",
        legend=dict(orientation="h", y=1.04, x=0),
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


def _component_figure(result: Any, ui_text: UiText) -> go.Figure:
    components = result.components.copy()
    final_date = components["Date"].max()
    final = components.loc[components["Date"] == final_date].copy()
    final["Channel"] = final["ChannelZH"] if ui_text("en", "zh") == "zh" else final["ChannelEN"]
    colors = ["#356B65" if value >= 0 else "#88939A" for value in final["Forecast"]]
    figure = go.Figure(
        go.Bar(
            x=final["Forecast"],
            y=final["Channel"],
            orientation="h",
            marker_color=colors,
            customdata=final[["IMF"]].to_numpy(),
            hovertemplate="%{y}<br>%{customdata[0]}: %{x:+.3f}<extra></extra>",
        )
    )
    figure.update_layout(
        title=dict(text=ui_text("Five-channel contribution at horizon end", "预测期末五类通道贡献"), x=0),
        height=390,
        margin=dict(l=12, r=12, t=64, b=12),
        xaxis_title=ui_text("Price contribution", "价格贡献"),
        yaxis_title=None,
    )
    return figure


def _hedge_figure(scenarios: pd.DataFrame, ui_text: UiText) -> go.Figure:
    labels = scenarios["ScenarioZH"] if ui_text("en", "zh") == "zh" else scenarios["Scenario"]
    figure = go.Figure()
    figure.add_trace(
        go.Bar(
            x=labels,
            y=scenarios["PhysicalCost"],
            name=ui_text("Unhedged physical cost", "未套保采购成本"),
            marker_color="#5A6870",
            hovertemplate="%{x}<br>$%{y:,.0f}<extra></extra>",
        )
    )
    figure.add_trace(
        go.Bar(
            x=labels,
            y=scenarios["NetCost"],
            name=ui_text("Net cost after hedge", "套保后净成本"),
            marker_color="#356B65",
            hovertemplate="%{x}<br>$%{y:,.0f}<extra></extra>",
        )
    )
    figure.add_trace(
        go.Scatter(
            x=labels,
            y=scenarios["BudgetCost"],
            mode="lines",
            name=ui_text("Budget", "预算"),
            line=dict(color="#354554", width=2, dash="dash"),
            hovertemplate="%{x}<br>$%{y:,.0f}<extra></extra>",
        )
    )
    figure.update_layout(
        title=dict(text=ui_text("Procurement cost under forecast scenarios", "预测情景下的采购成本"), x=0),
        height=420,
        margin=dict(l=12, r=12, t=64, b=12),
        barmode="group",
        hovermode="x unified",
        yaxis_title=ui_text("USD", "美元"),
        legend=dict(orientation="h", y=1.03),
    )
    return figure


def _render_legacy_decision_dashboard(ui_text: UiText, apply_theme: ThemeFunction) -> None:
    """Render the investor/enterprise result layer without exposing model plumbing."""
    st.markdown(
        f'<p class="section-kicker">{ui_text("MARKET OUTLOOK", "市场判断")}</p>',
        unsafe_allow_html=True,
    )
    st.markdown(
        f"""
        <section class="decision-hero">
          <div>
            <span>{ui_text("ONE METHOD, TWO USE CASES", "同一套方法，两种用法")}</span>
            <h2>{ui_text("Today's market outlook", "今天的市场判断")}</h2>
            <p>{ui_text("Read the direction and range first, then decide whether action is needed. The five-component forecast, validation and risk checks remain unchanged.", "先看方向和区间，再决定是否需要行动。五个 IMF 分量预测、样本外检验和风险判断都保留原样。")}</p>
          </div>
        </section>
        """,
        unsafe_allow_html=True,
    )

    target_col, horizon_col, sample_col, frequency_col, action_col = st.columns([1, 1, 1, 1, 1.3])
    target = target_col.selectbox(ui_text("Benchmark", "基准品种"), ["Brent", "WTI"], key="executive_target")
    horizon = horizon_col.selectbox(
        ui_text("Decision horizon", "决策期限"),
        [5, 10, 20, 60],
        index=2,
        format_func=lambda value: ui_text(f"{value} business days", f"{value}个交易日"),
        key="executive_horizon",
    )
    history_months = sample_col.selectbox(
        ui_text("Research sample", "研究样本"),
        [24, 36, 60, 84],
        index=2,
        format_func=lambda value: ui_text(f"{value} months", f"{value}个月"),
        key="executive_history_months",
    )
    frequency = frequency_col.radio(
        ui_text("Chart frequency", "图表频率"),
        ["daily", "monthly"],
        format_func=lambda value: ui_text("Daily", "日度") if value == "daily" else ui_text("Monthly", "月度"),
        horizontal=True,
        key="executive_frequency",
    )
    with action_col:
        st.write("")
        run = st.button(
            ui_text("Refresh outlook", "重新计算"),
            type="primary",
            use_container_width=True,
            key="executive_run_forecast",
        )
    result = _forecast_result(target, int(horizon), int(history_months))
    if run:
        with st.status(ui_text("Refreshing data and running the existing model…", "正在更新数据并运行现有模型……"), expanded=True) as status:
            try:
                result = _run_forecast(target, int(horizon), int(history_months))
                status.update(label=ui_text("Decision view ready", "决策视图已生成"), state="complete", expanded=False)
            except Exception as exc:  # noqa: BLE001
                status.update(label=ui_text("Decision view failed", "决策视图生成失败"), state="error")
                st.error(str(exc))
                result = None
    if result is None:
        st.info(ui_text(
            "Choose a benchmark and build the decision view. Existing forecast results are reused when the settings match.",
            "选择品种和观察周期后，即可查看最新判断。相同设置会直接使用已有结果。",
        ))
        return

    metrics = result.metrics
    high_volatility = _high_volatility_probability()
    decision = build_investment_decision(result, high_volatility_probability=high_volatility)
    recommendation = recommend_buyer_hedge(result, high_volatility_probability=high_volatility)
    final = result.forecast.iloc[-1]
    metric_columns = st.columns(5)
    metric_columns[0].metric(ui_text("Latest price", "最新价格"), f"${float(metrics['LatestPrice']):,.2f}")
    metric_columns[1].metric(ui_text("Horizon change", "预测期涨跌"), f"{float(metrics['ProjectedChangePercent']):+.1f}%")
    metric_columns[2].metric(ui_text("80% terminal range", "80%期末区间"), f"{float(final['Lower80']):.1f}-{float(final['Upper80']):.1f} USD/bbl")
    metric_columns[3].metric(ui_text("Directional accuracy", "方向准确率"), f"{float(metrics['DirectionalAccuracyPercent']):.1f}%")
    metric_columns[4].metric(ui_text("5-day high-volatility", "未来5日高波动概率"), f"{high_volatility * 100:.1f}%" if high_volatility else ui_text("Not run", "尚未计算"))

    mode = st.radio(
        ui_text("How will you use this view?", "你准备怎么用这份判断？"),
        ["investment", "enterprise"],
        format_func=lambda value: ui_text("Investment view", "投资判断") if value == "investment" else ui_text("Procurement hedge", "采购套保"),
        horizontal=True,
        key="executive_user_mode",
    )
    main_col, conclusion_col = st.columns([2.15, 0.85])
    with main_col:
        figure = _main_forecast_figure(result, frequency, ui_text)
        apply_theme(figure)
        st.plotly_chart(figure, use_container_width=True, config=PLOT_CONFIG, key=f"executive_main_{target}_{frequency}")
    with conclusion_col:
        if mode == "investment":
            label = decision.label_zh if ui_text("en", "zh") == "zh" else decision.label
            confidence = decision.confidence_zh if ui_text("en", "zh") == "zh" else decision.confidence
            gate_reason = decision.gate_reason_zh if ui_text("en", "zh") == "zh" else decision.gate_reason
            st.markdown(f"### {label}")
            st.metric(ui_text("Research position band", "建议仓位"), f"{decision.position_low:.0%}-{decision.position_high:.0%}")
            st.metric(ui_text("Signal confidence", "信号把握"), confidence)
            st.metric(ui_text("Invalidation boundary", "判断失效价"), f"${decision.invalidation_price:,.2f}")
            st.caption(gate_reason)
            st.warning(ui_text(
                "Research signal only. It does not account for an individual's leverage, margin or suitability.",
                "仅为研究信号，未考虑个人杠杆、保证金承受能力与适当性。",
            ))
        else:
            st.markdown(f"### {ui_text('Procurement hedge view', '采购套保建议')}")
            st.metric(ui_text("Suggested coverage band", "建议覆盖比例"), f"{max(0.0, recommendation.hedge_ratio - 0.08):.0%}-{min(1.0, recommendation.hedge_ratio + 0.08):.0%}")
            st.metric(ui_text("Futures layer", "期货层"), f"{recommendation.futures_share:.0%}")
            st.metric(ui_text("Options layer", "期权层"), f"{recommendation.options_share:.0%}")
            st.caption(recommendation.rationale_zh if ui_text("en", "zh") == "zh" else recommendation.rationale)
            st.warning(ui_text(
                "The policy range must be approved by finance and risk teams before execution.",
                "实际执行比例须由企业财务与风险部门审批。",
            ))

    if mode == "investment":
        channel_figure = _component_figure(result, ui_text)
        apply_theme(channel_figure)
        st.plotly_chart(channel_figure, use_container_width=True, config=PLOT_CONFIG, key=f"executive_components_{target}")
        direction = ui_text("upward", "偏强") if float(metrics["ProjectedChangePercent"]) >= 0 else ui_text("downward", "偏弱")
        st.markdown(ui_text(
            f"**What changed:** the {target} path is {direction} over {horizon} business days.  \n**Why it matters:** the five IMF components are converted into channel contributions above.  \n**Decision boundary:** use the empirical interval and validation gate, not the point forecast alone.",
            f"**市场判断：** {target}未来{horizon}个交易日的预测路径{direction}。  \n**主要依据：** 上图把五个 IMF 分量转换为对应的经济通道贡献。  \n**使用边界：** 必须同时参考经验预测区间和样本外验证结果，不能只看点预测。",
        ))
    else:
        st.markdown(f"#### {ui_text('Enterprise exposure inputs', '企业风险敞口输入')}")
        input_columns = st.columns(5)
        volume = input_columns[0].number_input(ui_text("Purchase volume (barrels)", "采购量（桶）"), min_value=1_000.0, value=300_000.0, step=10_000.0, key="hedge_volume")
        budget = input_columns[1].number_input(ui_text("Budget price", "预算单价"), min_value=1.0, value=float(metrics["LatestPrice"]), step=1.0, key="hedge_budget")
        ratio = input_columns[2].slider(ui_text("Hedge coverage", "套保覆盖比例"), 0.0, 1.0, float(round(recommendation.hedge_ratio, 2)), 0.05, key="hedge_ratio")
        futures_share = input_columns[3].slider(ui_text("Futures share", "期货占比"), 0.0, 1.0, float(round(recommendation.futures_share, 2)), 0.05, key="hedge_futures_share")
        premium = input_columns[4].number_input(ui_text("Call premium / barrel", "看涨期权费/桶"), min_value=0.0, value=2.0, step=0.25, key="hedge_option_premium")
        scenarios = build_buyer_hedge_scenarios(
            result,
            exposure_volume=float(volume),
            budget_price=float(budget),
            hedge_ratio=float(ratio),
            futures_share=float(futures_share),
            option_premium=float(premium),
        )
        hedge_figure = _hedge_figure(scenarios, ui_text)
        apply_theme(hedge_figure)
        st.plotly_chart(hedge_figure, use_container_width=True, config=PLOT_CONFIG, key=f"executive_hedge_{target}")
        stress = scenarios.iloc[-1]
        st.markdown(ui_text(
            f"**Exposure:** {volume:,.0f} barrels with a ${budget:,.2f} budget price.  \n**Stress result:** at the 95% upper path, hedging changes net procurement cost to ${float(stress['NetCost']):,.0f}.  \n**Execution boundary:** contract rounding, basis, FX, liquidity and margin must be confirmed against the enterprise's physical contract.",
            f"**风险敞口：** 采购{volume:,.0f}桶，预算单价${budget:,.2f}。  \n**压力结果：** 在95%上界情景下，套保后净采购成本为${float(stress['NetCost']):,.0f}。  \n**执行边界：** 合约取整、基差、汇率、流动性和保证金必须结合企业实货合同确认。",
        ))
        csv_data = scenarios.to_csv(index=False).encode("utf-8-sig")
        st.download_button(
            ui_text("Download hedge scenarios", "下载套保情景"),
            data=csv_data,
            file_name=f"{target.lower()}_hedge_scenarios.csv",
            mime="text/csv",
            use_container_width=True,
            key="download_hedge_scenarios",
        )


# The original dashboard above remains as a compatibility reference for saved
# Streamlit states. This result-first renderer intentionally overrides it.
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


def _load_decision_data(
    target: str,
    history_months: int,
    *,
    force_refresh: bool,
) -> tuple[pd.DataFrame, pd.DataFrame, list[dict[str, Any]]]:
    from src.data_fetcher import RAW_CACHE_FILES, SERIES_SOURCES, fetch_series_with_fallback
    from src.variable_pool import _fetch_registry_variable, load_variable_registry

    end = pd.Timestamp.today().normalize()
    start = (end - pd.DateOffset(months=int(history_months))).normalize()
    price = fetch_series_with_fallback(
        target,
        SERIES_SOURCES[target],
        start.strftime("%Y-%m-%d"),
        end.strftime("%Y-%m-%d"),
        RAW_CACHE_FILES[target],
        force_refresh=force_refresh,
    )
    factor_names = [
        "OVX", "VIX", "DollarIndex", "TNote10Y", "Gold",
        "Copper", "NaturalGas", "CrudeStocks", "GPRD",
    ]
    registry = {entry["name"]: entry for entry in load_variable_registry()}
    merged = price[["Date", target]].copy()
    statuses: list[dict[str, Any]] = []
    for name in factor_names:
        entry = registry.get(name)
        if not entry:
            continue
        series, status = _fetch_registry_variable(
            entry,
            start_date=start.strftime("%Y-%m-%d"),
            end_date=end.strftime("%Y-%m-%d"),
            force_refresh=force_refresh,
        )
        statuses.append(status)
        if not series.empty and name in series:
            merged = merged.merge(series[["Date", name]], on="Date", how="outer")
    merged = merged.sort_values("Date")
    return price, merged, statuses


@st.cache_data(ttl=6 * 60 * 60, show_spinner=False)
def _cached_decision_bundle(
    target: str,
    horizon: int,
    history_months: int,
    refresh_token: int,
) -> dict[str, Any]:
    from src.crisis_regime import run_markov_crisis_forecast
    from src.price_forecast import run_oil_price_forecast

    force_refresh = refresh_token > 0
    price, factors_frame, statuses = _load_decision_data(
        target,
        history_months,
        force_refresh=force_refresh,
    )
    result = run_oil_price_forecast(
        price,
        price_column=target,
        horizon=int(horizon),
        max_history=max(500, int(history_months) * 23),
    )
    try:
        regime = run_markov_crisis_forecast(price, price_column=target, horizon=5)
    except Exception:  # noqa: BLE001 - forecast remains useful without a converged regime fit.
        regime = None
    return {
        "result": result,
        "regime": regime,
        "factors": _factor_associations(factors_frame, target),
        "source_status": statuses,
    }


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
        title=dict(text=ui_text("Which oil-price rhythms dominate the forecast", "油价自身哪几层波动更重要"), x=0),
        height=470,
        margin=dict(l=18, r=18, t=72, b=18),
        yaxis_title=ui_text("Share of the final forecast move (%)", "预测期末波动贡献占比（%）"),
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
        refresh = st.button(ui_text("Refresh latest data", "更新最新数据"), type="primary", use_container_width=True)
    if refresh:
        st.session_state["story_refresh_token"] = int(st.session_state.get("story_refresh_token", 0)) + 1
    refresh_token = int(st.session_state.get("story_refresh_token", 0))

    try:
        with st.spinner(ui_text("Preparing the latest decision view…", "正在准备最新决策视图…")):
            bundle = _cached_decision_bundle(target, int(horizon), int(history_months), refresh_token)
    except Exception as exc:  # noqa: BLE001
        st.error(ui_text("The latest decision view could not be prepared: ", "最新决策视图生成失败：") + str(exc))
        return

    result = bundle["result"]
    regime = bundle.get("regime")
    factors = bundle.get("factors", pd.DataFrame())
    st.session_state["price_forecast_last_result"] = {
        "target": target, "horizon": int(horizon), "history_months": int(history_months), "result": result,
    }
    st.session_state["decision_regime_latest"] = regime
    st.session_state["decision_factors_latest"] = factors
    metrics = result.metrics
    risk_5d = float(regime.probability_5d) if regime is not None else 0.0
    decision = build_investment_decision(result, high_volatility_probability=risk_5d)
    recommendation = recommend_buyer_hedge(result, high_volatility_probability=risk_5d)
    final = result.forecast.iloc[-1]

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

    st.markdown(ui_text("### Latest price path", "### 最新油价路径"))
    headline_metrics = st.columns(5)
    headline_metrics[0].metric(ui_text("Data through", "数据截止"), str(metrics["AsOfDate"]))
    headline_metrics[1].metric(ui_text("Latest price", "最新价格"), f"${float(metrics['LatestPrice']):,.2f}")
    headline_metrics[2].metric(ui_text("Expected change", "预测期变化"), f"{float(metrics['ProjectedChangePercent']):+.1f}%")
    headline_metrics[3].metric(ui_text("80% range", "80% 期末区间"), f"{float(final['Lower80']):.1f}-{float(final['Upper80']):.1f}")
    headline_metrics[4].metric(ui_text("5-day volatility risk", "未来 5 日高波动风险"), f"{risk_5d:.1%}" if regime else ui_text("Unavailable", "暂不可用"))
    main_figure = _main_forecast_figure(result, frequency, ui_text)
    apply_theme(main_figure)
    st.plotly_chart(main_figure, use_container_width=True, config=PLOT_CONFIG, key=f"story_main_{target}_{frequency}")

    st.markdown(ui_text("### What has been moving oil recently", "### 最近哪些因素在影响油价"))
    st.caption(ui_text(
        "The estimates show recent statistical links, not proven causality. Positive bars moved with oil; negative bars moved against it.",
        "这里展示的是近期统计关联，不代表已经证明因果。正值表示与油价同向，负值表示反向。",
    ))
    if isinstance(factors, pd.DataFrame) and not factors.empty:
        factor_chart = _factor_figure(factors, ui_text)
        apply_theme(factor_chart)
        st.plotly_chart(factor_chart, use_container_width=True, config=PLOT_CONFIG, key=f"story_factors_{target}")
        strongest = factors.iloc[0]
        st.info(ui_text(
            f"The strongest recent link is {strongest['Variable']}, with an estimated {strongest['EstimatedEffectPercent']:+.2f}% association with the recent oil move.",
            f"近期关联最强的是“{strongest['LabelZH']}”，对这段油价变化的估算关联影响约为 {strongest['EstimatedEffectPercent']:+.2f}%。",
        ))
    else:
        st.info(ui_text("Factor data are being refreshed. The price forecast remains available.", "外部因素数据正在更新，油价预测仍可正常使用。"))

    st.markdown(ui_text("### Which parts of oil's own movement matter", "### 油价自身哪几层波动更重要"))
    st.caption(ui_text(
        "The model separates oil into five rhythms, from short market noise to slower demand and financial cycles.",
        "系统把油价拆成五层节奏，从短期交易波动到更慢的供需与金融周期。",
    ))
    imf_chart = _imf_story_figure(result, ui_text)
    apply_theme(imf_chart)
    st.plotly_chart(imf_chart, use_container_width=True, config=PLOT_CONFIG, key=f"story_imf_{target}")

    st.markdown(ui_text("### What the risk model sees next", "### 接下来需要警惕什么风险"))
    if regime is not None:
        risk_chart = _risk_figure(regime, ui_text)
        apply_theme(risk_chart)
        st.plotly_chart(risk_chart, use_container_width=True, config=PLOT_CONFIG, key=f"story_risk_{target}")
        risk_cols = st.columns(3)
        risk_cols[0].metric(ui_text("Current high-volatility state", "当前高波动状态概率"), f"{regime.current_probability:.1%}")
        risk_cols[1].metric(ui_text("Next business day", "下一个交易日"), f"{regime.probability_1d:.1%}")
        risk_cols[2].metric(ui_text("Next 5 business days", "未来 5 个交易日"), f"{regime.probability_5d:.1%}")
        st.caption(ui_text(
            "This is the probability of entering an oil-price high-volatility state, not the probability or date of a geopolitical crisis.",
            "这里预测的是油价进入高波动状态的概率，不是某场地缘危机发生的概率或日期。",
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
    budget = exposure[1].number_input(ui_text("Budget price", "预算单价"), min_value=1.0, value=float(metrics["LatestPrice"]), step=1.0, key="story_budget")
    ratio = exposure[2].slider(ui_text("Hedge coverage", "套保覆盖比例"), 0.0, 1.0, float(round(recommendation.hedge_ratio, 2)), 0.05, key="story_ratio")
    futures_share = exposure[3].slider(ui_text("Futures share", "期货占比"), 0.0, 1.0, float(round(recommendation.futures_share, 2)), 0.05, key="story_futures")
    scenarios = build_buyer_hedge_scenarios(
        result,
        exposure_volume=float(volume),
        budget_price=float(budget),
        hedge_ratio=float(ratio),
        futures_share=float(futures_share),
        option_premium=2.0,
    )
    hedge_chart = _hedge_figure(scenarios, ui_text)
    apply_theme(hedge_chart)
    st.plotly_chart(hedge_chart, use_container_width=True, config=PLOT_CONFIG, key=f"story_hedge_{target}")
    st.warning(ui_text(
        "Research output only. Investment suitability, physical-contract basis, FX, liquidity and margin must be checked before execution.",
        "以上仅为研究建议。实际执行前仍需核对投资适当性，以及企业合同中的基差、汇率、流动性和保证金条件。",
    ))
