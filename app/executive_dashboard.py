"""Decision cockpit UI built on top of the existing research forecast."""

from __future__ import annotations

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


UiText = Callable[[str, str], str]
ThemeFunction = Callable[[Any], Any]
PLOT_CONFIG = {
    "scrollZoom": True,
    "displaylogo": False,
    "responsive": True,
    "modeBarButtonsToRemove": ["lasso2d"],
    "toImageButtonOptions": {"format": "png", "scale": 2},
}


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
            line=dict(color="#42656D", width=2.2),
            hovertemplate="%{x|%Y-%m-%d}<br>$%{y:,.2f}<extra></extra>",
        )
    )
    if not forecast_view.empty:
        figure.add_trace(
            go.Scatter(
                x=forecast_view["Date"],
                y=forecast_view["Upper80"],
                mode="lines",
                line=dict(color="rgba(242,106,75,0.30)", width=1),
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
                fillcolor="rgba(242,106,75,0.15)",
                line=dict(color="rgba(242,106,75,0.42)", width=1),
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
                line=dict(color="#F26A4B", width=3),
                marker=dict(size=5, color="#F6A187"),
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
        rangeslider=dict(visible=True, thickness=0.08, bgcolor="#EAF1EF"),
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
    colors = ["#F26A4B" if value >= 0 else "#3E83F8" for value in final["Forecast"]]
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
            marker_color="#F26A4B",
            hovertemplate="%{x}<br>$%{y:,.0f}<extra></extra>",
        )
    )
    figure.add_trace(
        go.Scatter(
            x=labels,
            y=scenarios["BudgetCost"],
            mode="lines",
            name=ui_text("Budget", "预算"),
            line=dict(color="#173238", width=2, dash="dash"),
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


def render_decision_dashboard(ui_text: UiText, apply_theme: ThemeFunction) -> None:
    """Render the investor/enterprise result layer without exposing model plumbing."""
    st.markdown(
        f'<p class="section-kicker">{ui_text("DECISION COCKPIT", "决策驾驶舱")}</p>',
        unsafe_allow_html=True,
    )
    st.markdown(
        f"""
        <section class="decision-hero">
          <div>
            <span>{ui_text("ONE MODEL · TWO DECISIONS", "一套模型 · 两类决策")}</span>
            <h2>{ui_text("Turn oil-market research into an actionable view", "把油价研究结果转换成可执行的决策视图")}</h2>
            <p>{ui_text("The five-IMF forecast, validation and risk state stay unchanged. This layer only changes how results are organized for investment research and enterprise procurement hedging.", "底层的五个 IMF 分量预测、样本外验证和风险状态保持不变；这里只按照投资研究和企业采购套保的需要重新组织结果。")}</p>
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
            ui_text("Refresh & build decision view", "更新并生成决策视图"),
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
            "选择基准品种后生成决策视图；如果设置相同，系统会直接复用已有预测结果。",
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
    metric_columns[2].metric(ui_text("80% terminal range", "80%期末区间"), f"{float(final['Lower80']):.1f}–{float(final['Upper80']):.1f} USD/bbl")
    metric_columns[3].metric(ui_text("Directional accuracy", "方向准确率"), f"{float(metrics['DirectionalAccuracyPercent']):.1f}%")
    metric_columns[4].metric(ui_text("5-day high-volatility", "未来5日高波动概率"), f"{high_volatility * 100:.1f}%" if high_volatility else ui_text("Not run", "尚未计算"))

    mode = st.radio(
        ui_text("Decision user", "决策用户"),
        ["investment", "enterprise"],
        format_func=lambda value: ui_text("Investment research", "期货投资研究") if value == "investment" else ui_text("Enterprise procurement hedge", "企业采购套保"),
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
            st.metric(ui_text("Research position band", "参考仓位区间"), f"{decision.position_low:.0%}–{decision.position_high:.0%}")
            st.metric(ui_text("Signal confidence", "信号可信度"), confidence)
            st.metric(ui_text("Invalidation boundary", "观点失效价"), f"${decision.invalidation_price:,.2f}")
            st.caption(gate_reason)
            st.warning(ui_text(
                "Research signal only. It does not account for an individual's leverage, margin or suitability.",
                "仅为研究信号，未考虑个人杠杆、保证金承受能力与适当性。",
            ))
        else:
            st.markdown(f"### {ui_text('Procurement hedge view', '采购套保视图')}")
            st.metric(ui_text("Suggested coverage band", "建议覆盖比例"), f"{max(0.0, recommendation.hedge_ratio - 0.08):.0%}–{min(1.0, recommendation.hedge_ratio + 0.08):.0%}")
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
