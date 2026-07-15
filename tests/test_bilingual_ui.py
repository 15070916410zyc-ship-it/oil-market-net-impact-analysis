"""Tests for the website language switch."""

from __future__ import annotations

import unittest

import pandas as pd


class BilingualUITests(unittest.TestCase):
    def test_result_table_headings_and_explanations_are_localized(self) -> None:
        from app.streamlit_app import localized_workflow_frame

        frame = pd.DataFrame(
            [
                {
                    "IncludedDrivers": "OVX, Gold",
                    "DriverSelectionRule": (
                        "Selected by selected-scale MRGC/BIC Granger test at p < 0.10."
                    ),
                    "VMDSource": "Python vmdpy recomputed for the selected sample.",
                }
            ]
        )

        localized = localized_workflow_frame(frame, "zh")

        self.assertEqual(
            list(localized.columns),
            ["纳入的驱动变量", "驱动变量选择规则", "VMD 数据来源"],
        )
        self.assertEqual(localized.loc[0, "纳入的驱动变量"], "OVX, Gold")
        self.assertEqual(
            localized.loc[0, "驱动变量选择规则"],
            "依据所选尺度的 MRGC/BIC Granger 检验结果选入，显著性水平为 p < 0.10。",
        )
        self.assertEqual(
            localized.loc[0, "VMD 数据来源"],
            "针对所选样本使用 Python vmdpy 重新计算。",
        )

    def test_external_contribution_figure_title_follows_selected_language(self) -> None:
        from app.streamlit_app import external_contribution_figure_title

        self.assertEqual(
            external_contribution_figure_title("WTI", "IMF3+IMF4", "zh"),
            "WTI IMF3+IMF4 外部相对贡献",
        )
        self.assertEqual(
            external_contribution_figure_title("WTI", "IMF3+IMF4", "en"),
            "WTI IMF3+IMF4 external relative contribution",
        )

    def test_dynamic_window_warnings_use_natural_chinese_word_order(self) -> None:
        from app.streamlit_app import localized_runtime_message

        cases = {
            (
                "Prepared common data window 2024-01-02 to 2026-03-20 does not fully "
                "cover the initially selected analysis window 2024-01-01 to 2026-03-20."
            ): (
                "准备好的公共数据窗口为 2024-01-02 至 2026-03-20，未完全覆盖最初选择的"
                "分析窗口 2024-01-01 至 2026-03-20。"
            ),
            (
                "The selected pre-event window (2022-11-26 to 2025-01-10) contains "
                "555 business days before strict cleaning, but only 520 complete "
                "observations remain after strict missing-data removal."
            ): (
                "所选事件前窗口（2022-11-26 至 2025-01-10）在严格清洗前包含 555 个工作日，"
                "但严格剔除缺失值后仅剩 520 个完整观测。"
            ),
            (
                "There are 3 business days between the pre-event window end (2025-01-08) "
                "and the event window start (2025-01-13). These dates were removed before "
                "period splitting because at least one selected retained variable was missing."
            ): (
                "事件前窗口结束日期（2025-01-08）与事件窗口开始日期（2025-01-13）之间有 "
                "3 个工作日。由于至少一个已选保留变量存在缺失值，这些日期已在划分窗口前剔除。"
            ),
        }

        for english, chinese in cases.items():
            with self.subTest(message=english):
                self.assertEqual(localized_runtime_message(english, "zh"), chinese)

    def test_period_summary_rows_are_localized_as_complete_phrases(self) -> None:
        from app.streamlit_app import localized_workflow_frame

        frame = pd.DataFrame(
            [
                {
                    "Period": "Requested pre-event window",
                    "Start": "2022-11-26",
                    "End": "2025-01-10",
                    "TradingDays": 555,
                    "Basis": "Requested business-day window before strict complete-case cleaning.",
                }
            ]
        )

        localized = localized_workflow_frame(frame, "zh")

        self.assertEqual(list(localized.columns), ["期间", "开始日期", "结束日期", "交易日数", "计算依据"])
        self.assertEqual(localized.loc[0, "期间"], "请求的事件前窗口")
        self.assertEqual(
            localized.loc[0, "计算依据"],
            "严格完整样本清洗前请求的工作日窗口。",
        )

    def test_dynamic_alignment_note_is_localized_without_losing_limiters(self) -> None:
        from app.streamlit_app import localized_runtime_message

        english = (
            "Common window starts at the latest first available date (2024-01-02, limited by WTI) "
            "and ends at the earliest last available date (2026-03-20, limited by Brent, OVX). "
            "Strict complete-case cleaning was applied before the pre-event and event windows were split."
        )

        self.assertEqual(
            localized_runtime_message(english, "zh"),
            "公共数据窗口从各变量最晚的首个有效日期开始（2024-01-02，受 WTI 限制），"
            "到各变量最早的最后有效日期结束（2026-03-20，受 Brent, OVX 限制）。"
            "在划分事件前窗口与事件窗口之前，已执行严格完整样本清洗。",
        )

    def test_vmd_imf_range_is_one_to_thirty(self) -> None:
        from app.streamlit_app import MAX_VMD_IMF_COUNT, MIN_VMD_IMF_COUNT

        self.assertEqual(MIN_VMD_IMF_COUNT, 1)
        self.assertEqual(MAX_VMD_IMF_COUNT, 30)

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
