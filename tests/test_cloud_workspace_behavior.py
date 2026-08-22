"""Cloud-safety and result-export tests for the Streamlit application."""

from __future__ import annotations

from contextlib import nullcontext
from io import BytesIO
import hashlib
import os
from pathlib import Path
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from zipfile import ZipFile

import pandas as pd


class CloudWorkspaceBehaviorTests(unittest.TestCase):
    def test_chinese_catalog_queries_use_official_english_keywords(self) -> None:
        from app.data_library import _catalog_query, _indexed_catalog_results

        self.assertEqual(_catalog_query("原油库存"), "crude oil stocks")
        self.assertEqual(_catalog_query("美国通胀预期"), "US inflation expectations")
        self.assertEqual(_catalog_query("WTI"), "WTI")
        indexed = _indexed_catalog_results("原油库存")
        self.assertTrue(indexed)
        self.assertEqual(indexed[0]["source"], "EIA")
        self.assertIn("registry_entry", indexed[0])

        treasury_matches = _indexed_catalog_results("美国10年期国债收益率")
        self.assertTrue(treasury_matches)
        self.assertEqual(treasury_matches[0]["registry_entry"]["name"], "TNote10Y")

    def test_market_download_workers_run_independent_series_concurrently(self) -> None:
        from src import data_fetcher

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            barrier = threading.Barrier(2, timeout=2)
            thread_ids: set[int] = set()

            def fake_fetch(
                name: str,
                sources: list[dict[str, str]],
                start_date: str,
                end_date: str,
                cache_file: str | Path,
                force_refresh: bool = False,
            ):
                thread_ids.add(threading.get_ident())
                barrier.wait()
                data_fetcher.LAST_SOURCE_USED[name] = f"test:{name}"
                return pd.DataFrame(
                    {"Date": pd.to_datetime([end_date]), name: [1.0]}
                )

            gprd = pd.DataFrame(
                {"Date": pd.to_datetime(["2024-01-02"]), "GPRD": [1.0]}
            )
            sources = {"WTI": [{"type": "test", "id": "WTI"}], "Brent": [{"type": "test", "id": "Brent"}]}
            caches = {name: temp_path / f"{name}.csv" for name in sources}

            with (
                patch.object(data_fetcher, "SERIES_SOURCES", sources),
                patch.object(data_fetcher, "RAW_CACHE_FILES", caches),
                patch.object(data_fetcher, "PROCESSED_MARKET_DATA_PATH", temp_path / "market.xlsx"),
                patch.object(data_fetcher, "DATA_SOURCE_LOG_PATH", temp_path / "sources.xlsx"),
                patch.object(data_fetcher, "fetch_series_with_fallback", side_effect=fake_fetch),
                patch.object(data_fetcher, "fetch_gprd_auto", return_value=gprd),
            ):
                result = data_fetcher.build_market_dataset(
                    "2024-01-02",
                    "2024-01-02",
                    download_workers=2,
                )

            self.assertEqual(len(thread_ids), 2)
            self.assertEqual(result.loc[0, "WTI"], 1.0)
            self.assertEqual(result.loc[0, "Brent"], 1.0)

    def test_market_cache_first_uses_fresh_gprd_without_network_download(self) -> None:
        from src import data_fetcher

        dates = pd.to_datetime(["2024-01-02", "2024-01-03"])
        market_series = {
            name: pd.DataFrame({"Date": dates, name: [1.0, 2.0]})
            for name in data_fetcher.SERIES_SOURCES
        }
        gprd = pd.DataFrame({"Date": dates, "GPRD": [3.0, 4.0]})

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            with (
                patch.object(data_fetcher, "PROCESSED_MARKET_DATA_PATH", temp_path / "market.xlsx"),
                patch.object(data_fetcher, "DATA_SOURCE_LOG_PATH", temp_path / "sources.xlsx"),
                patch.object(data_fetcher, "_load_cache_file", side_effect=lambda path, name, start, end: market_series[name]),
                patch.object(data_fetcher, "_load_gprd_cache", return_value=gprd),
                patch.object(data_fetcher, "fetch_gprd_auto") as online_gprd,
            ):
                result = data_fetcher.build_market_dataset(
                    "2024-01-02",
                    "2024-01-03",
                    cache_first=True,
                )

            online_gprd.assert_not_called()
            self.assertEqual(result["GPRD"].tolist(), [3.0, 4.0])
            self.assertEqual(
                data_fetcher.LAST_SOURCE_USED["GPRD"],
                "cache:gprd_auto_download",
            )

    def test_cloud_refresh_reuses_valid_cache_without_disabling_stale_refresh(self) -> None:
        import inspect

        from app import streamlit_app as app

        with patch.object(app, "is_cloud_runtime", return_value=True):
            self.assertEqual(
                app.market_refresh_strategy(),
                {"cache_first": True, "force_refresh": False, "download_workers": 4},
            )
        with patch.object(app, "is_cloud_runtime", return_value=False):
            self.assertEqual(
                app.market_refresh_strategy(),
                {"cache_first": False, "force_refresh": True, "download_workers": 1},
            )

        setup_source = inspect.getsource(app.run_paper_replication_setup_workflow)
        update_source = inspect.getsource(app.run_update_market_data)
        self.assertIn('cache_first=refresh_strategy["cache_first"]', setup_source)
        self.assertIn('force_refresh=refresh_strategy["force_refresh"]', setup_source)
        self.assertIn('download_workers=refresh_strategy["download_workers"]', setup_source)
        self.assertIn('cache_first=refresh_strategy["cache_first"]', update_source)

    def test_crisis_warning_keeps_original_model_and_runs_regime_forecast_separately(self) -> None:
        import inspect

        from app import streamlit_app as app

        renderer = inspect.getsource(app.render_crisis_warning_tab)
        original_model = inspect.getsource(__import__("src.crisis_warning", fromlist=["run_five_day_warning"]))

        self.assertIn("run_five_day_warning(warning_data", renderer)
        self.assertIn("run_markov_crisis_forecast(", renderer)
        self.assertIn("regime_forecast = None", renderer)
        self.assertNotIn("MarkovRegression", original_model)
        self.assertNotIn("fetch_google_trends_timeline", original_model)

    def test_crisis_probability_chart_uses_original_date_timeline(self) -> None:
        import inspect

        from app import streamlit_app as app

        renderer = inspect.getsource(app._render_warning_results)
        self.assertIn('x=regime_history["Date"]', renderer)
        self.assertIn("height=440", renderer)
        self.assertIn("st.plotly_chart(regime_figure", renderer)
        self.assertNotIn("hamilton_crisis_display_window", renderer)
        self.assertNotIn("overflow-x:auto", renderer)

    def test_analysis_results_are_inline_not_a_top_level_tab(self) -> None:
        from app import streamlit_app as app

        self.assertEqual(
            app.main_navigation_labels(),
            ["决策模式", "专业模式"],
        )
        with (
            patch.object(app.st, "markdown"),
            patch.object(app.st, "radio", return_value="professional"),
            patch.object(app.st, "divider") as divider,
            patch.object(
                app,
                "render_analysis_window_controls",
                return_value={"start_date": "2020-01-01", "analysis_mode": "professional"},
            ) as window_controls,
            patch.object(app, "render_professional_pipeline_tab") as professional,
            patch.object(app, "render_paper_replication_tab") as results,
        ):
            returned = app.render_run_pipeline_tab({"start_date": "2020-01-01"})

        window_controls.assert_called_once()
        professional.assert_called_once()
        divider.assert_called_once()
        results.assert_called_once()
        self.assertEqual(returned["analysis_mode"], "professional")

    def test_hero_workspace_links_change_workspace_once(self) -> None:
        from app import streamlit_app as app

        navigation = ["决策模式", "专业模式"]
        session_state: dict[str, str] = {}
        with (
            patch.object(app.st, "query_params", {"workspace": "professional", "request": "first"}),
            patch.object(app.st, "session_state", session_state),
        ):
            app.sync_primary_workspace_from_query(navigation)
            self.assertEqual(session_state["primary_workspace_mode"], "professional")
            self.assertEqual(session_state["professional_workspace_mode"], "net_impact")
            self.assertFalse(session_state["professional_results_expanded"])

            session_state["primary_workspace_mode"] = "decision"
            app.sync_primary_workspace_from_query(navigation)
            self.assertEqual(session_state["primary_workspace_mode"], "decision")

        with (
            patch.object(app.st, "query_params", {"workspace": "professional", "request": "second"}),
            patch.object(app.st, "session_state", session_state),
        ):
            app.sync_primary_workspace_from_query(navigation)
        self.assertEqual(session_state["primary_workspace_mode"], "professional")

    def test_hero_links_replace_the_duplicate_workspace_radio(self) -> None:
        import inspect

        from app import streamlit_app as app

        renderer = inspect.getsource(app.render_main_header)
        main_source = inspect.getsource(app.main)
        self.assertIn("/?workspace=decision&amp;request=", renderer)
        self.assertIn("/?workspace=professional&amp;request=", renderer)
        self.assertIn('target="_self"', renderer)
        self.assertIn("#market-workspaces", renderer)
        self.assertNotIn("workspace-mode-switch", renderer)
        self.assertIn("professional_active", renderer)
        self.assertNotIn('key="primary_workspace_mode"', main_source)

    def test_professional_workspace_opens_directly_on_net_impact(self) -> None:
        import inspect

        from app import streamlit_app as app

        main_source = inspect.getsource(app.main)
        self.assertNotIn('"overview": ui_text("Professional home", "专业首页")', main_source)
        self.assertIn("st.segmented_control", main_source)
        self.assertNotIn("render_professional_overview()", main_source)
        self.assertIn('active_workspace = active_workspace or "net_impact"', main_source)
        self.assertIn("render_professional_results_loader()", main_source)
        self.assertNotIn("st.radio(\n        ui_text(\"Professional workspace\"", main_source)

    def test_saved_professional_results_are_deferred_until_requested(self) -> None:
        from app import streamlit_app as app

        with tempfile.TemporaryDirectory() as directory:
            summary_path = Path(directory) / "summary.xlsx"
            summary_path.touch()
            net_impacts_path = Path(directory) / "net_impacts.xlsx"
            session_state: dict[str, object] = {}
            with (
                patch.dict(
                    app.PATHS,
                    {"paper_summary": summary_path, "paper_net_impacts": net_impacts_path},
                ),
                patch.object(app.st, "session_state", session_state),
                patch.object(app.st, "markdown"),
                patch.object(app.st, "button", return_value=False),
                patch.object(app, "render_paper_replication_tab") as render_results,
            ):
                app.render_professional_results_loader()
            render_results.assert_not_called()

            session_state["professional_results_expanded"] = True
            with (
                patch.dict(
                    app.PATHS,
                    {"paper_summary": summary_path, "paper_net_impacts": net_impacts_path},
                ),
                patch.object(app.st, "session_state", session_state),
                patch.object(app.st, "button", return_value=False),
                patch.object(app, "render_paper_replication_tab") as render_results,
            ):
                app.render_professional_results_loader()
            render_results.assert_called_once()

    def test_analysis_dates_are_rendered_inside_the_run_workspace(self) -> None:
        import inspect

        from app import streamlit_app as app

        defaults_source = inspect.getsource(app.default_analysis_options)
        window_source = inspect.getsource(app.render_analysis_window_controls)
        run_source = inspect.getsource(app.render_run_pipeline_tab)

        self.assertNotIn("st.sidebar", defaults_source)
        self.assertIn("Event start", window_source)
        self.assertIn("Estimation start", window_source)
        self.assertIn("render_analysis_window_controls", run_source)

    def test_price_forecast_ui_offers_multiple_prediction_intervals_and_named_chart(self) -> None:
        import inspect

        from app import streamlit_app as app

        renderer = inspect.getsource(app.render_oil_price_forecast_panel)

        self.assertIn("Prediction intervals to display", renderer)
        self.assertIn('re.fullmatch(r"Lower\\d+"', renderer)
        self.assertIn("forecast and prediction intervals", renderer)
        self.assertIn("customdata", renderer)
        self.assertIn("Forecast-end ranges", renderer)
        self.assertNotIn("Empirical 80% band", renderer)

    def test_price_forecast_chart_reserves_two_fifths_and_supports_navigation(self) -> None:
        import inspect

        import pandas as pd

        from app import streamlit_app as app

        history = pd.date_range("2025-01-01", periods=220, freq="B")
        forecast = pd.date_range(history[-1] + pd.offsets.BDay(), periods=20, freq="B")
        visible_start, visible_end = app._forecast_chart_default_range(history, forecast)
        forecast_share = (visible_end - history[-1]) / (visible_end - visible_start)

        self.assertGreaterEqual(float(forecast_share), 0.40)
        self.assertGreater(visible_start, history[0])
        renderer = inspect.getsource(app.render_oil_price_forecast_panel)
        self.assertIn('dragmode="pan"', renderer)
        self.assertIn("rangeslider=dict(", renderer)
        self.assertIn('"scrollZoom": True', renderer)
        self.assertIn("fixedrange=False", renderer)

    def test_price_forecast_display_connects_actual_and_forecast_traces(self) -> None:
        import pandas as pd

        from app import streamlit_app as app

        history = pd.DataFrame(
            {
                "Date": pd.to_datetime(["2026-08-13", "2026-08-14"]),
                "Actual": [91.0, 93.0],
            }
        )
        forecast = pd.DataFrame(
            {
                "Date": pd.to_datetime(["2026-08-17", "2026-08-18"]),
                "PointForecast": [92.0, 91.5],
                "Lower80": [88.0, 87.0],
                "Upper80": [96.0, 96.5],
            }
        )

        displayed = app._anchored_forecast_display(history, forecast)

        self.assertEqual(displayed.iloc[0]["Date"], history.iloc[-1]["Date"])
        self.assertEqual(displayed.iloc[0]["PointForecast"], 93.0)
        self.assertEqual(displayed.iloc[0]["Lower80"], 93.0)
        self.assertEqual(displayed.iloc[0]["Upper80"], 93.0)
        self.assertEqual(displayed.iloc[1]["Date"], forecast.iloc[0]["Date"])
        self.assertEqual(len(displayed), len(forecast) + 1)

    def test_decision_chart_connects_the_forecast_and_shows_three_colored_ranges(self) -> None:
        from app import executive_dashboard as dashboard

        history = pd.DataFrame(
            {
                "Date": pd.to_datetime(["2026-08-13", "2026-08-14"]),
                "Actual": [91.0, 93.0],
            }
        )
        forecast = pd.DataFrame(
            {
                "Date": pd.to_datetime(["2026-08-17", "2026-08-18"]),
                "PointForecast": [92.0, 91.5],
                "Lower50": [90.0, 89.0],
                "Upper50": [94.0, 94.0],
                "Lower80": [88.0, 87.0],
                "Upper80": [96.0, 96.5],
                "Lower95": [85.0, 84.0],
                "Upper95": [99.0, 100.0],
            }
        )
        result = SimpleNamespace(
            history=history,
            forecast=forecast,
            metrics={"AsOfDate": "2026-08-14"},
        )

        figure = dashboard._main_forecast_figure(result, "daily", lambda _en, zh: zh)
        traces = {trace.name: trace for trace in figure.data if trace.name}

        self.assertIn("50%经验区间", traces)
        self.assertIn("80%经验区间", traces)
        self.assertIn("95%经验区间", traces)
        self.assertEqual(len({traces[name].fillcolor for name in ("50%经验区间", "80%经验区间", "95%经验区间")}), 3)
        forecast_trace = traces["多层波动合成预测"]
        self.assertEqual(pd.Timestamp(forecast_trace.x[0]), history.iloc[-1]["Date"])
        self.assertEqual(float(forecast_trace.y[0]), float(history.iloc[-1]["Actual"]))

    def test_warning_dataset_restores_complete_brent_history_after_alignment(self) -> None:
        import pandas as pd

        from app import streamlit_app as app

        dates = pd.date_range("2020-01-01", periods=600, freq="B")
        core = pd.DataFrame({"Date": dates, "Brent": 60.0 + pd.Series(range(600)) * 0.01})
        aligned = pd.DataFrame(
            {
                "Date": dates[-180:],
                "Brent": 1.0,
                "OVX": range(180),
            }
        )

        restored = app._warning_dataset_with_complete_price_history(aligned, core)

        self.assertEqual(len(restored), 600)
        self.assertEqual(int((restored["Brent"] > 0).sum()), 600)
        self.assertEqual(int(restored["OVX"].notna().sum()), 180)
        self.assertEqual(float(restored.iloc[-1]["Brent"]), float(core.iloc[-1]["Brent"]))

    def test_warning_pool_can_keep_full_price_calendar_for_feature_specific_cleaning(self) -> None:
        import pandas as pd

        from src import variable_pool

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            dates = pd.date_range("2020-01-01", periods=600, freq="B")
            model_ready = pd.DataFrame(
                {
                    "Date": dates,
                    "WTI": 55.0,
                    "Brent": 60.0,
                    "OVX": [None] * 420 + list(range(180)),
                }
            )
            model_path = root / "model_ready.xlsx"
            model_ready.to_excel(model_path, index=False)
            registry_path = root / "registry.yaml"
            registry_path.write_text(
                """variables:
  - name: WTI
    auto_download: false
    sources: [{type: existing_model_ready_column, id: WTI}]
  - name: Brent
    auto_download: false
    sources: [{type: existing_model_ready_column, id: Brent}]
  - name: OVX
    auto_download: false
    sources: [{type: existing_model_ready_column, id: OVX}]
""",
                encoding="utf-8",
            )
            report_paths = {
                key: root / f"{key}.xlsx"
                for key in (
                    "registry_table",
                    "coverage_report",
                    "quality_report",
                    "date_alignment_report",
                    "download_status",
                )
            }
            with patch.dict(variable_pool.OUTPUT_PATHS, report_paths, clear=False):
                report_paths["date_alignment_report"].write_text("keep", encoding="utf-8")
                warning_pool = variable_pool.build_expanded_variable_pool(
                    start_date=dates.min().strftime("%Y-%m-%d"),
                    end_date=dates.max().strftime("%Y-%m-%d"),
                    model_ready_path=model_path,
                    registry_path=registry_path,
                    output_path=root / "warning_pool.xlsx",
                    auto_download=False,
                    selected_variables=["WTI", "Brent", "OVX"],
                    protected_variables=["Brent"],
                    min_coverage=0.10,
                    strict_complete_case=False,
                )

            self.assertEqual(len(warning_pool), 600)
            self.assertEqual(int(warning_pool["Brent"].notna().sum()), 600)
            self.assertEqual(int(warning_pool["OVX"].notna().sum()), 180)
            self.assertTrue(report_paths["date_alignment_report"].exists())

    def test_price_forecast_ui_accepts_custom_days_and_history_months(self) -> None:
        import inspect

        from app import streamlit_app as app

        renderer = inspect.getsource(app.render_oil_price_forecast_panel)
        self.assertIn('"Forecast horizon (business days)"', renderer)
        self.assertIn('"Historical sample (months)"', renderer)
        self.assertIn("min_value=1", renderer)
        self.assertIn("max_value=120", renderer)
        self.assertIn("min_value=12", renderer)
        self.assertIn("pd.DateOffset(months=int(history_months))", renderer)
        self.assertIn('result_payload.get("history_months") == int(history_months)', renderer)

    def test_visible_copy_names_both_oil_targets_and_avoids_thesis_wording(self) -> None:
        import inspect

        from app import streamlit_app as app

        app_source = inspect.getsource(app)
        renderer = inspect.getsource(app.render_oil_price_forecast_panel)
        self.assertIn("WTI and Brent", renderer)
        self.assertIn("WTI 与 Brent", renderer)
        self.assertNotIn("论文", app_source)
        self.assertNotIn("paper's decomposition", renderer)
        self.assertNotIn("paper channel", renderer)
        legacy_value = (
            "Dynamic paper-style selection from IMF1-IMF5 using MRGC/GPRD significance, "
            "event-window range share, variance contribution, and correlation; "
            "one or multiple IMFs may be retained"
        )
        self.assertNotIn("paper", app.localized_workflow_value(legacy_value, "en").lower())
        self.assertNotIn("论文", app.localized_workflow_value(legacy_value, "zh"))

    def test_charts_and_tables_use_bright_data_surfaces(self) -> None:
        import plotly.graph_objects as go

        from app import streamlit_app as app

        figure = app._apply_dark_plot_theme(go.Figure())
        self.assertEqual(figure.layout.paper_bgcolor, "#FDFEFB")
        self.assertEqual(figure.layout.plot_bgcolor, "#FDFEFB")
        self.assertEqual(figure.layout.font.color, "#182622")

        with patch.object(app.st, "markdown") as markdown:
            app.apply_custom_css()
        css = markdown.call_args.args[0]
        self.assertIn("--canvas: #f7f8f5;", css)
        self.assertIn("--surface: #fdfefb;", css)
        self.assertNotIn("--canvas: #f7f7f2;", css)
        self.assertIn("@keyframes ambient-field", css)
        self.assertIn("@keyframes ambient-nodes", css)
        self.assertIn("animation-timeline: scroll(root block)", css)
        self.assertIn("animation-timeline: view()", css)
        self.assertIn('[data-testid="stPlotlyChart"]', css)
        self.assertIn('[data-testid="stDataFrame"]', css)

    def test_date_chart_controls_have_dedicated_non_overlapping_space(self) -> None:
        import plotly.graph_objects as go

        from app import streamlit_app as app

        figure = go.Figure(go.Scatter(x=["2026-01-01", "2026-02-01"], y=[1, 2], name="Series"))
        figure.update_layout(title="Market path", margin=dict(t=40))
        figure.update_xaxes(
            rangeselector=dict(buttons=[dict(count=1, label="1M", step="month", stepmode="backward")]),
            rangeslider=dict(visible=True),
        )

        app._apply_dark_plot_theme(figure)

        self.assertGreaterEqual(figure.layout.margin.t, 132)
        self.assertEqual(figure.layout.xaxis.rangeselector.xanchor, "right")
        self.assertGreater(figure.layout.xaxis.rangeselector.y, figure.layout.legend.y)
        self.assertEqual(figure.layout.title.xanchor, "left")

    def test_interactive_controls_have_visible_keyboard_focus(self) -> None:
        from app import streamlit_app as app

        with patch.object(app.st, "markdown") as markdown:
            app.apply_custom_css()

        css = markdown.call_args.args[0]
        self.assertIn("button:focus-visible", css)
        self.assertIn('[role="tab"]:focus-visible', css)
        self.assertIn("outline: 3px solid rgba(53, 107, 101, 0.28)", css)
        self.assertIn("outline-offset: 2px", css)

    def test_data_surfaces_and_expanders_stay_bright(self) -> None:
        from app import streamlit_app as app

        with patch.object(app.st, "markdown") as markdown:
            app.apply_custom_css()

        css = markdown.call_args.args[0]
        self.assertIn('[data-testid="stDataFrame"], [data-testid="stTable"], [data-testid="stPlotlyChart"]', css)
        self.assertIn("background: var(--surface) !important;", css)
        self.assertIn('[data-testid="stExpander"]', css)
        self.assertIn("border-radius: 16px !important;", css)
        self.assertNotIn("#F26A4B", css)

    def test_bright_theme_covers_interactive_controls(self) -> None:
        from app import streamlit_app as app

        with patch.object(app.st, "markdown") as markdown:
            app.apply_custom_css()

        css = markdown.call_args.args[0]
        self.assertIn('div[data-baseweb="select"] > div', css)
        self.assertIn("background: var(--surface) !important;", css)
        self.assertIn('[data-testid="stRadio"] [role="radiogroup"] > label:has(input:checked)', css)
        self.assertIn('[data-testid="baseButton-primary"]', css)
        self.assertIn('[data-testid="stFileUploaderDropzone"]', css)
        self.assertIn("color: var(--ink) !important;", css)

    def test_result_plotly_charts_are_loaded_as_dynamic_figures(self) -> None:
        from app import streamlit_app as app
        import plotly.graph_objects as go

        with tempfile.TemporaryDirectory() as temp_dir:
            chart_path = Path(temp_dir) / "event.json"
            figure = go.Figure(go.Scatter(x=[1, 2, 3], y=[3, 1, 2]))
            chart_path.write_text(figure.to_json(), encoding="utf-8")
            with (
                patch.object(app.st, "columns", return_value=(nullcontext(), nullcontext())),
                patch.object(app.st, "plotly_chart") as plotly_chart,
                patch.object(app.st, "caption"),
                patch.object(app.st, "write"),
                patch.object(app, "render_artifact_download_button"),
            ):
                app.render_downloadable_plotly("Event chart", chart_path, "Description")

        plotly_chart.assert_called_once()
        rendered = plotly_chart.call_args.args[0]
        self.assertEqual(len(rendered.data), 1)
        self.assertEqual(rendered.layout.paper_bgcolor, "#FDFEFB")

    def test_cloud_runtime_detection_supports_override_and_streamlit_marker(self) -> None:
        from app.streamlit_app import is_cloud_runtime

        self.assertTrue(is_cloud_runtime({"NET_IMPACT_RUNTIME_MODE": "cloud"}, Path("C:/project")))
        self.assertFalse(is_cloud_runtime({"NET_IMPACT_RUNTIME_MODE": "local"}, Path("/mount/src/app")))
        self.assertTrue(is_cloud_runtime({"STREAMLIT_SHARING_MODE": "true"}, Path("C:/project")))
        self.assertTrue(is_cloud_runtime({}, Path("/mount/src/net-impact")))
        self.assertFalse(is_cloud_runtime({}, Path("C:/project")))
        with patch.dict(os.environ, {"NET_IMPACT_RUNTIME_MODE": "cloud"}, clear=True):
            self.assertTrue(is_cloud_runtime(project_root=Path("C:/project")))

    def test_upload_priority_maps_to_existing_value_preference(self) -> None:
        from app.streamlit_app import prefer_existing_variable_values

        self.assertFalse(prefer_existing_variable_values({"use_uploaded_local_data_first": True}))
        self.assertTrue(prefer_existing_variable_values({"use_uploaded_local_data_first": False}))
        self.assertFalse(prefer_existing_variable_values({}))

    def test_result_archive_contains_outputs_and_excludes_workspace_secrets(self) -> None:
        from app.streamlit_app import build_results_archive

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            table = root / "outputs" / "tables" / "summary.xlsx"
            figure = root / "outputs" / "figures" / "impact.png"
            secret = root / "API.env"
            upload = root / "data" / "raw" / "uploads" / "private.csv"
            table.parent.mkdir(parents=True)
            figure.parent.mkdir(parents=True)
            (table.parent / "empty-directory").mkdir()
            upload.parent.mkdir(parents=True)
            table.write_bytes(b"table")
            figure.write_bytes(b"figure")
            secret.write_text("FRED_API_KEY=secret", encoding="utf-8")
            upload.write_text("private", encoding="utf-8")

            archive_bytes, archive_names = build_results_archive(root)

            self.assertEqual(
                archive_names,
                ["outputs/figures/impact.png", "outputs/tables/summary.xlsx"],
            )
            with ZipFile(BytesIO(archive_bytes)) as archive:
                self.assertEqual(sorted(archive.namelist()), archive_names)
                self.assertEqual(archive.read("outputs/tables/summary.xlsx"), b"table")
                self.assertNotIn("API.env", archive.namelist())
                self.assertNotIn("data/raw/uploads/private.csv", archive.namelist())

    def test_result_archive_is_empty_when_no_results_exist(self) -> None:
        from app.streamlit_app import build_results_archive

        with tempfile.TemporaryDirectory() as temp_dir:
            archive_bytes, archive_names = build_results_archive(Path(temp_dir))

        self.assertEqual(archive_bytes, b"")
        self.assertEqual(archive_names, [])

    def test_upload_priority_checkbox_is_removed_from_the_interface(self) -> None:
        source = (Path(__file__).resolve().parents[1] / "app" / "streamlit_app.py").read_text(encoding="utf-8")

        self.assertNotIn("Use uploaded local data first", source)
        self.assertNotIn("优先使用本地上传数据", source)

    def test_cloud_tool_menu_renders_per_browser_api_controls_only(self) -> None:
        from app import streamlit_app as app

        with (
            patch.object(app, "is_cloud_runtime", return_value=True),
            patch.object(app, "render_cloud_api_tool_menu") as cloud_api_menu,
        ):
            app.render_top_tool_menu()

        cloud_api_menu.assert_called_once_with()

    def test_cloud_cookie_keys_are_restored_into_request_local_context(self) -> None:
        from app import streamlit_app as app
        from src.api_credentials import encrypt_api_keys

        encryption_key = "MDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDA="
        token = encrypt_api_keys({"FRED_API_KEY": "a" * 32}, encryption_key)

        session_state: dict[str, object] = {}
        with (
            patch.object(app, "is_cloud_runtime", return_value=True),
            patch.object(app, "browser_api_cookie_encryption_key", return_value=encryption_key),
            patch.object(app, "read_browser_api_cookie", return_value=token),
            patch.object(app.st, "session_state", session_state),
            patch.object(app, "set_session_api_keys") as activate_keys,
        ):
            restored = app.restore_api_credentials_for_request()

        self.assertEqual(restored, {"FRED_API_KEY": "a" * 32})
        self.assertEqual(session_state[app.BROWSER_API_SESSION_STATE], restored)
        activate_keys.assert_called_once_with(restored, allow_shared_fallback=False)

    def test_cloud_cookie_restore_fails_closed_without_crashing_the_app(self) -> None:
        from app import streamlit_app as app

        with (
            patch.object(app, "is_cloud_runtime", return_value=True),
            patch.object(
                app,
                "browser_api_cookie_encryption_key",
                side_effect=RuntimeError("cloud secrets are temporarily unavailable"),
            ),
            patch.object(app, "set_session_api_keys") as activate_keys,
        ):
            restored = app.restore_api_credentials_for_request()

        self.assertEqual(restored, {})
        activate_keys.assert_called_once_with({}, allow_shared_fallback=False)

    def test_cloud_api_status_ignores_shared_file_and_environment_keys(self) -> None:
        from app import streamlit_app as app

        with (
            patch.object(app, "read_api_env_values", return_value={"EIA_API_KEY": "shared-file-key"}),
            patch.dict(os.environ, {"EIA_API_KEY": "shared-environment-key"}, clear=False),
            patch.object(
                app,
                "validate_fred_api_key",
                return_value={"status": "valid", "message": "verified"},
            ),
        ):
            status = app.api_key_status(
                {"FRED_API_KEY": "a" * 32},
                include_shared_sources=False,
            )

        self.assertTrue(status["keys"]["FRED_API_KEY"]["configured"])
        self.assertEqual(status["keys"]["FRED_API_KEY"]["source"], "this browser")
        self.assertFalse(status["keys"]["EIA_API_KEY"]["configured"])

    def test_api_panel_save_does_not_interrupt_the_rest_of_the_page_rerun(self) -> None:
        import inspect

        from app import streamlit_app as app

        source = inspect.getsource(app.render_api_settings_panel)

        self.assertNotIn("st.rerun()", source)

    def test_browser_cookie_secure_flag_follows_the_access_protocol(self) -> None:
        from app.streamlit_app import browser_api_cookie_is_secure

        self.assertTrue(browser_api_cookie_is_secure("https://example.streamlit.app"))
        self.assertFalse(browser_api_cookie_is_secure("http://localhost:8501"))

    def test_browser_cookie_value_is_url_decoded_before_decryption(self) -> None:
        from app.streamlit_app import decode_browser_api_cookie_value

        self.assertEqual(decode_browser_api_cookie_value("encrypted-token%3D%3D"), "encrypted-token==")

    def test_clear_browser_keys_expires_cookie_even_for_a_new_session(self) -> None:
        from app import streamlit_app as app

        class NewSessionController:
            def __init__(self) -> None:
                self.set_calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

            def set(self, *args: object, **kwargs: object) -> None:
                self.set_calls.append((args, kwargs))

        controller = NewSessionController()
        session_state = {app.BROWSER_API_SESSION_STATE: {"EIA_API_KEY": "private"}}
        with (
            patch.object(app, "get_browser_cookie_controller", return_value=controller),
            patch.object(app, "browser_api_cookie_is_secure", return_value=True),
            patch.object(app.st, "session_state", session_state),
            patch.object(app, "set_session_api_keys") as activate_keys,
        ):
            app.clear_browser_api_values()

        self.assertEqual(len(controller.set_calls), 1)
        args, kwargs = controller.set_calls[0]
        self.assertEqual(args, (app.BROWSER_API_COOKIE_NAME, ""))
        self.assertEqual(kwargs["max_age"], 0)
        self.assertEqual(session_state[app.BROWSER_API_SESSION_STATE], {})
        activate_keys.assert_called_once_with({}, allow_shared_fallback=False)

    def test_fred_validation_cache_uses_a_digest_instead_of_the_secret(self) -> None:
        from app import streamlit_app as app

        class ValidFredResponse:
            status_code = 200
            text = ""

            @staticmethod
            def json() -> dict[str, object]:
                return {"seriess": [{"id": "DGS10"}]}

        api_key = "a" * 32
        app.API_VALIDATION_CACHE.clear()
        with patch("requests.get", return_value=ValidFredResponse()):
            result = app.validate_fred_api_key(api_key)

        expected_cache_key = f"fred:{hashlib.sha256(api_key.encode()).hexdigest()}"
        self.assertEqual(result["status"], "valid")
        self.assertIn(expected_cache_key, app.API_VALIDATION_CACHE)
        self.assertTrue(all(api_key not in cache_key for cache_key in app.API_VALIDATION_CACHE))


if __name__ == "__main__":
    unittest.main()
