import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


class VariablePoolWorkflowTests(unittest.TestCase):
    def test_default_variable_pool_is_full_pool_without_bdti(self) -> None:
        from app.streamlit_app import load_variable_pool_options

        options, defaults = load_variable_pool_options()

        self.assertNotIn("BDTI", options)
        self.assertNotIn("BDTI", defaults)
        self.assertIn("ShanghaiSC", options)
        self.assertIn("ShanghaiSC", defaults)
        self.assertIn("VIX", options)
        self.assertIn("VIX", defaults)
        for variable in ["WTI", "Brent", "GPRD", "EPU", "TPU", "EMV", "Gold", "OVX", "DollarIndex", "TNote10Y"]:
            self.assertIn(variable, defaults)
        self.assertGreaterEqual(len(defaults), 20)

    def test_gappy_variable_is_retained_even_when_coverage_is_below_threshold(self) -> None:
        from src import variable_pool as vp

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            model_ready_path = temp_path / "model_ready.xlsx"
            registry_path = temp_path / "registry.yaml"
            output_dir = temp_path / "outputs"
            output_dir.mkdir()

            pd.DataFrame(
                {
                    "Date": pd.to_datetime(["2022-10-07", "2022-10-10", "2022-10-11"]),
                    "WTI": [92.64, 91.13, 89.35],
                    "GPRD": [144.24, 193.34, 228.25],
                    "GAPPY": [10.0, 11.0, pd.NA],
                }
            ).to_excel(model_ready_path, index=False)
            registry_path.write_text(
                """
variables:
  - name: WTI
    auto_download: false
    sources:
      - type: existing_model_ready_column
        id: WTI
  - name: GPRD
    auto_download: false
    sources:
      - type: existing_model_ready_column
        id: GPRD
  - name: GAPPY
    auto_download: false
    sources:
      - type: existing_model_ready_column
        id: GAPPY
""",
                encoding="utf-8",
            )
            output_paths = {
                key: output_dir / Path(path).name
                for key, path in vp.OUTPUT_PATHS.items()
            }

            with patch.object(vp, "OUTPUT_PATHS", output_paths):
                expanded = vp.build_expanded_variable_pool(
                    start_date="2022-10-07",
                    end_date="2022-10-11",
                    model_ready_path=model_ready_path,
                    registry_path=registry_path,
                    output_path=output_paths["expanded_pool"],
                    auto_download=False,
                    merge_to_model_ready=False,
                    min_coverage=0.95,
                    selected_variables=["WTI", "GPRD", "GAPPY"],
                    protected_variables=["WTI"],
                )
                quality = pd.read_excel(output_paths["quality_report"])
                coverage = pd.read_excel(output_paths["coverage_report"])

            self.assertEqual(expanded["Date"].min(), pd.Timestamp("2022-10-07"))
            self.assertIn("GAPPY", expanded.columns)
            self.assertEqual(len(expanded), 2)
            self.assertEqual(
                expanded["Date"].dt.strftime("%Y-%m-%d").tolist(),
                ["2022-10-07", "2022-10-10"],
            )
            gappy_quality = quality.set_index("Variable").loc["GAPPY"]
            self.assertEqual(gappy_quality["Action"], "Kept")
            self.assertIn("coverage below threshold", gappy_quality["Reason"])
            gappy_coverage = coverage.set_index("Variable").loc["GAPPY"]
            self.assertEqual(int(gappy_coverage["MissingCount"]), 1)

    def test_cache_fallback_status_is_not_reported_as_downloaded(self) -> None:
        from src import data_fetcher
        from src import variable_pool as vp

        with tempfile.TemporaryDirectory() as temp_dir:
            cache_file = Path(temp_dir) / "CacheVar.csv"
            entry = {
                "name": "CacheVar",
                "auto_download": True,
                "is_proxy": False,
                "frequency": "Daily",
                "daily_alignment": "Native daily series.",
                "sources": [{"type": "fake_source", "id": "X"}],
                "cache_file": str(cache_file),
                "note": "",
            }
            returned = pd.DataFrame(
                {
                    "Date": pd.to_datetime(["2022-10-07", "2022-10-11"]),
                    "CacheVar": [1.0, 2.0],
                }
            )

            def fake_fetch_series_with_fallback(
                name: str,
                sources: list[dict[str, str]],
                start_date: str,
                end_date: str,
                cache_path: str | Path,
                force_refresh: bool = False,
            ) -> pd.DataFrame:
                data_fetcher.LAST_SOURCE_USED[name] = "cache:CacheVar.csv"
                data_fetcher.LAST_SOURCE_NOTES[name] = (
                    "Loaded from existing cache after automatic sources failed. "
                    "Failure details: fake_source:X failed"
                )
                return returned

            with patch.object(data_fetcher, "fetch_series_with_fallback", fake_fetch_series_with_fallback):
                _, status = vp._fetch_registry_variable(
                    entry,
                    start_date="2022-10-07",
                    end_date="2022-10-11",
                    force_refresh=True,
                )

            self.assertEqual(status["ActualSource"], "cache:CacheVar.csv")
            self.assertEqual(status["Status"], "LoadedCacheAfterSourceFailure")
            self.assertIn("Failure details", status["Note"])

    def test_data_refresh_preparation_workbook_includes_periods_and_variable_ranges(self) -> None:
        from app import streamlit_app as app

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            patched_paths = dict(app.PATHS)
            patched_paths["data_refresh_preparation_workbook"] = temp_path / "data_refresh_and_preparation.xlsx"
            for key in [
                "expanded_variable_pool",
                "variable_pool_download_status",
                "variable_pool_coverage_report",
                "variable_pool_quality_report",
                "variable_pool_date_alignment_report",
                "data_source_log",
            ]:
                patched_paths[key] = temp_path / f"{key}.xlsx"

            prepared = pd.DataFrame(
                {
                    "Date": pd.to_datetime(["2022-10-07", "2022-10-10", "2022-10-11"]),
                    "WTI": [92.64, 91.13, 89.35],
                    "GAPPY": [1.0, 2.0, 3.0],
                }
            )
            summary = {
                "requested_window_start_date": "2022-10-07",
                "requested_window_end_date": "2022-10-10",
                "requested_window_trading_days": 2,
                "requested_event_start_date": "2022-10-11",
                "requested_event_end_date": "2022-10-11",
                "requested_event_trading_days": 1,
                "effective_window_start_date": "2022-10-07",
                "effective_window_end_date": "2022-10-10",
                "effective_window_trading_days": 2,
                "effective_event_start_date": "2022-10-11",
                "effective_event_end_date": "2022-10-11",
                "effective_event_trading_days": 1,
                "common_data_start_date": "2022-10-07",
                "common_data_end_date": "2022-10-11",
                "variable_update_review_table": pd.DataFrame(
                    [
                        {
                            "Variable": "GAPPY",
                            "AutoDownload": True,
                            "UpdateResult": "Auto-updated",
                            "Status": "Downloaded",
                            "EarliestDate": "2022-10-07",
                            "LatestDate": "2022-10-11",
                            "MissingCount": 0,
                            "CoveragePercent": "100.0%",
                            "ActualSource": "test_source",
                            "Note": "",
                        }
                    ]
                ),
            }

            with patch.object(app, "PATHS", patched_paths):
                workbook_path = app.write_data_refresh_preparation_workbook(summary, prepared)
                workbook = pd.read_excel(workbook_path, sheet_name=None)

            self.assertIn("PreparedData", workbook)
            self.assertIn("PeriodSummary", workbook)
            self.assertIn("VariableUpdateRanges", workbook)
            self.assertIn("Cleaned event window", workbook["PeriodSummary"]["Period"].tolist())
            self.assertEqual(workbook["VariableUpdateRanges"].loc[0, "AvailableStart"], "2022-10-07")
            self.assertEqual(workbook["VariableUpdateRanges"].loc[0, "AvailableEnd"], "2022-10-11")


if __name__ == "__main__":
    unittest.main()
