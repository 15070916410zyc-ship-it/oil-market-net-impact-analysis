"""Searchable official-data center and source-governance UI."""

from __future__ import annotations

from typing import Any, Callable

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.api_variable_catalog import (
    EIA_DATASET_ROUTES,
    catalog_item_to_registry_entry,
    search_eia_datasets,
    search_official_catalogs,
)
from src.data_governance import aggregate_time_series, audit_registry_sources
from src.variable_pool import load_variable_registry


UiText = Callable[[str, str], str]
ThemeFunction = Callable[[Any], Any]
PLOT_CONFIG = {"scrollZoom": True, "displaylogo": False, "responsive": True}


def _search_result_label(item: dict[str, Any]) -> str:
    return (
        f"{item.get('source', '')} · {item.get('title', item.get('series_id', ''))} · "
        f"{item.get('series_id', '')} · {item.get('frequency', '')}"
    ).strip(" ·")


def _authority_figure(audit_table: pd.DataFrame, ui_text: UiText) -> go.Figure:
    summary = (
        audit_table.groupby(["Source", "SourceType"], as_index=False)
        .agg(SeriesCount=("SeriesID", "count"), AuthorityScore=("AuthorityScore", "mean"))
        .sort_values(["AuthorityScore", "SeriesCount"], ascending=[True, True])
    )
    figure = go.Figure(
        go.Bar(
            x=summary["SeriesCount"],
            y=summary["Source"],
            orientation="h",
            marker=dict(
                color=summary["AuthorityScore"],
                colorscale=[[0, "#77808A"], [1, "#A98BE8"]],
                cmin=2,
                cmax=5,
                colorbar=dict(title=ui_text("Authority", "权威性")),
            ),
            customdata=summary[["SourceType", "AuthorityScore"]].to_numpy(),
            hovertemplate=(
                "%{y}<br>"
                + ui_text("Registered series", "注册序列")
                + ": %{x}<br>"
                + ui_text("Authority score", "权威评分")
                + ": %{customdata[1]:.1f}<extra></extra>"
            ),
        )
    )
    figure.update_layout(
        title=dict(text=ui_text("Current source mix", "当前数据来源结构"), x=0),
        height=max(360, 44 * len(summary)),
        margin=dict(l=12, r=12, t=64, b=12),
        xaxis_title=ui_text("Registered source entries", "已注册来源数量"),
        yaxis_title=None,
    )
    return figure


def _preview_selected_entry(entry: dict[str, Any], months: int) -> tuple[pd.DataFrame, dict[str, Any]]:
    from src.variable_pool import _fetch_registry_variable

    end = pd.Timestamp.today().normalize()
    start = (end - pd.DateOffset(months=int(months))).normalize()
    return _fetch_registry_variable(
        entry,
        start_date=start.strftime("%Y-%m-%d"),
        end_date=end.strftime("%Y-%m-%d"),
        force_refresh=True,
    )


def _preview_figure(data: pd.DataFrame, variable: str, frequency: str, ui_text: UiText) -> go.Figure:
    view = aggregate_time_series(data, frequency, metadata={variable: {"description": variable}})
    figure = go.Figure(
        go.Scatter(
            x=view["Date"],
            y=view[variable],
            mode="lines+markers" if frequency == "monthly" else "lines",
            line=dict(color="#7658B5", width=2.3),
            marker=dict(size=5),
            name=variable,
            hovertemplate="%{x|%Y-%m-%d}<br>%{y:,.4f}<extra></extra>",
        )
    )
    figure.update_layout(
        title=dict(text=ui_text(f"{variable} data preview", f"{variable} 数据预览"), x=0),
        height=470,
        margin=dict(l=12, r=12, t=64, b=12),
        hovermode="x unified",
        dragmode="pan",
        yaxis_title=variable,
    )
    figure.update_xaxes(rangeslider=dict(visible=True, thickness=0.09, bgcolor="#F1F3F8"))
    return figure


