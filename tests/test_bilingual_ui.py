"""Tests for the website language switch."""

from __future__ import annotations

import unittest


class BilingualUITests(unittest.TestCase):
    def test_vmd_imf_range_is_one_to_one_hundred(self) -> None:
        from app.streamlit_app import MAX_VMD_IMF_COUNT, MIN_VMD_IMF_COUNT

        self.assertEqual(MIN_VMD_IMF_COUNT, 1)
        self.assertEqual(MAX_VMD_IMF_COUNT, 100)

    def test_localized_text_selects_chinese(self) -> None:
        from app.streamlit_app import localized_text

        self.assertEqual(localized_text("Run Analysis", "运行分析", "zh"), "运行分析")

    def test_localized_text_selects_english(self) -> None:
        from app.streamlit_app import localized_text

        self.assertEqual(localized_text("Run Analysis", "运行分析", "en"), "Run Analysis")

    def test_runtime_status_translation_preserves_dynamic_values(self) -> None:
        from app.streamlit_app import localized_runtime_message

        message = "Data refresh completed: 2024-01-01 to 2024-03-31"

        self.assertEqual(
            localized_runtime_message(message, "zh"),
            "数据更新完成: 2024-01-01 至 2024-03-31",
        )
        self.assertEqual(localized_runtime_message(message, "en"), message)

    def test_analysis_workflow_statuses_are_fully_localized_in_chinese(self) -> None:
        from app.streamlit_app import localized_runtime_message

        cases = {
            "Data refresh completed. Clean market data range: 2024-01-01 to 2024-03-31.":
                "数据更新完成。清洗后市场数据范围：2024-01-01 至 2024-03-31。",
            "Core market data freshness check passed. Latest complete core-market row before strict cleaning: 2024-03-29.":
                "核心市场数据新鲜度检查通过。严格清洗前最新完整核心市场数据日期：2024-03-29。",
            "Expanded variable pool refreshed and merged into model-ready data. Additional candidate columns: VIX, SP500.":
                "扩展变量池已更新并合并到模型数据。新增候选变量：VIX, SP500。",
            "Running VMD decomposition review with K = 4...":
                "正在运行 VMD 分解审查，K = 4……",
            "Determining selected-scale extrema and FEVD horizon h before TVP/FEVD...":
                "正在确定所选尺度极值与 FEVD 预测期 h，随后进入 TVP/FEVD……",
            "Data refresh and preparation workbook created: data_refresh_and_preparation.xlsx.":
                "数据更新与准备工作簿已生成：data_refresh_and_preparation.xlsx。",
        }

        for english, chinese in cases.items():
            with self.subTest(message=english):
                self.assertEqual(localized_runtime_message(english, "zh"), chinese)

    def test_variable_name_follows_selected_language(self) -> None:
        from app.streamlit_app import format_variable_option

        metadata = {
            "ShanghaiSC": {
                "FullName": "Shanghai INE crude oil futures main-contract settlement price.",
                "Frequency": "Daily",
                "Sources": "exchange_futures_daily:INE:SC",
            }
        }

        chinese_label = format_variable_option("ShanghaiSC", metadata, "zh")
        english_label = format_variable_option("ShanghaiSC", metadata, "en")

        self.assertIn("上海原油期货", chinese_label)
        self.assertIn("Shanghai INE crude oil futures", english_label)
        self.assertNotIn("上海国际能源交易中心", english_label)
        self.assertNotIn("exchange_futures_daily", chinese_label)
        self.assertNotIn("_", chinese_label)
        self.assertNotIn("^", chinese_label)

    def test_metadata_sources_are_human_readable(self) -> None:
        from app.streamlit_app import selected_variable_metadata_frame

        metadata = {
            "VIX": {
                "FullName": "CBOE equity market volatility index.",
                "Frequency": "Daily",
                "SourceTypes": ["fred", "yfinance"],
                "AutoDownload": True,
                "IsProxy": False,
            }
        }

        frame = selected_variable_metadata_frame(["VIX"], metadata, "zh")
        source_text = str(frame.loc[0, "数据来源"])

        self.assertEqual(source_text, "FRED、Yahoo Finance")
        self.assertNotIn("_", source_text)
        self.assertNotIn("^", source_text)

    def test_unknown_uploaded_variable_keeps_its_name(self) -> None:
        from app.streamlit_app import localized_variable_name

        metadata = {"MyFactor": {"FullName": "My custom factor"}}

        self.assertEqual(localized_variable_name("MyFactor", metadata, "zh"), "My custom factor")
        self.assertEqual(localized_variable_name("MyFactor", metadata, "en"), "My custom factor")


if __name__ == "__main__":
    unittest.main()
