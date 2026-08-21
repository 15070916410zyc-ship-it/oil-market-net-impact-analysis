"""One-search official-data workspace with persistent variable registration."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from io import BytesIO
from typing import Any, Callable

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.api_variable_catalog import (
    EIA_DATASET_ROUTES,
    catalog_item_to_registry_entry,
    deduplicate_catalog_results,
    search_eia_datasets,
    search_eia_series,
    search_fred_series,
)
from src.data_governance import aggregate_time_series, audit_registry_sources
from src.research_store import ResearchStore
from src.variable_pool import load_variable_registry


UiText = Callable[[str, str], str]
ThemeFunction = Callable[[Any], Any]
PLOT_CONFIG = {
    "scrollZoom": True,
    "displaylogo": False,
    "responsive": True,
    "toImageButtonOptions": {"format": "png", "scale": 2},
}


def _database_url() -> str:
    try:
        return str(st.secrets.get("DATABASE_URL", "") or "").strip()
    except Exception:  # pragma: no cover - no local secrets file is normal.
        return ""


def _store() -> ResearchStore:
    return ResearchStore(database_url=_database_url() or None)


def _search_result_label(item: dict[str, Any]) -> str:
    parts = [
        str(item.get("source", "")),
        str(item.get("title", item.get("series_id", ""))),
        str(item.get("series_id", "")),
        str(item.get("frequency", "")),
    ]
    return "  |  ".join(part for part in parts if part)


def _catalog_query(query: str) -> str:
    """Translate common Chinese research terms into official-catalog keywords."""
    normalized = str(query or "").strip()
    replacements = {
        "美国原油库存": "US crude oil stocks",
        "美国通胀预期": "US inflation expectations",
        "原油库存": "crude oil stocks",
        "石油库存": "petroleum stocks",
        "炼厂开工率": "refinery utilization",
        "原油价格": "crude oil price",
        "汽油价格": "gasoline price",
        "天然气库存": "natural gas storage",
        "天然气价格": "natural gas price",
        "通胀预期": "inflation expectations",
        "美元指数": "broad dollar index",
        "利率": "interest rate",
        "就业": "employment",
    }
    for chinese, official_keyword in replacements.items():
        if chinese in normalized:
            return normalized.replace(chinese, official_keyword)
    return normalized


def _indexed_catalog_results(query: str, limit: int = 30) -> list[dict[str, Any]]:
    """Return fast matches from the synced index of connected official series."""
    keywords = [token for token in _catalog_query(query).lower().replace("-", " ").split() if token]
    if not keywords:
        return []
    matches: list[tuple[int, dict[str, Any]]] = []
    for entry in load_variable_registry():
        sources = list(entry.get("sources") or [])
        official = next(
            (
                source
                for source in sources
                if str(source.get("type", "")).lower() in {"fred", "eia_v2", "eia_excel"}
            ),
            None,
        )
        if not official:
            continue
        searchable = " ".join(
            [
                str(entry.get("name", "")),
                str(entry.get("display_name", "")),
                str(entry.get("description", "")),
                str(entry.get("note", "")),
                str(official.get("id", "")),
            ]
        ).lower().replace("-", " ")
        score = sum(token in searchable for token in keywords)
        if score == 0:
            continue
        source_type = str(official.get("type", "")).lower()
        source_name = "FRED" if source_type == "fred" else "EIA"
        series_id = str(official.get("id") or entry.get("name") or "")
        matches.append(
            (
                score,
                {
                    "source": source_name,
                    "series_id": series_id,
                    "title": str(entry.get("display_name") or entry.get("description") or entry.get("name")),
                    "frequency": str(entry.get("frequency") or ""),
                    "economic_category": str(entry.get("economic_category") or "other_indicators"),
                    "registry_entry": entry,
                },
            )
        )
    matches.sort(key=lambda pair: (-pair[0], str(pair[1].get("title", ""))))
    return [item for _, item in matches[: max(1, int(limit))]]


@st.cache_data(ttl=6 * 60 * 60, show_spinner=False)
def _search_everywhere(query: str, limit: int = 30) -> tuple[list[dict[str, Any]], list[str]]:
    """Search every configured official catalog while preserving partial results."""
    indexed = _indexed_catalog_results(query, limit=limit)
    if indexed:
        return indexed, []
    catalog_query = _catalog_query(query)
    results: list[dict[str, Any]] = []
    errors: list[str] = []
    try:
        results.extend(search_fred_series(catalog_query, limit=limit))
    except Exception as exc:  # noqa: BLE001 - EIA can still return matches.
        errors.append(f"FRED: {exc}")

    # EIA routes are independent official catalogs. Search them concurrently so
    # "all sources" does not turn into a long serial wait on the first query.
    routes = list(EIA_DATASET_ROUTES)
    with ThreadPoolExecutor(max_workers=min(8, len(routes) + 1)) as pool:
        discovery_future = pool.submit(search_eia_datasets, catalog_query, max_nodes=36, limit=6)
        route_futures = {
            pool.submit(search_eia_series, catalog_query, route, limit=limit): route
            for route in routes
        }
        for future in as_completed([discovery_future, *route_futures]):
            if future is discovery_future:
                try:
                    discovered = future.result()
                    routes.extend(str(item.get("route", "")) for item in discovered)
                except Exception as exc:  # noqa: BLE001 - fixed routes remain available.
                    errors.append(f"EIA目录发现: {exc}")
                continue
            route = route_futures[future]
            try:
                results.extend(future.result())
            except Exception as exc:  # noqa: BLE001 - one branch must not fail all search.
                errors.append(f"EIA {route}: {exc}")

    fixed_routes = set(EIA_DATASET_ROUTES)
    discovered_routes = list(dict.fromkeys(route for route in routes if route and route not in fixed_routes))
    if discovered_routes:
        with ThreadPoolExecutor(max_workers=min(6, len(discovered_routes))) as pool:
            route_futures = {
                pool.submit(search_eia_series, catalog_query, route, limit=limit): route
                for route in discovered_routes
            }
            for future in as_completed(route_futures):
                route = route_futures[future]
                try:
                    results.extend(future.result())
                except Exception as exc:  # noqa: BLE001 - one branch must not fail all search.
                    errors.append(f"EIA {route}: {exc}")
    return deduplicate_catalog_results(results), errors


def _preview_selected_entry(
    entry: dict[str, Any],
    *,
    start_date: pd.Timestamp,
    end_date: pd.Timestamp,
    force_refresh: bool,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    from src.variable_pool import _fetch_registry_variable

    return _fetch_registry_variable(
        entry,
        start_date=start_date.strftime("%Y-%m-%d"),
        end_date=end_date.strftime("%Y-%m-%d"),
        force_refresh=force_refresh,
    )


def _preview_figure(
    data: pd.DataFrame,
    variable: str,
    title: str,
    frequency: str,
    ui_text: UiText,
) -> go.Figure:
    view = aggregate_time_series(data, frequency, metadata={variable: {"description": title}})
    figure = go.Figure(
        go.Scatter(
            x=view["Date"],
            y=view[variable],
            mode="lines+markers" if frequency == "monthly" else "lines",
            line=dict(color="#356B65", width=2.7),
            marker=dict(size=5, color="#356B65"),
            fill="tozeroy",
            fillcolor="rgba(53,107,101,0.08)",
            name=title,
            hovertemplate="%{x|%Y-%m-%d}<br>%{y:,.4f}<extra></extra>",
        )
    )
    figure.update_layout(
        title=dict(text=title, x=0),
        height=560,
        margin=dict(l=18, r=18, t=72, b=18),
        hovermode="x unified",
        dragmode="pan",
        yaxis_title=None,
        uirevision=f"data-{variable}-{frequency}",
    )
    figure.update_xaxes(
        rangeslider=dict(visible=True, thickness=0.08, bgcolor="#EEF0EC"),
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


def _excel_bytes(data: pd.DataFrame, variable: str) -> bytes:
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        data.to_excel(writer, index=False, sheet_name=variable[:31] or "data")
    return buffer.getvalue()


def _stored_registry_entries(store: ResearchStore) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for item in store.list_variables():
        metadata = item.get("metadata")
        if isinstance(metadata, dict) and metadata.get("name"):
            entries.append(metadata)
    return entries


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
                colorscale=[[0, "#A9AEAA"], [1, "#356B65"]],
                cmin=2,
                cmax=5,
                colorbar=dict(title=ui_text("Authority", "权威性")),
            ),
            customdata=summary[["SourceType", "AuthorityScore"]].to_numpy(),
            hovertemplate="%{y}<br>%{x} series<br>%{customdata[1]:.1f}<extra></extra>",
        )
    )
    figure.update_layout(
        title=dict(text=ui_text("Source coverage and authority", "来源覆盖与权威性"), x=0),
        height=max(360, 44 * len(summary)),
        margin=dict(l=12, r=12, t=64, b=12),
        xaxis_title=ui_text("Registered source entries", "已注册来源数量"),
        yaxis_title=None,
    )
    return figure


def render_data_library(ui_text: UiText, apply_theme: ThemeFunction) -> None:
    """Render search, immediate charting, Excel download, and persistent add."""
    store = _store()
    status = store.status
    st.markdown(
        f"""
        <section class="data-library-intro view-reveal">
          <div>
            <span>{ui_text("OFFICIAL DATA SEARCH", "官方数据搜索")}</span>
            <h2>{ui_text("Type what you need. See the data first.", "输入想找的数据，先看走势")}</h2>
            <p>{ui_text("Every connected FRED and EIA source is included automatically. The synced index responds first; unfamiliar terms expand into the official catalogs. Inspect the line, choose a range, then download or add it.", "FRED 与 EIA 的已连接来源会自动纳入。系统先从同步索引即时匹配，陌生变量再扩展到官方目录；看过走势后即可选择时间、下载或加入变量库。")}</p>
          </div>
        </section>
        """,
        unsafe_allow_html=True,
    )
    st.caption(
        ui_text("Storage: ", "变量库：")
        + status.backend
        + "  |  "
        + (ui_text("shared", "共享") if status.shared else ui_text("local fallback", "本地后备"))
    )

    latest_payload = st.session_state.get("price_forecast_last_result")
    if isinstance(latest_payload, dict) and latest_payload.get("result") is not None:
        latest_result = latest_payload["result"]
        history = latest_result.history.copy()
        target_name = str(latest_payload.get("target") or latest_result.metrics.get("Target") or "Oil")
        context = go.Figure(
            go.Scatter(
                x=history["Date"],
                y=history["Actual"],
                mode="lines",
                line=dict(color="#356B65", width=2.7),
                fill="tozeroy",
                fillcolor="rgba(53,107,101,0.08)",
                name=target_name,
                hovertemplate="%{x|%Y-%m-%d}<br>$%{y:,.2f}<extra></extra>",
            )
        )
        context.update_layout(
            title=dict(text=ui_text(f"Latest {target_name} data", f"最新 {target_name} 数据"), x=0),
            height=460,
            margin=dict(l=18, r=18, t=72, b=18),
            hovermode="x unified",
        )
        apply_theme(context)
        st.plotly_chart(context, use_container_width=True, config=PLOT_CONFIG, key="data_library_default_context")

    search_col, action_col = st.columns([4.5, 1.0])
    query = search_col.text_input(
        ui_text("Search all connected databases", "搜索全部已连接数据库"),
        placeholder=ui_text(
            "e.g. crude inventories, refinery utilization, inflation expectations…",
            "例如：原油库存、炼厂开工率、通胀预期…",
        ),
        key="data_library_query",
    )
    with action_col:
        st.write("")
        search = st.button(
            ui_text("Search", "搜索数据"),
            type="primary",
            use_container_width=True,
            disabled=not query.strip(),
            key="data_library_search",
        )
    if search:
        with st.status(ui_text("Searching official catalogs…", "正在搜索全部官方目录…"), expanded=False) as progress:
            results, errors = _search_everywhere(query.strip())
            st.session_state["data_library_search_results"] = results
            st.session_state["data_library_search_errors"] = errors
            progress.update(
                label=ui_text(f"Found {len(results)} series", f"找到 {len(results)} 个序列"),
                state="complete" if results else "error",
            )

    results = list(st.session_state.get("data_library_search_results", []))
    if not results:
        st.markdown(
            f"""
            <div class="data-empty-state view-reveal">
              <strong>{ui_text("All sources are ready", "数据源已经准备好")}</strong>
              <span>{ui_text("Search a variable above. The first matching series will be charted automatically.", "在上方输入变量，系统会自动绘制第一个匹配序列。")}</span>
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        selected_index = st.selectbox(
            ui_text("Matching series", "匹配的数据序列"),
            range(len(results)),
            format_func=lambda index: _search_result_label(results[index]),
            key="data_library_result_selection",
        )
        selected_item = results[int(selected_index)]
        entry = dict(selected_item.get("registry_entry") or catalog_item_to_registry_entry(selected_item))
        preview_signature = f"{selected_item.get('source')}|{selected_item.get('route')}|{selected_item.get('series_id')}"
        preview = st.session_state.get("data_library_preview")
        if not isinstance(preview, dict) or preview.get("signature") != preview_signature:
            try:
                with st.spinner(ui_text("Loading the latest observations…", "正在读取最新观测值…")):
                    end = pd.Timestamp.today().normalize()
                    start = end - pd.DateOffset(years=10)
                    data, source_status = _preview_selected_entry(
                        entry,
                        start_date=start,
                        end_date=end,
                        force_refresh=False,
                    )
                preview = {
                    "signature": preview_signature,
                    "data": data,
                    "status": source_status,
                    "entry": entry,
                    "item": selected_item,
                }
                st.session_state["data_library_preview"] = preview
            except Exception as exc:  # noqa: BLE001
                preview = None
                st.error(ui_text("The selected series could not be loaded: ", "所选序列暂时无法读取：") + str(exc))

        if isinstance(preview, dict):
            data = preview.get("data")
            if isinstance(data, pd.DataFrame) and not data.empty and entry["name"] in data:
                earliest = pd.to_datetime(data["Date"]).min().date()
                latest = pd.to_datetime(data["Date"]).max().date()
                controls = st.columns([1.35, 1.35, 0.85, 1.0])
                start_date = controls[0].date_input(
                    ui_text("Start date", "开始时间"),
                    value=max(earliest, (pd.Timestamp(latest) - pd.DateOffset(years=5)).date()),
                    min_value=earliest,
                    max_value=latest,
                    key=f"data_start_{preview_signature}",
                )
                end_date = controls[1].date_input(
                    ui_text("End date", "结束时间"),
                    value=latest,
                    min_value=earliest,
                    max_value=latest,
                    key=f"data_end_{preview_signature}",
                )
                frequency = controls[2].radio(
                    ui_text("Frequency", "频率"),
                    ["daily", "monthly"],
                    format_func=lambda value: ui_text("Daily", "日度") if value == "daily" else ui_text("Monthly", "月度"),
                    horizontal=True,
                    key=f"data_frequency_{preview_signature}",
                )
                filtered = data[
                    (pd.to_datetime(data["Date"]).dt.date >= start_date)
                    & (pd.to_datetime(data["Date"]).dt.date <= end_date)
                ].copy()
                metrics = st.columns(3)
                metrics[0].metric(ui_text("Latest date", "最新日期"), latest.isoformat())
                metrics[1].metric(ui_text("Observations", "观测数"), f"{filtered[entry['name']].notna().sum():,}")
                metrics[2].metric(ui_text("Source", "数据来源"), str(selected_item.get("source", "")))
                figure = _preview_figure(
                    filtered,
                    entry["name"],
                    str(selected_item.get("title") or entry["display_name"]),
                    frequency,
                    ui_text,
                )
                apply_theme(figure)
                st.plotly_chart(
                    figure,
                    use_container_width=True,
                    config=PLOT_CONFIG,
                    key=f"data_preview_{preview_signature}_{frequency}",
                )
                with controls[3]:
                    st.write("")
                    if st.button(
                        ui_text("Add to database", "加入变量库"),
                        type="primary",
                        use_container_width=True,
                        key=f"data_add_{preview_signature}",
                    ):
                        try:
                            stored = store.upsert_variable(entry)
                            count = store.upsert_observations(stored["id"], data, entry["name"])
                            current_entries = list(st.session_state.get("quick_api_catalog_registry_entries", []))
                            current_entries = [item for item in current_entries if item.get("name") != entry["name"]]
                            current_entries.append(entry)
                            st.session_state["quick_api_catalog_registry_entries"] = current_entries
                            st.success(ui_text(
                                f"Added to the research library with {count:,} observations.",
                                f"已加入研究变量库，共保存 {count:,} 条观测。",
                            ))
                        except Exception as exc:  # noqa: BLE001
                            st.error(ui_text("Could not add this series: ", "未能加入变量库：") + str(exc))
                st.download_button(
                    ui_text("Download selected range as Excel", "下载所选时间范围 Excel"),
                    data=_excel_bytes(filtered, entry["name"]),
                    file_name=f"{entry['name']}_{start_date}_{end_date}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True,
                    key=f"download_data_excel_{preview_signature}",
                )
            else:
                st.warning(ui_text("This series returned no usable values.", "该序列没有返回可用数据。"))

    try:
        stored_entries = _stored_registry_entries(store)
    except Exception as exc:  # noqa: BLE001
        stored_entries = []
        st.warning(ui_text("The shared variable library is temporarily unavailable: ", "共享变量库暂时不可用：") + str(exc))
    session_entries = list(st.session_state.get("quick_api_catalog_registry_entries", []))
    available_entries = {
        entry["name"]: entry
        for entry in [*stored_entries, *session_entries]
        if isinstance(entry, dict) and entry.get("name")
    }
    if available_entries:
        st.markdown(ui_text("### Variables available for analysis", "### 已加入、可用于分析的数据"))
        selected_names = st.multiselect(
            ui_text("Use these added variables", "选择要用于分析的已添加数据"),
            options=list(available_entries),
            default=list(available_entries),
            format_func=lambda name: str(available_entries[name].get("display_name") or name),
            key="data_library_active_variables",
        )
        st.session_state["quick_api_catalog_registry_entries"] = [available_entries[name] for name in selected_names]

    with st.expander(ui_text("Professional source audit", "专业模式：数据来源核对"), expanded=False):
        registry = load_variable_registry(extra_entries=list(available_entries.values()))
        audit = audit_registry_sources(registry)
        metrics = st.columns(4)
        metrics[0].metric(ui_text("Registered variables", "已注册变量"), audit.variable_count)
        metrics[1].metric(ui_text("Source entries", "来源条目"), len(audit.table))
        metrics[2].metric(ui_text("Exact duplicates", "硬重复"), audit.exact_duplicate_count)
        metrics[3].metric(ui_text("Proxy fallbacks", "代理回退"), audit.proxy_fallback_count)
        st.caption(ui_text(
            "Exact duplicates can be removed. Labelled fallback sources remain available only when the primary source fails.",
            "硬重复可以删除；已标记的备用来源只在主来源失败时启用。",
        ))
        if not audit.table.empty:
            authority = _authority_figure(audit.table, ui_text)
            apply_theme(authority)
            st.plotly_chart(authority, use_container_width=True, config=PLOT_CONFIG, key="data_source_authority")
            st.dataframe(audit.table, use_container_width=True, hide_index=True, height=420)