def render_data_library(ui_text: UiText, apply_theme: ThemeFunction) -> None:
    """Render searchable official catalogs, preview, and duplicate/source audit."""
    st.markdown(
        f'<p class="section-kicker">{ui_text("DATA CENTER", "数据中心")}</p>',
        unsafe_allow_html=True,
    )
    st.markdown(
        f"""
        <section class="data-library-intro">
          <div>
            <span>{ui_text("SEARCH, CHECK, USE", "先搜索，再核对")}</span>
            <h2>{ui_text("Find the data you need", "需要什么数据，直接搜")}</h2>
            <p>{ui_text("Search official FRED and EIA catalogs by variable, code or economic concept. Preview a series before adding it to the analysis pool.", "按变量名称、代码或经济含义搜索 FRED 与 EIA 官方目录；先预览数据，再决定是否加入分析。")}</p>
          </div>
        </section>
        """,
        unsafe_allow_html=True,
    )

    search_tab, preview_tab, audit_tab = st.tabs([
        ui_text("Search official catalogs", "搜索官方目录"),
        ui_text("Selected data preview", "数据预览"),
        ui_text("Source audit", "来源核对"),
    ])
    state_key = "quick_api_catalog_registry_entries"
    item_state_key = "data_library_selected_items"
    entries = list(st.session_state.get(state_key, []))
    selected_items = dict(st.session_state.get(item_state_key, {}))

    with search_tab:
        source_col, query_col = st.columns([0.85, 2.15])
        sources = source_col.multiselect(
            ui_text("Catalogs", "数据目录"),
            ["FRED", "EIA"],
            default=["FRED", "EIA"],
            key="data_library_sources",
        )
        query = query_col.text_input(
            ui_text("Variable, code or economic concept", "变量名称、代码或经济概念"),
            placeholder=ui_text("Crude inventory, inflation expectations, DGS10…", "例如：原油库存、通胀预期、DGS10…"),
            key="data_library_query",
        )
        fixed_routes = list(EIA_DATASET_ROUTES)
        discovered = list(st.session_state.get("data_library_discovered_eia_routes", []))
        route_options = list(dict.fromkeys([*fixed_routes, *[item["route"] for item in discovered]]))
        route_col, discover_col = st.columns([2.15, 0.85])
        eia_routes = route_col.multiselect(
            ui_text("EIA datasets to search", "要搜索的EIA数据集"),
            route_options,
            default=[route for route in ("petroleum/pri/fut", "petroleum/stoc/wstk") if route in route_options],
            disabled="EIA" not in sources,
            key="data_library_eia_routes",
        )
        with discover_col:
            st.write("")
            if st.button(
                ui_text("Discover EIA datasets", "发现EIA数据集"),
                disabled="EIA" not in sources or not query.strip(),
                use_container_width=True,
                key="discover_eia_routes",
            ):
                try:
                    with st.spinner(ui_text("Traversing the official EIA route tree…", "正在遍历EIA官方数据树……")):
                        discovered = search_eia_datasets(query)
                    st.session_state["data_library_discovered_eia_routes"] = discovered
                    if discovered:
                        st.success(ui_text(
                            f"Found {len(discovered)} matching EIA datasets. Rerun the selector to choose them.",
                            f"发现{len(discovered)}个匹配的EIA数据集，可在上方选择后搜索具体序列。",
                        ))
                    else:
                        st.info(ui_text("No matching EIA leaf datasets were found.", "未发现匹配的EIA叶级数据集。"))
                except Exception as exc:  # noqa: BLE001
                    st.error(str(exc))
        if discovered:
            st.dataframe(pd.DataFrame(discovered), use_container_width=True, hide_index=True)

        if st.button(
            ui_text("Search selected official catalogs", "搜索所选官方数据目录"),
            type="primary",
            use_container_width=True,
            disabled=not query.strip() or not sources,
            key="data_library_search",
        ):
            try:
                with st.spinner(ui_text("Searching provider metadata…", "正在搜索数据目录元数据……")):
                    results = search_official_catalogs(
                        query,
                        include_fred="FRED" in sources,
                        eia_routes=eia_routes if "EIA" in sources else [],
                        limit_per_source=35,
                    )
                st.session_state["data_library_search_results"] = results
            except Exception as exc:  # noqa: BLE001
                st.error(str(exc))

        results = list(st.session_state.get("data_library_search_results", []))
        if results:
            result_table = pd.DataFrame(results)
            visible_columns = [
                column for column in ["source", "series_id", "title", "frequency", "units", "start", "end", "route", "economic_category"]
                if column in result_table.columns
            ]
            st.dataframe(result_table[visible_columns], use_container_width=True, hide_index=True, height=360)
            selected_index = st.selectbox(
                ui_text("Series to add", "要加入的序列"),
                range(len(results)),
                format_func=lambda index: _search_result_label(results[index]),
                key="data_library_result_selection",
            )
            selected_item = results[int(selected_index)]
            if st.button(
                ui_text("Add to analysis pool", "加入分析变量池"),
                type="primary",
                use_container_width=True,
                key="data_library_add",
            ):
                entry = catalog_item_to_registry_entry(selected_item)
                entries = [item for item in entries if item.get("name") != entry["name"]]
                entries.append(entry)
                selected_items[entry["name"]] = selected_item
                st.session_state[state_key] = entries
                st.session_state[item_state_key] = selected_items
                st.success(ui_text(
                    f"{entry['display_name']} is now available in the quick-analysis variable pool.",
                    f"{entry['display_name']}已加入快速分析变量池。",
                ))
        elif query.strip():
            st.info(ui_text("Run a catalog search to see matching series.", "请执行目录搜索以查看匹配序列。"))

    with preview_tab:
        entries = list(st.session_state.get(state_key, []))
        if not entries:
            st.info(ui_text("Add a FRED or EIA series from the search tab first.", "请先在搜索页加入一个FRED或EIA序列。"))
        else:
            control_a, control_b, control_c, control_d = st.columns([1.6, 0.8, 0.8, 1.0])
            variable = control_a.selectbox(
                ui_text("Selected series", "已选序列"),
                [entry["name"] for entry in entries],
                format_func=lambda name: next((entry.get("display_name", name) for entry in entries if entry["name"] == name), name),
                key="data_library_preview_variable",
            )
            months = control_b.selectbox(ui_text("History", "历史长度"), [12, 36, 60, 120], index=2, key="data_library_preview_months")
            frequency = control_c.radio(
                ui_text("Frequency", "频率"),
                ["daily", "monthly"],
                format_func=lambda value: ui_text("Daily", "日度") if value == "daily" else ui_text("Monthly", "月度"),
                horizontal=True,
                key="data_library_preview_frequency",
            )
            with control_d:
                st.write("")
                load_preview = st.button(ui_text("Refresh preview", "更新预览"), type="primary", use_container_width=True, key="data_library_preview_run")
            entry = next(item for item in entries if item["name"] == variable)
            if load_preview:
                try:
                    with st.spinner(ui_text("Downloading the selected official series…", "正在下载所选官方序列……")):
                        data, status = _preview_selected_entry(entry, int(months))
                    st.session_state["data_library_preview"] = {"variable": variable, "data": data, "status": status}
                except Exception as exc:  # noqa: BLE001
                    st.error(str(exc))
            preview = st.session_state.get("data_library_preview")
            if isinstance(preview, dict) and preview.get("variable") == variable:
                data = preview.get("data")
                status = preview.get("status", {})
                if isinstance(data, pd.DataFrame) and variable in data and data[variable].notna().any():
                    status_columns = st.columns(3)
                    status_columns[0].metric(ui_text("Actual source", "实际来源"), str(status.get("ActualSource", "")))
                    status_columns[1].metric(ui_text("Observations", "观测数"), f"{int(data[variable].notna().sum()):,}")
                    status_columns[2].metric(ui_text("Latest date", "最新日期"), pd.to_datetime(data["Date"]).max().strftime("%Y-%m-%d"))
                    figure = _preview_figure(data, variable, frequency, ui_text)
                    apply_theme(figure)
                    st.plotly_chart(figure, use_container_width=True, config=PLOT_CONFIG, key=f"data_preview_{variable}_{frequency}")
                    st.download_button(
                        ui_text("Download preview CSV", "下载预览CSV"),
                        data=data.to_csv(index=False).encode("utf-8-sig"),
                        file_name=f"{variable}.csv",
                        mime="text/csv",
                        use_container_width=True,
                        key="download_data_preview",
                    )
                else:
                    st.warning(ui_text("The selected source returned no usable values.", "所选来源没有返回可用数值。"))

    with audit_tab:
        registry = load_variable_registry(extra_entries=entries)
        audit = audit_registry_sources(registry)
        metrics = st.columns(4)
        metrics[0].metric(ui_text("Registered variables", "已注册变量"), audit.variable_count)
        metrics[1].metric(ui_text("Source entries", "来源条目"), len(audit.table))
        metrics[2].metric(ui_text("Exact duplicates", "硬重复"), audit.exact_duplicate_count)
        metrics[3].metric(ui_text("Proxy fallbacks", "代理回退"), audit.proxy_fallback_count)
        st.caption(ui_text(
            "Exact duplicates may be removed. Proxy fallbacks are retained for continuity but are explicitly labelled because they can change the instrument definition.",
            "硬重复可以删除；代理回退为保证连续性而保留，但因其可能改变工具定义，必须明确标记。",
        ))
        if not audit.table.empty:
            figure = _authority_figure(audit.table, ui_text)
            apply_theme(figure)
            st.plotly_chart(figure, use_container_width=True, config=PLOT_CONFIG, key="data_source_authority")
            st.dataframe(audit.table, use_container_width=True, hide_index=True, height=420)
            st.download_button(
                ui_text("Download source audit", "下载来源审计"),
                data=audit.table.to_csv(index=False).encode("utf-8-sig"),
                file_name="data_source_audit.csv",
                mime="text/csv",
                use_container_width=True,
                key="download_source_audit",
            )
