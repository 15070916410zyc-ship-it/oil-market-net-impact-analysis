"""Streamlit app for the multiscale net-impact analysis system."""

from __future__ import annotations

import importlib
from io import BytesIO
import os
import re
import shutil
from pathlib import Path
import sys
from typing import Any, Callable, Literal, Mapping
import warnings
from zipfile import ZIP_DEFLATED, ZipFile

import pandas as pd
import streamlit as st


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

DEFAULT_PRE_EVENT_WINDOW_TRADING_DAYS = 300
DEFAULT_VARIABLE_SELECTION_VERSION = "full-pool-no-bdti-v7-compact-selector"
MIN_VMD_IMF_COUNT = 1
MAX_VMD_IMF_COUNT = 100
CORE_MARKET_FRESHNESS_COLUMNS = ["WTI", "Brent", "Gold", "OVX", "DollarIndex", "TNote10Y", "GPRD"]
NET_IMPACT_CONFIRMATION_STATE = "net_impact_pending_variable_update_confirmation"
NET_IMPACT_VMD_CONFIRMATION_STATE = "net_impact_pending_vmd_confirmation"
NET_IMPACT_TVP_CONFIRMATION_STATE = "net_impact_pending_tvp_confirmation"
API_ENV_PATH = PROJECT_ROOT / "API.env"
API_KEY_ORDER = ["FRED_API_KEY", "EIA_API_KEY"]
API_VALIDATION_CACHE: dict[str, dict[str, str]] = {}
UI_LANGUAGE_STATE = "ui_language"
LanguageCode = Literal["zh", "en"]
RESULT_ARTIFACT_DIRECTORIES = ("tables", "figures", "reports", "models")

VARIABLE_CHINESE_NAMES: dict[str, str] = {
    "WTI": "WTI 西得克萨斯中质原油期货价格",
    "GPRD": "全球地缘政治风险日度指数",
    "OVX": "CBOE 原油 ETF 波动率指数",
    "DollarIndex": "美国广义美元指数",
    "TNote10Y": "美国 10 年期国债收益率",
    "Gold": "黄金期货价格",
    "VIX": "CBOE 股票市场波动率指数",
    "SP500": "标普 500 指数",
    "Nasdaq": "纳斯达克综合指数",
    "NaturalGas": "亨利港天然气现货价格",
    "US2Y": "美国 2 年期国债收益率",
    "FedFunds": "联邦基金有效利率",
    "CNYUSD": "美元兑人民币即期汇率",
    "ShanghaiSC": "上海国际能源交易中心原油期货主力结算价",
    "ShanghaiFU": "上海期货交易所燃料油期货主力结算价",
    "Brent": "布伦特原油期货价格",
    "Gasoline": "RBOB 汽油期货价格",
    "HeatingOil": "取暖油期货价格",
    "Copper": "铜期货价格",
    "Silver": "白银期货价格",
    "EPU": "美国经济政策不确定性指数",
    "TPU": "贸易政策不确定性指数",
    "EMV": "股票市场波动新闻指数",
}

VARIABLE_SHORT_CHINESE_NAMES: dict[str, str] = {
    "WTI": "西得克萨斯原油",
    "GPRD": "地缘政治风险",
    "OVX": "原油波动率",
    "DollarIndex": "美元指数",
    "TNote10Y": "美国 10 年期国债",
    "Gold": "黄金",
    "VIX": "市场波动率",
    "SP500": "标普 500",
    "Nasdaq": "纳斯达克",
    "NaturalGas": "天然气",
    "US2Y": "美国 2 年期国债",
    "FedFunds": "联邦基金利率",
    "CNYUSD": "美元兑人民币",
    "ShanghaiSC": "上海原油期货",
    "ShanghaiFU": "上海燃料油期货",
    "Brent": "布伦特原油",
    "Gasoline": "RBOB 汽油",
    "HeatingOil": "取暖油",
    "Copper": "铜",
    "Silver": "白银",
    "EPU": "经济政策不确定性",
    "TPU": "贸易政策不确定性",
    "EMV": "股票市场波动新闻",
}

SOURCE_DISPLAY_NAMES: dict[str, tuple[str, str]] = {
    "existing_model_ready_column": ("Built-in dataset", "内置数据"),
    "fred": ("FRED", "FRED"),
    "yfinance": ("Yahoo Finance", "Yahoo Finance"),
    "stooq": ("Stooq", "Stooq"),
    "treasury_yield_curve": ("U.S. Treasury", "美国财政部"),
    "nyfed_rate": ("Federal Reserve Bank of New York", "纽约联储"),
    "exchange_futures_daily": ("Official futures exchange", "期货交易所"),
    "sina_main_futures": ("Sina Finance", "新浪财经"),
    "policy_uncertainty_daily": ("Policy Uncertainty Database", "政策不确定性数据库"),
}


PATHS = {
    "clean_market": PROJECT_ROOT / "data" / "processed" / "clean_market_data.xlsx",
    "model_ready": PROJECT_ROOT / "data" / "processed" / "model_ready_data.xlsx",
    "data_source_log": PROJECT_ROOT / "outputs" / "tables" / "data_source_log.xlsx",
    "expanded_variable_pool": PROJECT_ROOT / "outputs" / "tables" / "expanded_variable_pool.xlsx",
    "data_refresh_preparation_workbook": PROJECT_ROOT / "outputs" / "tables" / "data_refresh_and_preparation.xlsx",
    "variable_pool_download_status": PROJECT_ROOT / "outputs" / "tables" / "variable_pool_download_status.xlsx",
    "variable_pool_coverage_report": PROJECT_ROOT / "outputs" / "tables" / "variable_pool_coverage_report.xlsx",
    "variable_pool_quality_report": PROJECT_ROOT / "outputs" / "tables" / "variable_pool_quality_filter_report.xlsx",
    "variable_pool_update_review_report": PROJECT_ROOT / "outputs" / "tables" / "variable_pool_update_review_report.xlsx",
    "variable_pool_date_alignment_report": PROJECT_ROOT / "outputs" / "tables" / "variable_pool_date_alignment_report.xlsx",
    "variable_registry_table": PROJECT_ROOT / "outputs" / "tables" / "variable_registry.xlsx",
    "variable_registry_config": PROJECT_ROOT / "config" / "variable_sources.yaml",
    "paper_dashboard": PROJECT_ROOT / "outputs" / "tables" / "paper_replication_dashboard.xlsx",
    "paper_summary": PROJECT_ROOT / "outputs" / "tables" / "paper_replication_summary.xlsx",
    "paper_mrgc": PROJECT_ROOT / "outputs" / "tables" / "paper_mrgc_results.xlsx",
    "paper_vmd_center_frequencies": PROJECT_ROOT / "outputs" / "tables" / "paper_vmd_center_frequencies.xlsx",
    "paper_scale_statistics": PROJECT_ROOT / "outputs" / "tables" / "paper_scale_statistics.xlsx",
    "paper_selected_scale_effect": PROJECT_ROOT / "outputs" / "tables" / "paper_selected_scale_effect.xlsx",
    "paper_h_review": PROJECT_ROOT / "outputs" / "tables" / "paper_fevd_h_review.xlsx",
    "paper_selected_scale_granger": PROJECT_ROOT / "outputs" / "tables" / "paper_selected_scale_granger.xlsx",
    "paper_tvp_settings": PROJECT_ROOT / "outputs" / "tables" / "paper_tvp_var_settings.xlsx",
    "paper_contribution_weights": PROJECT_ROOT / "outputs" / "tables" / "paper_external_contribution_weights.xlsx",
    "paper_net_impacts": PROJECT_ROOT / "outputs" / "tables" / "paper_net_impacts.xlsx",
    "paper_break_test": PROJECT_ROOT / "outputs" / "tables" / "paper_structural_break_test.xlsx",
    "paper_optimal_break_rss": PROJECT_ROOT / "outputs" / "tables" / "paper_optimal_break_rss_profile.xlsx",
    "paper_selected_scale_series": PROJECT_ROOT / "outputs" / "tables" / "paper_selected_scale_series.xlsx",
    "paper_price_event_figure": PROJECT_ROOT / "outputs" / "figures" / "paper_price_event.png",
    "paper_selected_scale_figure": PROJECT_ROOT / "outputs" / "figures" / "paper_selected_scale_trend.png",
    "paper_mrgc_figure": PROJECT_ROOT / "outputs" / "figures" / "paper_mrgc_heatmap.png",
    "paper_scale_statistics_figure": PROJECT_ROOT / "outputs" / "figures" / "paper_scale_statistics.png",
    "paper_hht_imf1_figure": PROJECT_ROOT / "outputs" / "figures" / "paper_hht_imf1_frequency.png",
    "paper_contribution_figure": PROJECT_ROOT / "outputs" / "figures" / "paper_external_contribution.png",
    "paper_net_impact_figure": PROJECT_ROOT / "outputs" / "figures" / "paper_net_impacts.png",
    "paper_break_figure": PROJECT_ROOT / "outputs" / "figures" / "paper_structural_break_fit.png",
    "paper_optimal_break_rss_figure": PROJECT_ROOT / "outputs" / "figures" / "paper_optimal_break_rss_profile.png",
    "upload_dir": PROJECT_ROOT / "data" / "raw" / "uploads",
    "upload_original_dir": PROJECT_ROOT / "data" / "raw" / "uploads" / "originals",
    "uploaded_variable_manifest": PROJECT_ROOT / "outputs" / "tables" / "uploaded_variable_manifest.xlsx",
    "uploaded_variable_quality_report": PROJECT_ROOT / "outputs" / "tables" / "uploaded_variable_quality_report.xlsx",
}


def is_cloud_runtime(
    environment: Mapping[str, str] | None = None,
    project_root: Path = PROJECT_ROOT,
) -> bool:
    """Return whether the app is running in a hosted Streamlit workspace."""
    values = os.environ if environment is None else environment
    explicit_mode = str(values.get("NET_IMPACT_RUNTIME_MODE", "")).strip().lower()
    if explicit_mode in {"cloud", "hosted", "website"}:
        return True
    if explicit_mode in {"local", "desktop", "software"}:
        return False
    sharing_mode = str(values.get("STREAMLIT_SHARING_MODE", "")).strip().lower()
    if sharing_mode in {"1", "true", "yes", "on"}:
        return True
    normalized_root = project_root.as_posix().lower().rstrip("/")
    return normalized_root == "/mount/src" or normalized_root.startswith("/mount/src/")


def prefer_existing_variable_values(options: Mapping[str, Any]) -> bool:
    """Map the upload-priority option to the variable-pool merge behavior."""
    return not bool(options.get("use_uploaded_local_data_first", True))


def build_results_archive(project_root: Path = PROJECT_ROOT) -> tuple[bytes, list[str]]:
    """Build an in-memory ZIP containing generated result artifacts only."""
    root = Path(project_root)
    artifacts: list[tuple[str, Path]] = []
    for directory_name in RESULT_ARTIFACT_DIRECTORIES:
        directory = root / "outputs" / directory_name
        if not directory.exists():
            continue
        for path in directory.rglob("*"):
            if path.is_file():
                artifacts.append((path.relative_to(root).as_posix(), path))
    artifacts.sort(key=lambda item: item[0])
    if not artifacts:
        return b"", []

    archive_buffer = BytesIO()
    with ZipFile(archive_buffer, mode="w", compression=ZIP_DEFLATED) as archive:
        for archive_name, path in artifacts:
            archive.write(path, arcname=archive_name)
    return archive_buffer.getvalue(), [archive_name for archive_name, _ in artifacts]


def localized_text(english: str, chinese: str, language: LanguageCode) -> str:
    """Return text in the selected website language."""
    return chinese if language == "zh" else english


def current_language() -> LanguageCode:
    """Return the language shared by the website UI and AI reports."""
    value = str(st.session_state.get(UI_LANGUAGE_STATE, "zh"))
    return "en" if value == "en" else "zh"


def ui_text(english: str, chinese: str) -> str:
    """Return one UI label in the active website language."""
    return localized_text(english, chinese, current_language())


RUNTIME_TRANSLATIONS = {
    "Data refresh and preparation": "数据更新与准备",
    "refreshing market and geopolitical-risk data": "正在更新市场与地缘政治风险数据",
    "Data refresh completed": "数据更新完成",
    "checking complete core market data freshness": "正在检查核心市场数据新鲜度",
    "Core market data freshness check passed": "核心市场数据新鲜度检查通过",
    "preparing model-ready data": "正在准备模型数据",
    "Model-ready data prepared": "模型数据准备完成",
    "refreshing and aligning the expanded candidate variable pool": "正在更新并对齐扩展候选变量池",
    "Expanded variable pool refreshed and merged": "扩展变量池已更新并合并",
    "Running VMD decomposition review": "正在运行 VMD 分解审查",
    "VMD center-frequency review is ready": "VMD 中心频率审查已就绪",
    "Determining selected-scale extrema and FEVD horizon h": "正在确定所选尺度极值与 FEVD 预测期 h",
    "FEVD horizon h review is ready": "FEVD 预测期 h 审查已就绪",
    "Running final TVP/VAR FEVD contribution": "正在运行最终 TVP/VAR FEVD 贡献分析",
    "No explanatory variable passed the data-quality filter": "没有解释变量通过数据质量筛选",
    "Dropped before": "在进入下一步前已剔除",
    " to ": " 至 ",
    "warning": "警告",
}


def localized_runtime_message(message: str, language: LanguageCode) -> str:
    """Translate common dynamic workflow messages while preserving values and dates."""
    text = str(message)
    if language == "en":
        return text
    for english, chinese in RUNTIME_TRANSLATIONS.items():
        text = text.replace(english, chinese)
    return text


def render_language_switcher() -> None:
    """Render the global Chinese/English website language control."""
    _, language_col = st.columns([0.62, 0.38])
    with language_col:
        st.radio(
            "Language / 语言",
            options=["zh", "en"],
            format_func=lambda value: "中文" if value == "zh" else "English",
            horizontal=True,
            label_visibility="collapsed",
            key=UI_LANGUAGE_STATE,
        )


def configure_page() -> None:
    """Configure global Streamlit page settings."""
    st.set_page_config(
        page_title="Oil Market Net-Impact Analysis | 油市净影响分析",
        layout="wide",
    )


def apply_custom_css() -> None:
    """Apply lightweight professional dashboard styling."""
    st.markdown(
        """
        <style>
        :root {
            --primary-color: #111827;
            --background-color: #FAFAFA;
            --secondary-background-color: #FFFFFF;
            --text-color: #111827;
            --border-color: #D1D5DB;
        }
        html, body, .stApp, [data-testid="stAppViewContainer"] {
            background: #FAFAFA !important;
            color: #111827 !important;
            color-scheme: light !important;
            --text-color: #111827 !important;
            --background-color: #FAFAFA !important;
            --secondary-background-color: #FFFFFF !important;
            --primary-color: #111827 !important;
        }
        .stApp {
            background: #FAFAFA !important;
            color: #111827 !important;
            color-scheme: light !important;
        }
        [data-testid="stHeader"] {
            background: rgba(250, 250, 250, 0.96) !important;
            color: #111827 !important;
        }
        .block-container {
            max-width: 1280px;
            padding-top: 2rem;
            padding-bottom: 3rem;
            color: #111827;
        }
        h1, h2, h3, h4, h5, h6,
        p, label, span,
        [data-testid="stMarkdownContainer"],
        [data-testid="stMarkdownContainer"] p,
        [data-testid="stMarkdownContainer"] span {
            color: #111827;
        }
        [data-testid="stSidebar"] {
            background-color: #F5F5F5 !important;
            border-right: 1px solid #D1D5DB;
        }
        [data-testid="stSidebar"] * {
            color: #111827 !important;
            opacity: 1 !important;
        }
        [data-testid="stSidebar"] label,
        [data-testid="stSidebar"] p,
        [data-testid="stSidebar"] span {
            color: #111827 !important;
        }
        [data-testid="stSidebar"] [data-testid="stMetric"] {
            background: #FFFFFF !important;
            border: 1px solid #D1D5DB !important;
            box-shadow: none !important;
        }
        [data-testid="stSidebar"] div[data-baseweb="input"],
        [data-testid="stSidebar"] div[data-baseweb="select"],
        [data-testid="stSidebar"] input,
        [data-testid="stSidebar"] textarea {
            background: #FFFFFF !important;
            color: #111827 !important;
            border-color: #D1D5DB !important;
            -webkit-text-fill-color: #111827 !important;
        }
        input::placeholder,
        textarea::placeholder {
            color: #6B7280 !important;
            opacity: 1 !important;
        }
        [data-testid="stSidebar"] div[data-baseweb="input"] *,
        [data-testid="stSidebar"] div[data-baseweb="select"] *,
        [data-testid="stSidebar"] [role="button"] {
            background: #FFFFFF !important;
            color: #111827 !important;
            -webkit-text-fill-color: #111827 !important;
        }
        [data-testid="stSidebar"] [data-baseweb="slider"] span,
        [data-testid="stSidebar"] [data-baseweb="slider"] div {
            color: #111827 !important;
        }
        .dashboard-header {
            border: 1px solid #D1D5DB;
            border-radius: 12px;
            padding: 1.4rem 1.6rem;
            margin-bottom: 1.2rem;
            background: #FFFFFF;
        }
        .dashboard-header h1 {
            margin: 0 0 0.45rem 0;
            color: #111827;
            letter-spacing: 0;
        }
        .dashboard-subtitle {
            margin: 0;
            color: #4B5563;
            font-size: 1rem;
            line-height: 1.5;
        }
        .risk-note {
            margin-top: 0.75rem;
            color: #6B7280;
            font-size: 0.9rem;
        }
        .stTabs [data-baseweb="tab-list"] {
            gap: 0.5rem;
            border-bottom: 1px solid #E5E7EB;
        }
        .stTabs [data-baseweb="tab"] {
            color: #374151 !important;
            opacity: 1 !important;
            font-weight: 600;
            padding: 0.75rem 0.25rem;
        }
        .stTabs [data-baseweb="tab"] p,
        .stTabs [data-baseweb="tab"] span {
            color: #374151 !important;
            opacity: 1 !important;
        }
        .stTabs [aria-selected="true"] {
            color: #111827 !important;
            border-bottom-color: #6B7280 !important;
        }
        .stTabs [aria-selected="true"] p,
        .stTabs [aria-selected="true"] span {
            color: #111827 !important;
        }
        .stTabs [data-baseweb="tab-highlight"] {
            background-color: #6B7280 !important;
        }
        div[data-testid="stMetric"] {
            background: #FFFFFF !important;
            border: 1px solid #D1D5DB !important;
            border-radius: 12px !important;
            padding: 1rem 1.1rem !important;
            color: #111827 !important;
            box-shadow: none !important;
            overflow: visible !important;
        }
        div[data-testid="stMetric"] * {
            opacity: 1 !important;
        }
        div[data-testid="stMetricLabel"],
        div[data-testid="stMetricLabel"] p,
        div[data-testid="stMetricLabel"] span {
            color: #4B5563 !important;
            font-weight: 600 !important;
        }
        div[data-testid="stMetricValue"],
        div[data-testid="stMetricValue"] div,
        div[data-testid="stMetricValue"] span {
            color: #111827 !important;
            font-size: clamp(1.25rem, 2vw, 1.85rem) !important;
            line-height: 1.2 !important;
            white-space: normal !important;
            overflow-wrap: anywhere !important;
            text-overflow: clip !important;
        }
        div[data-testid="stVerticalBlockBorderWrapper"] {
            background: #FFFFFF !important;
            border: 1px solid #E5E7EB !important;
            border-radius: 12px !important;
            padding: 1rem 1.25rem !important;
            color: #111827 !important;
        }
        div[data-testid="stVerticalBlockBorderWrapper"] * {
            color: inherit;
            opacity: 1;
        }
        [data-testid="stDataFrame"],
        [data-testid="stTable"] {
            border: 1px solid #E5E7EB !important;
            border-radius: 10px !important;
            overflow: hidden !important;
            background: #FFFFFF !important;
            color: #111827 !important;
            --text-color: #111827 !important;
            --background-color: #FFFFFF !important;
            --secondary-background-color: #F5F5F5 !important;
        }
        [data-testid="stDataFrame"] *,
        [data-testid="stTable"] * {
            color: #111827 !important;
            opacity: 1 !important;
        }
        .stDataFrame div,
        .stTable div {
            color: #111827 !important;
        }
        div[data-testid="stTable"] div,
        div[data-testid="stTable"] span,
        div[data-testid="stTable"] [role="table"],
        div[data-testid="stTable"] [role="row"],
        div[data-testid="stTable"] [role="columnheader"],
        div[data-testid="stTable"] [role="cell"] {
            background: #FFFFFF !important;
            background-color: #FFFFFF !important;
            background-image: none !important;
            color: #111827 !important;
            -webkit-text-fill-color: #111827 !important;
            border-color: #E5E7EB !important;
            opacity: 1 !important;
        }
        div[data-testid="stExpander"],
        div[data-testid="stExpander"] details,
        div[data-testid="stExpander"] summary,
        div[data-testid="stExpander"] summary *,
        div[data-testid="stExpanderDetails"] {
            background: #FFFFFF !important;
            background-color: #FFFFFF !important;
            background-image: none !important;
            color: #111827 !important;
            -webkit-text-fill-color: #111827 !important;
            border-color: #D1D5DB !important;
            opacity: 1 !important;
            text-shadow: none !important;
        }
        div[data-testid="stExpander"] {
            border: 1px solid #D1D5DB !important;
            border-radius: 10px !important;
            overflow: hidden !important;
        }
        div[data-testid="stExpanderDetails"] > div,
        div[data-testid="stExpander"] [data-testid="stMarkdownContainer"],
        div[data-testid="stExpander"] [data-testid="stMarkdownContainer"] * {
            background: transparent !important;
            color: #111827 !important;
            -webkit-text-fill-color: #111827 !important;
            opacity: 1 !important;
            text-shadow: none !important;
        }
        div[data-testid="stDownloadButton"] button,
        div[data-testid="stButton"] button,
        .stButton > button {
            border-radius: 8px !important;
            border: 1px solid #D1D5DB !important;
            background: #FFFFFF !important;
            color: #111827 !important;
            font-weight: 600 !important;
            opacity: 1 !important;
        }
        div[data-testid="stDownloadButton"] button *,
        div[data-testid="stButton"] button *,
        .stButton > button * {
            color: inherit !important;
            opacity: 1 !important;
        }
        div[data-testid="stDownloadButton"] button:hover,
        div[data-testid="stButton"] button:hover,
        .stButton > button:hover {
            border-color: #6B7280 !important;
            background: #F5F5F5 !important;
            color: #111827 !important;
        }
        div[data-testid="stDownloadButton"] button:focus,
        div[data-testid="stDownloadButton"] button:active,
        div[data-testid="stButton"] button:focus,
        div[data-testid="stButton"] button:active,
        .stButton > button:focus,
        .stButton > button:active {
            border-color: #111827 !important;
            outline-color: #111827 !important;
            box-shadow: 0 0 0 1px #111827 !important;
        }
        div[data-testid="stButton"] button[kind="primary"],
        .stButton > button[kind="primary"] {
            background: #FFFFFF !important;
            border-color: #9CA3AF !important;
            color: #111827 !important;
            box-shadow: none !important;
        }
        div[data-testid="stButton"] button[kind="primary"] *,
        .stButton > button[kind="primary"] * {
            color: #111827 !important;
            -webkit-text-fill-color: #111827 !important;
        }
        div[data-testid="stNumberInput"] {
            color: #111827 !important;
        }
        div[data-testid="stSlider"],
        div[data-testid="stSlider"] *,
        div[data-baseweb="slider"],
        div[data-baseweb="slider"] * {
            color: #111827 !important;
            -webkit-text-fill-color: #111827 !important;
            opacity: 1 !important;
        }
        div[data-baseweb="slider"] [role="slider"] {
            background: #FFFFFF !important;
            border: 2px solid #6B7280 !important;
            box-shadow: 0 0 0 2px #FFFFFF !important;
        }
        div[data-baseweb="slider"] div {
            border-color: #D1D5DB !important;
        }
        div[data-baseweb="slider"] div[style*="background"] {
            background: #D1D5DB !important;
        }
        div[data-testid="stSlider"] div[data-baseweb="slider"] div {
            background-image: none !important;
        }
        div[data-testid="stSlider"] div[data-baseweb="slider"] div:empty,
        div[data-testid="stSlider"] div[data-baseweb="slider"] div:not([role="slider"]):not(:has([role="slider"])) {
            background-color: #E5E7EB !important;
            border-color: #E5E7EB !important;
        }
        div[data-testid="stSlider"] span:empty,
        div[data-baseweb="slider"] span:empty {
            background-color: #D1D5DB !important;
            border-color: #D1D5DB !important;
        }
        div[data-testid="stSlider"] [role="slider"],
        div[data-baseweb="slider"] [role="slider"],
        div[data-testid="stSlider"] [role="slider"] *,
        div[data-baseweb="slider"] [role="slider"] * {
            background-color: #FFFFFF !important;
            border-color: #6B7280 !important;
        }
        div[data-baseweb="slider"] [aria-valuenow],
        div[data-baseweb="slider"] [aria-valuetext] {
            background: #FFFFFF !important;
            color: #111827 !important;
            -webkit-text-fill-color: #111827 !important;
            border: 1px solid #9CA3AF !important;
            box-shadow: 0 1px 2px rgba(17, 24, 39, 0.10) !important;
        }
        div[data-testid="stSlider"] [role="slider"] p,
        div[data-testid="stSlider"] [role="slider"] span,
        div[data-testid="stSlider"] [aria-valuenow] p,
        div[data-testid="stSlider"] [aria-valuenow] span,
        div[data-baseweb="slider"] [role="slider"] p,
        div[data-baseweb="slider"] [role="slider"] span,
        div[data-baseweb="slider"] [aria-valuenow] p,
        div[data-baseweb="slider"] [aria-valuenow] span {
            color: #111827 !important;
            -webkit-text-fill-color: #111827 !important;
            opacity: 1 !important;
        }
        div[data-testid="stDateInput"] {
            color: #111827 !important;
            opacity: 1 !important;
        }
        div[data-testid="stDateInput"] label,
        div[data-testid="stDateInput"] label *,
        div[data-testid="stDateInput"] [data-testid="stWidgetLabel"],
        div[data-testid="stDateInput"] [data-testid="stWidgetLabel"] * {
            background: transparent !important;
            color: #111827 !important;
            -webkit-text-fill-color: #111827 !important;
        }
        div[data-testid="stDateInput"] input,
        div[data-testid="stDateInput"] div[data-baseweb="input"],
        div[data-testid="stDateInput"] div[data-baseweb="input"] * {
            background: #FFFFFF !important;
            color: #111827 !important;
            -webkit-text-fill-color: #111827 !important;
            opacity: 1 !important;
        }
        div[data-testid="stDateInput"] input,
        div[data-testid="stDateInput"] div[data-baseweb="input"] {
            border-color: #D1D5DB !important;
            border-radius: 10px !important;
        }
        div[data-testid="stSelectbox"],
        div[data-testid="stSelectbox"] *,
        div[data-baseweb="select"],
        div[data-baseweb="select"] * {
            background: #FFFFFF !important;
            color: #111827 !important;
            -webkit-text-fill-color: #111827 !important;
            opacity: 1 !important;
        }
        div[data-baseweb="select"] {
            border-color: #D1D5DB !important;
            border-radius: 10px !important;
        }
        div[data-baseweb="select"] svg,
        div[data-baseweb="select"] svg * {
            fill: #111827 !important;
            stroke: #111827 !important;
            color: #111827 !important;
        }
        div[data-testid="stNumberInput"] input {
            background: #FFFFFF !important;
            color: #111827 !important;
            -webkit-text-fill-color: #111827 !important;
            border-color: #D1D5DB !important;
        }
        div[data-testid="stTextInput"] {
            color: #111827 !important;
            opacity: 1 !important;
        }
        div[data-testid="stTextInput"] label,
        div[data-testid="stTextInput"] label *,
        div[data-testid="stTextInput"] [data-testid="stWidgetLabel"],
        div[data-testid="stTextInput"] [data-testid="stWidgetLabel"] * {
            background: transparent !important;
            color: #111827 !important;
            -webkit-text-fill-color: #111827 !important;
        }
        div[data-testid="stTextInput"] input,
        div[data-testid="stTextInput"] div[data-baseweb="input"],
        div[data-testid="stTextInput"] div[data-baseweb="input"] * {
            background: #FFFFFF !important;
            color: #111827 !important;
            -webkit-text-fill-color: #111827 !important;
            opacity: 1 !important;
        }
        div[data-testid="stTextInput"] input {
            border-color: #D1D5DB !important;
            border-radius: 10px !important;
        }
        div[data-testid="stCheckbox"] label,
        div[data-testid="stCheckbox"] label *,
        div[data-testid="stCheckbox"] span:empty {
            color: #111827 !important;
            -webkit-text-fill-color: #111827 !important;
            border-color: #D1D5DB !important;
        }
        div[data-testid="stCheckbox"] span:empty {
            background: #FFFFFF !important;
        }
        div[data-testid="stCheckbox"] label[data-baseweb="checkbox"]:has(input:checked) > span:first-child {
            background: #F3F4F6 !important;
            border-color: #6B7280 !important;
            color: #111827 !important;
        }
        div[data-testid="stCheckbox"] label[data-baseweb="checkbox"]:has(input:checked) > span:first-child *,
        div[data-testid="stCheckbox"] label[data-baseweb="checkbox"]:has(input:checked) svg,
        div[data-testid="stCheckbox"] label[data-baseweb="checkbox"]:has(input:checked) svg * {
            color: #111827 !important;
            fill: #111827 !important;
            stroke: #111827 !important;
        }
        div[data-testid="stCheckbox"] input + div,
        div[data-testid="stCheckbox"] input + div *,
        div[data-testid="stCheckbox"] [data-testid="stWidgetLabel"],
        div[data-testid="stCheckbox"] [data-testid="stWidgetLabel"] * {
            background: transparent !important;
            color: #111827 !important;
            -webkit-text-fill-color: #111827 !important;
        }
        div[data-testid="stNumberInput"] button,
        div[data-testid="stNumberInput"] button *,
        div[data-testid="stNumberInput"] button[kind="secondary"],
        div[data-testid="stNumberInput"] button[kind="secondary"] *,
        div[data-testid="stNumberInput"] svg,
        div[data-testid="stNumberInput"] svg *,
        button[kind="secondary"][aria-label*="Increment"],
        button[kind="secondary"][aria-label*="Increment"] *,
        button[kind="secondary"][aria-label*="Decrement"],
        button[kind="secondary"][aria-label*="Decrement"] * {
            background: #FFFFFF !important;
            background-color: #FFFFFF !important;
            color: #111827 !important;
            -webkit-text-fill-color: #111827 !important;
            fill: #111827 !important;
            stroke: #111827 !important;
            border-color: #D1D5DB !important;
            opacity: 1 !important;
        }
        div[data-testid="stNumberInput"] button:hover,
        div[data-testid="stNumberInput"] button:hover *,
        button[kind="secondary"][aria-label*="Increment"]:hover,
        button[kind="secondary"][aria-label*="Increment"]:hover *,
        button[kind="secondary"][aria-label*="Decrement"]:hover,
        button[kind="secondary"][aria-label*="Decrement"]:hover * {
            background: #F5F5F5 !important;
            background-color: #F5F5F5 !important;
            color: #111827 !important;
            -webkit-text-fill-color: #111827 !important;
            fill: #111827 !important;
            stroke: #111827 !important;
        }
        div[data-testid="stNumberInput"] button:disabled,
        div[data-testid="stNumberInput"] button:disabled *,
        button[kind="secondary"][aria-label*="Increment"]:disabled,
        button[kind="secondary"][aria-label*="Increment"]:disabled *,
        button[kind="secondary"][aria-label*="Decrement"]:disabled,
        button[kind="secondary"][aria-label*="Decrement"]:disabled * {
            background: #FAFAFA !important;
            background-color: #FAFAFA !important;
            color: #9CA3AF !important;
            -webkit-text-fill-color: #9CA3AF !important;
            fill: #9CA3AF !important;
            stroke: #9CA3AF !important;
            opacity: 1 !important;
        }
        div[data-baseweb="notification"] {
            opacity: 1 !important;
            border-radius: 10px !important;
            background: #FFFFFF !important;
            border: 1px solid #D1D5DB !important;
        }
        div[data-testid="stAlert"] {
            border-radius: 10px !important;
            border: 1px solid #D1D5DB !important;
            background: #FFFFFF !important;
        }
        div[data-testid="stAlert"] * {
            color: #111827 !important;
            opacity: 1 !important;
        }
        div[data-testid="stCaptionContainer"],
        div[data-testid="stCaptionContainer"] * {
            color: #4B5563 !important;
            opacity: 1 !important;
        }
        div[data-baseweb="popover"],
        div[data-baseweb="menu"] {
            background: #FFFFFF !important;
            color: #111827 !important;
            border: 1px solid #D1D5DB !important;
        }
        div[data-baseweb="popover"] *,
        div[data-baseweb="menu"] * {
            color: #111827 !important;
            opacity: 1 !important;
        }
        div[data-baseweb="popover"] {
            z-index: 999999 !important;
        }
        div[data-baseweb="popover"] > div {
            background: #FFFFFF !important;
            color: #111827 !important;
            border: 1px solid #D1D5DB !important;
            border-radius: 12px !important;
            box-shadow: 0 18px 45px rgba(15, 23, 42, 0.18) !important;
        }
        div[data-baseweb="popover"] div[data-baseweb="calendar"],
        div[data-baseweb="calendar"] {
            background: #FFFFFF !important;
            color: #111827 !important;
            border: 1px solid #D1D5DB !important;
            border-radius: 12px !important;
            overflow: hidden !important;
        }
        div[data-baseweb="popover"] div[data-baseweb="calendar"] *,
        div[data-baseweb="calendar"] * {
            color: #111827 !important;
            opacity: 1 !important;
            text-shadow: none !important;
        }
        div[data-baseweb="popover"] div[data-baseweb="calendar"] > div,
        div[data-baseweb="calendar"] > div {
            background: #FFFFFF !important;
            color: #111827 !important;
        }
        div[data-baseweb="popover"] div[data-baseweb="calendar"] button,
        div[data-baseweb="calendar"] button,
        div[data-baseweb="popover"] div[data-baseweb="calendar"] [role="button"],
        div[data-baseweb="calendar"] [role="button"] {
            background: transparent !important;
            color: #111827 !important;
            border-color: transparent !important;
            -webkit-text-fill-color: #111827 !important;
            opacity: 1 !important;
        }
        div[data-baseweb="popover"] div[data-baseweb="calendar"] button svg,
        div[data-baseweb="calendar"] button svg,
        div[data-baseweb="popover"] div[data-baseweb="calendar"] [role="button"] svg,
        div[data-baseweb="calendar"] [role="button"] svg {
            fill: #111827 !important;
            color: #111827 !important;
            stroke: #111827 !important;
            opacity: 1 !important;
        }
        div[data-baseweb="popover"] div[data-baseweb="calendar"] [role="grid"],
        div[data-baseweb="calendar"] [role="grid"],
        div[data-baseweb="popover"] div[data-baseweb="calendar"] [role="row"],
        div[data-baseweb="calendar"] [role="row"],
        div[data-baseweb="popover"] div[data-baseweb="calendar"] [role="columnheader"],
        div[data-baseweb="calendar"] [role="columnheader"],
        div[data-baseweb="popover"] div[data-baseweb="calendar"] [role="gridcell"],
        div[data-baseweb="calendar"] [role="gridcell"] {
            background: #FFFFFF !important;
            color: #111827 !important;
            opacity: 1 !important;
        }
        div[data-baseweb="popover"] div[data-baseweb="calendar"] [role="columnheader"],
        div[data-baseweb="calendar"] [role="columnheader"] {
            color: #4B5563 !important;
            font-weight: 700 !important;
        }
        div[data-baseweb="popover"] div[data-baseweb="calendar"] [role="gridcell"] button,
        div[data-baseweb="calendar"] [role="gridcell"] button {
            color: #111827 !important;
            -webkit-text-fill-color: #111827 !important;
            border-radius: 999px !important;
        }
        div[data-baseweb="popover"] div[data-baseweb="calendar"] [role="gridcell"] button:hover,
        div[data-baseweb="calendar"] [role="gridcell"] button:hover,
        div[data-baseweb="popover"] div[data-baseweb="calendar"] [role="gridcell"]:hover,
        div[data-baseweb="calendar"] [role="gridcell"]:hover {
            background: #F5F5F5 !important;
            color: #111827 !important;
            -webkit-text-fill-color: #111827 !important;
        }
        div[data-baseweb="popover"] div[data-baseweb="calendar"] [aria-selected="true"],
        div[data-baseweb="calendar"] [aria-selected="true"],
        div[data-baseweb="popover"] div[data-baseweb="calendar"] button[aria-selected="true"],
        div[data-baseweb="calendar"] button[aria-selected="true"] {
            background: #F3F4F6 !important;
            color: #111827 !important;
            -webkit-text-fill-color: #111827 !important;
            border-color: #9CA3AF !important;
        }
        div[data-baseweb="popover"] div[data-baseweb="calendar"] [aria-selected="true"] *,
        div[data-baseweb="calendar"] [aria-selected="true"] * {
            color: #111827 !important;
            -webkit-text-fill-color: #111827 !important;
        }
        div[data-baseweb="popover"] div[data-baseweb="calendar"] [aria-disabled="true"],
        div[data-baseweb="calendar"] [aria-disabled="true"],
        div[data-baseweb="popover"] div[data-baseweb="calendar"] button:disabled,
        div[data-baseweb="calendar"] button:disabled {
            background: #FAFAFA !important;
            color: #9CA3AF !important;
            -webkit-text-fill-color: #9CA3AF !important;
            opacity: 1 !important;
        }
        div[data-baseweb="popover"] div[data-baseweb="calendar"] [aria-disabled="true"] *,
        div[data-baseweb="calendar"] [aria-disabled="true"] * {
            color: #9CA3AF !important;
            -webkit-text-fill-color: #9CA3AF !important;
        }
        body div[data-baseweb="popover"],
        body div[data-baseweb="popover"] > div,
        body div[data-baseweb="popover"] [data-baseweb="calendar"],
        body div[data-baseweb="popover"] [role="application"][aria-roledescription="datepicker"],
        body div[data-baseweb="popover"] [aria-label="Calendar."] {
            background: #FFFFFF !important;
            color: #111827 !important;
            border-color: #D1D5DB !important;
            z-index: 999999 !important;
            box-shadow: 0 18px 44px rgba(15, 23, 42, 0.18) !important;
        }
        body div[data-baseweb="popover"] [data-baseweb="calendar"],
        body div[data-baseweb="popover"] [data-baseweb="calendar"] *,
        body div[data-baseweb="calendar"],
        body div[data-baseweb="calendar"] *,
        body div[data-baseweb="calendar"] header,
        body div[data-baseweb="calendar"] div,
        body div[data-baseweb="calendar"] button,
        body div[data-baseweb="calendar"] button *,
        body div[data-baseweb="calendar"] [role="button"],
        body div[data-baseweb="calendar"] [role="grid"],
        body div[data-baseweb="calendar"] [role="grid"] *,
        body div[data-baseweb="calendar"] [role="row"],
        body div[data-baseweb="calendar"] [role="row"] *,
        body div[data-baseweb="calendar"] [role="columnheader"],
        body div[data-baseweb="calendar"] [role="gridcell"],
        body div[data-baseweb="calendar"] [role="gridcell"] *,
        body div[data-baseweb="calendar"] [role="presentation"],
        body div[data-baseweb="calendar"] [role="presentation"] * {
            background-color: #FFFFFF !important;
            background-image: none !important;
            color: #111827 !important;
            -webkit-text-fill-color: #111827 !important;
            border-color: transparent !important;
            opacity: 1 !important;
            text-shadow: none !important;
        }
        body div[data-baseweb="calendar"] > div:first-child,
        body div[data-baseweb="calendar"] > div:first-child *,
        body div[data-baseweb="calendar"] header,
        body div[data-baseweb="calendar"] header *,
        body div[data-baseweb="calendar"] button[aria-label="Previous month."],
        body div[data-baseweb="calendar"] button[aria-label="Next month."],
        body div[data-baseweb="calendar"] button[aria-label="Previous month."] *,
        body div[data-baseweb="calendar"] button[aria-label="Next month."] * {
            background: #FAFAFA !important;
            color: #111827 !important;
            -webkit-text-fill-color: #111827 !important;
            fill: #111827 !important;
            stroke: #111827 !important;
            opacity: 1 !important;
        }
        body div[data-baseweb="calendar"] button,
        body div[data-baseweb="calendar"] button span,
        body div[data-baseweb="calendar"] button div,
        body div[data-baseweb="calendar"] div[role="button"],
        body div[data-baseweb="calendar"] div[role="button"] * {
            background: transparent !important;
            color: #111827 !important;
            -webkit-text-fill-color: #111827 !important;
            opacity: 1 !important;
        }
        body div[data-baseweb="calendar"] svg,
        body div[data-baseweb="calendar"] svg *,
        body div[data-baseweb="calendar"] path {
            color: #111827 !important;
            fill: #111827 !important;
            stroke: #111827 !important;
            opacity: 1 !important;
        }
        body div[data-baseweb="calendar"] [role="columnheader"],
        body div[data-baseweb="calendar"] [role="columnheader"] *,
        body div[data-baseweb="calendar"] [aria-label="Calendar."] [role="columnheader"] {
            background: #FAFAFA !important;
            color: #374151 !important;
            -webkit-text-fill-color: #374151 !important;
            font-weight: 700 !important;
        }
        body div[data-baseweb="calendar"] [role="gridcell"]:hover,
        body div[data-baseweb="calendar"] [role="gridcell"]:hover *,
        body div[data-baseweb="calendar"] [role="gridcell"] button:hover,
        body div[data-baseweb="calendar"] [role="gridcell"] button:hover * {
            background: #F3F4F6 !important;
            color: #111827 !important;
            -webkit-text-fill-color: #111827 !important;
        }
        body div[data-baseweb="calendar"] [aria-label^="Selected"],
        body div[data-baseweb="calendar"] [aria-label^="Selected"] *,
        body div[data-baseweb="calendar"] [aria-selected="true"],
        body div[data-baseweb="calendar"] [aria-selected="true"] *,
        body div[data-baseweb="calendar"] [data-selected="true"],
        body div[data-baseweb="calendar"] [data-selected="true"] *,
        body div[data-baseweb="calendar"] [data-highlighted="true"],
        body div[data-baseweb="calendar"] [data-highlighted="true"] *,
        body div[data-baseweb="calendar"] button[aria-selected="true"],
        body div[data-baseweb="calendar"] button[aria-selected="true"] * {
            background: #F3F4F6 !important;
            background-color: #F3F4F6 !important;
            color: #111827 !important;
            -webkit-text-fill-color: #111827 !important;
            border-color: #9CA3AF !important;
            fill: #111827 !important;
            stroke: #111827 !important;
        }
        body div[data-baseweb="calendar"] [aria-disabled="true"],
        body div[data-baseweb="calendar"] [aria-disabled="true"] *,
        body div[data-baseweb="calendar"] button:disabled,
        body div[data-baseweb="calendar"] button:disabled *,
        body div[data-baseweb="calendar"] [aria-label*="not available"],
        body div[data-baseweb="calendar"] [aria-label*="not available"] * {
            background: #FAFAFA !important;
            color: #9CA3AF !important;
            -webkit-text-fill-color: #9CA3AF !important;
            opacity: 1 !important;
        }
        body div[data-baseweb="popover"] div[data-baseweb="select"],
        body div[data-baseweb="popover"] div[data-baseweb="select"] *,
        body div[data-baseweb="popover"] div[data-baseweb="menu"],
        body div[data-baseweb="popover"] div[data-baseweb="menu"] * {
            background: #FFFFFF !important;
            color: #111827 !important;
            -webkit-text-fill-color: #111827 !important;
            border-color: #D1D5DB !important;
            opacity: 1 !important;
        }
        body div[data-baseweb="popover"] div[data-baseweb="select"],
        body div[data-baseweb="popover"] div[data-baseweb="select"] *,
        body div[data-baseweb="popover"] div[data-baseweb="menu"],
        body div[data-baseweb="popover"] div[data-baseweb="menu"] *,
        body div[data-baseweb="popover"] ul[role="listbox"],
        body div[data-baseweb="popover"] ul[role="listbox"] *,
        body div[data-baseweb="popover"] li[role="option"],
        body div[data-baseweb="popover"] li[role="option"] *,
        body div[data-baseweb="popover"] div[role="listbox"],
        body div[data-baseweb="popover"] div[role="listbox"] *,
        body div[data-baseweb="popover"] div[role="option"],
        body div[data-baseweb="popover"] div[role="option"] *,
        body div[data-baseweb="menu"],
        body div[data-baseweb="menu"] *,
        body ul[role="listbox"],
        body ul[role="listbox"] *,
        body li[role="option"],
        body li[role="option"] *,
        body div[role="listbox"],
        body div[role="listbox"] *,
        body div[role="option"],
        body div[role="option"] * {
            background: #FFFFFF !important;
            background-color: #FFFFFF !important;
            background-image: none !important;
            color: #111827 !important;
            -webkit-text-fill-color: #111827 !important;
            border-color: #D1D5DB !important;
            opacity: 1 !important;
            text-shadow: none !important;
        }
        body div[data-baseweb="popover"] li[role="option"]:hover,
        body div[data-baseweb="popover"] li[role="option"]:hover *,
        body div[data-baseweb="popover"] div[role="option"]:hover,
        body div[data-baseweb="popover"] div[role="option"]:hover *,
        body li[role="option"]:hover,
        body li[role="option"]:hover *,
        body div[role="option"]:hover,
        body div[role="option"]:hover * {
            background: #F5F5F5 !important;
            background-color: #F5F5F5 !important;
            color: #111827 !important;
            -webkit-text-fill-color: #111827 !important;
        }
        body div[data-baseweb="popover"] li[role="option"][aria-selected="true"],
        body div[data-baseweb="popover"] li[role="option"][aria-selected="true"] *,
        body div[data-baseweb="popover"] div[role="option"][aria-selected="true"],
        body div[data-baseweb="popover"] div[role="option"][aria-selected="true"] *,
        body li[role="option"][aria-selected="true"],
        body li[role="option"][aria-selected="true"] *,
        body div[role="option"][aria-selected="true"],
        body div[role="option"][aria-selected="true"] * {
            background: #F3F4F6 !important;
            background-color: #F3F4F6 !important;
            color: #111827 !important;
            -webkit-text-fill-color: #111827 !important;
            font-weight: 700 !important;
        }
        body div[data-baseweb="popover"] li[role="option"][aria-disabled="true"],
        body div[data-baseweb="popover"] li[role="option"][aria-disabled="true"] *,
        body div[data-baseweb="popover"] div[role="option"][aria-disabled="true"],
        body div[data-baseweb="popover"] div[role="option"][aria-disabled="true"] *,
        body li[role="option"][aria-disabled="true"],
        body li[role="option"][aria-disabled="true"] *,
        body div[role="option"][aria-disabled="true"],
        body div[role="option"][aria-disabled="true"] * {
            background: #FAFAFA !important;
            background-color: #FAFAFA !important;
            color: #9CA3AF !important;
            -webkit-text-fill-color: #9CA3AF !important;
            opacity: 1 !important;
        }
        body div[data-baseweb="calendar"] [aria-label^="Selected."],
        body div[data-baseweb="calendar"] [aria-label^="Selected."] *,
        body div[data-baseweb="calendar"] [aria-selected="true"],
        body div[data-baseweb="calendar"] [aria-selected="true"] *,
        body div[data-baseweb="calendar"] [data-selected="true"],
        body div[data-baseweb="calendar"] [data-selected="true"] *,
        body div[data-baseweb="calendar"] [data-highlighted="true"],
        body div[data-baseweb="calendar"] [data-highlighted="true"] *,
        body div[data-baseweb="calendar"] [role="gridcell"][aria-label^="Selected."],
        body div[data-baseweb="calendar"] [role="gridcell"][aria-label^="Selected."] * {
            background: #F3F4F6 !important;
            background-color: #F3F4F6 !important;
            color: #111827 !important;
            -webkit-text-fill-color: #111827 !important;
            border-color: #9CA3AF !important;
            fill: #111827 !important;
            stroke: #111827 !important;
            opacity: 1 !important;
        }
        body div[data-baseweb="calendar"] [role="gridcell"][aria-label^="Selected."] {
            border-radius: 999px !important;
            overflow: hidden !important;
        }
        div[data-testid="stMultiSelect"] div[data-baseweb="select"] {
            min-height: 3.45rem !important;
            padding: 0.42rem 0.5rem !important;
            align-items: center !important;
            background: rgba(255, 255, 253, 0.96) !important;
            border: 1px solid rgba(35, 35, 32, 0.13) !important;
            border-radius: 14px !important;
            box-shadow: 0 4px 14px rgba(29, 29, 27, 0.035) !important;
        }
        div[data-testid="stMultiSelect"] div[data-baseweb="tag"] {
            max-width: 18rem !important;
            min-height: 2.05rem !important;
            margin: 0.16rem 0.2rem !important;
            padding-left: 0.18rem !important;
            background: #EEF2F0 !important;
            border: 1px solid #D9E1DD !important;
            border-radius: 9px !important;
            color: #111827 !important;
            box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.72) !important;
        }
        div[data-testid="stMultiSelect"] div[data-baseweb="tag"] span,
        div[data-testid="stMultiSelect"] div[data-baseweb="tag"] * {
            max-width: 15rem !important;
            white-space: nowrap !important;
            overflow: hidden !important;
            text-overflow: ellipsis !important;
            color: #111827 !important;
            -webkit-text-fill-color: #111827 !important;
            font-weight: 600 !important;
        }
        div[data-testid="stMultiSelect"] label,
        div[data-testid="stMultiSelect"] label * {
            color: #111827 !important;
            font-weight: 650 !important;
        }
        body div[data-baseweb="popover"] [role="listbox"] {
            padding: 0.45rem !important;
            background: rgba(255, 255, 253, 0.98) !important;
            border: 1px solid rgba(35, 35, 32, 0.10) !important;
            border-radius: 14px !important;
            box-shadow: 0 18px 45px rgba(29, 29, 27, 0.14) !important;
        }
        body div[data-baseweb="popover"] div[role="option"] {
            min-height: 2.8rem !important;
            margin: 0.12rem 0 !important;
            padding: 0.65rem 0.8rem !important;
            border-radius: 9px !important;
            color: #292925 !important;
            transition: background 120ms ease, transform 120ms ease !important;
        }
        body div[data-baseweb="popover"] div[role="option"]:hover {
            background: #F1F3F1 !important;
            transform: translateX(2px);
        }
        body div[data-baseweb="popover"] div[role="option"][aria-selected="true"] {
            background: #E8EFEB !important;
            color: #18211D !important;
            font-weight: 650 !important;
        }
        .variable-selection-summary {
            display: flex;
            align-items: center;
            gap: 0.7rem;
            margin: 0.45rem 0 0.8rem;
            padding: 0.78rem 0.95rem;
            background: rgba(238, 242, 240, 0.78);
            border: 1px solid #D9E1DD;
            border-radius: 12px;
            color: #30332F;
        }
        .variable-selection-summary::before {
            content: "✓";
            display: inline-grid;
            place-items: center;
            width: 1.55rem;
            height: 1.55rem;
            flex: 0 0 1.55rem;
            border-radius: 999px;
            background: #273B32;
            color: #FFFFFF;
            font-size: 0.78rem;
            font-weight: 800;
        }
        .variable-selection-summary strong {
            color: #20221F !important;
            font-weight: 680;
        }
        .variable-selection-summary span {
            color: #6B6D68 !important;
            font-size: 0.88rem;
        }
        .top-tool-menu {
            display: flex;
            justify-content: flex-end;
            align-items: flex-start;
            padding-top: 0.15rem;
        }
        .api-status-badge {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            border-radius: 999px;
            padding: 0.2rem 0.55rem;
            font-size: 0.8rem;
            font-weight: 700;
            margin-bottom: 0.45rem;
            border: 1px solid #D1D5DB;
            color: #111827;
            background: #FFFFFF;
        }
        .api-status-badge.missing {
            color: #991B1B;
            background: #FEE2E2;
            border-color: #FCA5A5;
        }
        .api-status-badge.configured {
            color: #14532D;
            background: #DCFCE7;
            border-color: #86EFAC;
        }
        .api-status-badge.warning {
            color: #854D0E;
            background: #FEF3C7;
            border-color: #FCD34D;
        }
        body div[data-baseweb="popover"] div[data-testid="stButton"] button[kind="primary"] {
            background: #FEE2E2 !important;
            border-color: #FCA5A5 !important;
            color: #991B1B !important;
        }
        body div[data-baseweb="popover"] div[data-testid="stButton"] button[kind="primary"] * {
            color: #991B1B !important;
            -webkit-text-fill-color: #991B1B !important;
        }
        hr {
            border-color: #E5E7EB;
        }
        /* Codex-inspired workspace layer: quiet neutrals, soft light, precise edges. */
        html, body, .stApp, [data-testid="stAppViewContainer"] {
            background:
                radial-gradient(circle at 80% -8%, rgba(182, 202, 194, 0.24), transparent 30rem),
                radial-gradient(circle at 58% 0%, rgba(214, 205, 224, 0.18), transparent 25rem),
                radial-gradient(circle at 98% 22%, rgba(235, 218, 197, 0.20), transparent 26rem),
                #F7F7F5 !important;
            font-family: "Segoe UI Variable", "SF Pro Display", "PingFang SC", "Microsoft YaHei UI", sans-serif !important;
        }
        [data-testid="stHeader"] {
            background: rgba(247, 247, 245, 0.78) !important;
            backdrop-filter: blur(18px);
            border-bottom: 1px solid rgba(29, 29, 27, 0.06);
        }
        .block-container {
            max-width: 1380px;
            padding-top: 3.1rem;
            padding-bottom: 4rem;
        }
        h1, h2, h3, h4 {
            font-family: "Segoe UI Variable", "SF Pro Display", "PingFang SC", "Microsoft YaHei UI", sans-serif !important;
            letter-spacing: -0.035em;
            color: #20201E !important;
        }
        .dashboard-header {
            position: relative;
            isolation: isolate;
            overflow: hidden;
            min-height: 250px;
            display: flex;
            flex-direction: column;
            justify-content: center;
            background: rgba(255, 255, 253, 0.82) !important;
            border: 1px solid rgba(35, 35, 32, 0.10) !important;
            border-radius: 24px !important;
            box-shadow: 0 22px 55px rgba(28, 31, 28, 0.07) !important;
            padding: 2.4rem 2.7rem !important;
            backdrop-filter: blur(16px);
        }
        .dashboard-header::before {
            content: "";
            position: absolute;
            z-index: -1;
            width: 520px;
            height: 520px;
            right: -130px;
            top: -290px;
            border-radius: 48%;
            background:
                radial-gradient(circle at 30% 35%, rgba(178, 203, 193, 0.60), transparent 43%),
                radial-gradient(circle at 64% 45%, rgba(211, 199, 224, 0.54), transparent 40%),
                radial-gradient(circle at 50% 73%, rgba(236, 215, 190, 0.44), transparent 42%);
            filter: blur(8px);
            opacity: 0.78;
        }
        .dashboard-header::after {
            content: "";
            position: absolute;
            z-index: -1;
            inset: 0;
            background: linear-gradient(110deg, rgba(255, 255, 253, 0.95) 30%, rgba(255, 255, 253, 0.30) 100%);
        }
        .dashboard-header h1 {
            color: #1D1D1B !important;
            font-size: clamp(2.15rem, 3.2vw, 3.55rem);
            line-height: 1.06;
            font-weight: 580;
            max-width: 1020px;
            margin-bottom: 1.1rem;
        }
        .dashboard-header .dashboard-subtitle {
            color: #595954 !important;
            max-width: 940px;
            font-size: 1.02rem;
            line-height: 1.65;
        }
        .dashboard-header .risk-note {
            color: #777772 !important;
            letter-spacing: 0.025em;
            font-size: 0.76rem;
            margin-top: 0.7rem;
        }
        [data-testid="stSidebar"] {
            background: rgba(242, 242, 239, 0.94) !important;
            border-right: 1px solid rgba(35, 35, 32, 0.09) !important;
        }
        [data-testid="stSidebar"] [data-testid="stVerticalBlock"] {
            gap: 0.75rem;
        }
        [data-testid="stVerticalBlockBorderWrapper"] {
            background: rgba(255, 255, 253, 0.80);
            border-color: rgba(35, 35, 32, 0.10) !important;
            border-radius: 16px !important;
            box-shadow: 0 10px 30px rgba(29, 29, 27, 0.035);
            backdrop-filter: blur(12px);
        }
        .stTabs [data-baseweb="tab-list"] {
            gap: 0.2rem;
            width: fit-content;
            padding: 0.24rem;
            background: rgba(232, 232, 228, 0.84);
            border: 1px solid rgba(35, 35, 32, 0.07) !important;
            border-radius: 12px;
        }
        .stTabs [data-baseweb="tab"] {
            min-height: 2.6rem;
            padding: 0.6rem 1.15rem;
            border-radius: 9px;
        }
        .stTabs [aria-selected="true"] {
            background: #FFFFFF !important;
            box-shadow: 0 1px 5px rgba(28, 28, 26, 0.11);
        }
        .stTabs [aria-selected="true"] p,
        .stTabs [aria-selected="true"] span {
            color: #1D1D1B !important;
        }
        div[data-testid="stButton"] button,
        div[data-testid="stDownloadButton"] button {
            border-radius: 10px !important;
            transition: transform 150ms ease, box-shadow 150ms ease, background 150ms ease;
        }
        div[data-testid="stButton"] button[kind="primary"] {
            background: #20201E !important;
            border-color: #20201E !important;
            color: #FFFFFF !important;
            box-shadow: 0 5px 14px rgba(29, 29, 27, 0.14);
        }
        div[data-testid="stButton"] button[kind="primary"] * {
            color: #FFFFFF !important;
            -webkit-text-fill-color: #FFFFFF !important;
        }
        div[data-testid="stButton"] button[kind="primary"]:hover {
            background: #343431 !important;
            border-color: #343431 !important;
            box-shadow: 0 8px 20px rgba(29, 29, 27, 0.18);
            transform: translateY(-1px);
        }
        div[data-baseweb="input"],
        div[data-baseweb="select"] > div,
        [data-baseweb="textarea"] {
            background: rgba(255, 255, 253, 0.92) !important;
            border-color: rgba(35, 35, 32, 0.14) !important;
            border-radius: 10px !important;
        }
        [data-testid="stDataFrame"] {
            border: 1px solid rgba(35, 35, 32, 0.10);
            border-radius: 12px;
            overflow: hidden;
        }
        [data-testid="stRadio"] > div {
            justify-content: flex-end;
            gap: 0.22rem;
            width: fit-content;
            margin-left: auto;
            padding: 0.2rem;
            background: rgba(232, 232, 228, 0.76);
            border-radius: 999px;
        }
        [data-testid="stRadio"] [role="radiogroup"] {
            display: flex !important;
            flex-direction: row !important;
            flex-wrap: nowrap !important;
        }
        [data-testid="stRadio"] label {
            background: transparent;
            border: 0;
            border-radius: 999px;
            padding: 0.34rem 0.72rem;
        }
        [data-testid="stRadio"] label p {
            white-space: nowrap !important;
        }
        [data-testid="stRadio"] label:has(input:checked) {
            background: #FFFFFF;
            box-shadow: 0 1px 5px rgba(29, 29, 27, 0.12);
        }
        hr {
            border-color: rgba(35, 35, 32, 0.09) !important;
        }
        @media (max-width: 760px) {
            .block-container { padding-left: 1rem; padding-right: 1rem; }
            .dashboard-header { min-height: auto; padding: 1.6rem !important; border-radius: 18px !important; }
            .dashboard-header h1 { font-size: 2.35rem; }
            .stTabs [data-baseweb="tab-list"] { width: 100%; }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_main_header() -> None:
    """Render the dashboard header."""
    title = ui_text("Multiscale Net-Impact Analysis System", "多尺度净影响分析系统")
    subtitle = ui_text(
        "A VMD-based EMTV-NEI website for measuring multiscale net impacts.",
        "基于 VMD 的 EMTV-NEI 多尺度净影响分析网站。",
    )
    description = ui_text(
        "The system updates market data, builds the variable pool, runs MRGC screening, selects main response scales, estimates FEVD contribution weights, and reports narrow and broad net impacts.",
        "系统可更新市场数据、构建变量池、执行 MRGC 筛选、选择主要响应尺度、估计 FEVD 贡献权重，并报告狭义与广义净影响。",
    )
    risk_note = ui_text(
        "For academic research demonstration only. Not investment advice.",
        "仅供学术研究演示，不构成投资建议。",
    )
    title_col, tools_col = st.columns([0.94, 0.06])
    with title_col:
        st.markdown(
            f"""
            <div class="dashboard-header">
                <h1>{title}</h1>
                <p class="dashboard-subtitle">{subtitle}</p>
                <p class="dashboard-subtitle">{description}</p>
                <p class="risk-note">{risk_note}</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with tools_col:
        render_top_tool_menu()
    render_workspace_status_messages()


def load_excel_if_exists(path: str | Path, sheet_name: str | None = None) -> pd.DataFrame | None:
    """Load one Excel sheet as a DataFrame if the file exists.

    When sheet_name is None, pandas reads the first sheet and returns a
    DataFrame. Loading every sheet is handled by load_excel_sheets_if_exists.
    """
    path = Path(path)
    if not path.exists():
        return None
    if sheet_name is None:
        try:
            return pd.read_excel(path)
        except Exception as exc:  # noqa: BLE001 - show exact read failure in UI.
            st.error(f"Failed to read Excel file {path}: {safe_exception_text(exc)}")
            return None
    try:
        return pd.read_excel(path, sheet_name=sheet_name)
    except Exception as exc:  # noqa: BLE001 - show exact read failure in UI.
        st.error(f"Failed to read Excel file {path} sheet {sheet_name}: {safe_exception_text(exc)}")
        return None


def load_excel_sheets_if_exists(path: str | Path) -> dict[str, pd.DataFrame] | None:
    """Load all sheets from an Excel workbook if it exists."""
    path = Path(path)
    if not path.exists():
        return None
    try:
        return pd.read_excel(path, sheet_name=None)
    except Exception as exc:  # noqa: BLE001 - show exact read failure in UI.
        st.error(f"Failed to read Excel workbook {path}: {safe_exception_text(exc)}")
        return None


def show_dataframe_or_sheets(data: pd.DataFrame | dict[str, pd.DataFrame]) -> None:
    """Display either a DataFrame or a dict of sheet-name/DataFrame pairs."""
    if isinstance(data, dict):
        for sheet_name, sheet_df in data.items():
            st.subheader(str(sheet_name))
            st.dataframe(sheet_df, use_container_width=True)
        return

    st.dataframe(data, use_container_width=True)


def get_date_range_if_exists(path: str | Path) -> tuple[pd.Timestamp | None, pd.Timestamp | None]:
    """Return min/max Date from an Excel file, or None values if unavailable."""
    data = load_excel_if_exists(path)
    if data is None or "Date" not in data.columns:
        return None, None

    dates = pd.to_datetime(data["Date"], errors="coerce").dropna()
    if dates.empty:
        return None, None
    return dates.min(), dates.max()


def get_complete_market_date_range_if_exists(
    path: str | Path,
    required_columns: list[str] | None = None,
) -> tuple[pd.Timestamp | None, pd.Timestamp | None]:
    """Return min/max dates where all required market columns are available."""
    data = load_excel_if_exists(path)
    if data is None or "Date" not in data.columns:
        return None, None
    required_columns = required_columns or CORE_MARKET_FRESHNESS_COLUMNS
    if any(column not in data.columns for column in required_columns):
        return None, None

    prepared = data.copy()
    prepared["Date"] = pd.to_datetime(prepared["Date"], errors="coerce")
    complete = prepared.dropna(subset=["Date", *required_columns])
    dates = complete["Date"].dropna()
    if dates.empty:
        return None, None
    return dates.min(), dates.max()


def parse_manual_date_text(value: Any) -> tuple[pd.Timestamp | None, str | None, str | None]:
    """Parse manual date input and normalize it to YYYY-MM-DD."""
    text = str(value or "").strip()
    if not text:
        return None, None, "date is empty"
    digits = re.sub(r"\D", "", text)
    if re.fullmatch(r"\d{8}", text) or (len(digits) == 8 and re.fullmatch(r"[\d\s./_-]+", text)):
        year, month, day = int(digits[:4]), int(digits[4:6]), int(digits[6:8])
    else:
        match = re.fullmatch(r"\s*(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})\s*", text)
        if not match:
            return None, None, "use YYYY-MM-DD, YYYY/MM/DD, or YYYYMMDD"
        year, month, day = map(int, match.groups())
    try:
        timestamp = pd.Timestamp(year=year, month=month, day=day).normalize()
    except ValueError:
        return None, None, f"{text} is not a valid calendar date"
    return timestamp, timestamp.strftime("%Y-%m-%d"), None


def sync_picker_to_manual(picker_key: str, manual_key: str) -> None:
    """Keep manual date text aligned with the date picker."""
    timestamp = pd.to_datetime(st.session_state.get(picker_key), errors="coerce")
    if pd.notna(timestamp):
        st.session_state[manual_key] = pd.Timestamp(timestamp).strftime("%Y-%m-%d")


def apply_manual_analysis_dates(
    start_manual_key: str,
    end_manual_key: str,
    start_picker_key: str,
    end_picker_key: str,
    error_key: str,
) -> None:
    """Apply manual date input to the calendar widgets."""
    start_timestamp, start_label, start_error = parse_manual_date_text(st.session_state.get(start_manual_key))
    end_timestamp, end_label, end_error = parse_manual_date_text(st.session_state.get(end_manual_key))
    if start_error or end_error:
        messages = []
        if start_error:
            messages.append(f"Start date: {start_error}.")
        if end_error:
            messages.append(f"End date: {end_error}.")
        st.session_state[error_key] = " ".join(messages)
        return
    if start_timestamp is None or end_timestamp is None or start_label is None or end_label is None:
        st.session_state[error_key] = "Manual dates could not be parsed."
        return
    if start_timestamp > end_timestamp:
        st.session_state[error_key] = "Start date must be on or before end date."
        return
    st.session_state[start_manual_key] = start_label
    st.session_state[end_manual_key] = end_label
    st.session_state[start_picker_key] = start_timestamp.date()
    st.session_state[end_picker_key] = end_timestamp.date()
    st.session_state[error_key] = ""


def show_dataframe_summary(df: pd.DataFrame) -> None:
    """Display basic dataframe summary information."""
    st.write("Columns")
    st.code(", ".join(df.columns.astype(str).tolist()))

    st.write("Missing values")
    st.dataframe(
        df.isna().sum().rename("MissingCount").reset_index().rename(columns={"index": "Column"}),
        use_container_width=True,
    )

    if "Date" in df.columns:
        dates = pd.to_datetime(df["Date"], errors="coerce").dropna()
        if not dates.empty:
            col_start, col_end = st.columns(2)
            col_start.metric("Start date", dates.min().strftime("%Y-%m-%d"))
            col_end.metric("End date", dates.max().strftime("%Y-%m-%d"))


def import_function(module_name: str, function_name: str) -> Callable[..., Any]:
    """Import a function and reload the module if Streamlit has a stale cache."""
    module = importlib.import_module(module_name)
    module = importlib.reload(module)
    if not hasattr(module, function_name):
        raise ImportError(f"cannot import name '{function_name}' from '{module_name}'")
    return getattr(module, function_name)


def safe_exception_text(exc: BaseException) -> str:
    """Return an ASCII-only exception summary for Streamlit messages."""
    message = str(exc).encode("ascii", errors="ignore").decode("ascii").strip()
    message = re.sub(r"\s+", " ", message)
    if message:
        return f"{type(exc).__name__}: {message}"
    return type(exc).__name__


def _safe_project_child(path: str | Path) -> Path:
    """Resolve a path and ensure it stays inside the project workspace."""
    root = PROJECT_ROOT.resolve()
    resolved = Path(path).resolve()
    if resolved == root or not resolved.is_relative_to(root):
        raise ValueError(f"Refusing to clean path outside project workspace: {resolved}")
    return resolved


def _delete_path(path: Path) -> list[str]:
    """Delete one file or directory after workspace-boundary validation."""
    target = _safe_project_child(path)
    if not target.exists():
        return []
    deleted: list[str] = []
    if target.is_dir():
        deleted = [
            str(child.relative_to(PROJECT_ROOT))
            for child in target.rglob("*")
            if child.is_file()
        ]
        shutil.rmtree(target)
        target.mkdir(parents=True, exist_ok=True)
        if not deleted:
            deleted.append(str(target.relative_to(PROJECT_ROOT)) + "/")
    else:
        target.unlink()
        deleted.append(str(target.relative_to(PROJECT_ROOT)))
    return deleted


def _delete_files_in_directory(path: str | Path) -> list[str]:
    """Delete files directly inside a workspace directory, keeping subdirectories."""
    directory = _safe_project_child(path)
    if not directory.exists():
        directory.mkdir(parents=True, exist_ok=True)
        return []
    if not directory.is_dir():
        return _delete_path(directory)
    deleted: list[str] = []
    for child in directory.iterdir():
        if child.is_file():
            deleted.extend(_delete_path(child))
    return deleted


def _api_value_is_filled(value: Any) -> bool:
    """Return whether an API value is a real user-provided value."""
    text = str(value or "").strip()
    if not text:
        return False
    lowered = text.lower()
    placeholder_tokens = {"your_key_here", "your_fred_api_key", "your_eia_api_key", "demo_key"}
    return lowered not in placeholder_tokens


def _looks_like_fred_api_key(api_key: str) -> bool:
    """Return whether a FRED key has the expected public format."""
    text = str(api_key or "").strip()
    return len(text) == 32 and text.isalnum() and text.lower() == text


def validate_fred_api_key(api_key: str) -> dict[str, str]:
    """Validate a saved FRED key without exposing it in the UI."""
    text = str(api_key or "").strip()
    if not _api_value_is_filled(text):
        return {"status": "missing", "message": "FRED_API_KEY is not saved."}
    if not _looks_like_fred_api_key(text):
        return {
            "status": "invalid",
            "message": "FRED_API_KEY has the wrong format. A FRED key should be 32 lower-case alphanumeric characters.",
        }

    cache_key = f"fred:{text}"
    if cache_key in API_VALIDATION_CACHE:
        return API_VALIDATION_CACHE[cache_key]

    try:
        import requests

        response = requests.get(
            "https://api.stlouisfed.org/fred/series",
            params={"series_id": "DGS10", "api_key": text, "file_type": "json"},
            headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json,*/*"},
            timeout=8,
        )
        payload = response.json()
        if response.status_code >= 400 or "error_code" in payload:
            message = str(payload.get("error_message") or response.text or "FRED rejected the key.")
            if "not registered" in message.lower():
                result = {
                    "status": "invalid",
                    "message": "FRED_API_KEY is present, but FRED says it is not registered. Create a new key at fred.stlouisfed.org and save it again.",
                }
            else:
                result = {"status": "invalid", "message": f"FRED rejected the saved key: {message[:220]}"}
        else:
            result = {"status": "valid", "message": "FRED_API_KEY was verified successfully."}
    except Exception as exc:  # noqa: BLE001 - network validation should not block app use.
        result = {
            "status": "unverified",
            "message": f"FRED_API_KEY is saved, but it could not be verified right now: {safe_exception_text(exc)}",
        }

    API_VALIDATION_CACHE[cache_key] = result
    return result


def read_api_env_values() -> dict[str, str]:
    """Read saved API values without exposing them in the UI."""
    values: dict[str, str] = {}
    if not API_ENV_PATH.exists():
        return values
    try:
        for line in API_ENV_PATH.read_text(encoding="utf-8", errors="ignore").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            key, value = stripped.split("=", 1)
            values[key.strip()] = value.strip().strip('"').strip("'")
    except OSError:
        return {}
    return values


def api_key_status() -> dict[str, Any]:
    """Return API key availability from API.env or process environment."""
    file_values = read_api_env_values()
    keys: dict[str, dict[str, str | bool]] = {}
    for key in API_KEY_ORDER:
        file_value = file_values.get(key, "")
        env_value = os.getenv(key, "").strip()
        if _api_value_is_filled(file_value):
            configured = True
            source = "API.env"
            value = file_value
        elif _api_value_is_filled(env_value):
            configured = True
            source = "environment"
            value = env_value
        else:
            configured = False
            source = ""
            value = ""
        validation = {"status": "not_checked", "message": ""}
        if key == "FRED_API_KEY":
            validation = validate_fred_api_key(value)
        keys[key] = {
            "configured": configured,
            "source": source,
            "validation_status": validation.get("status", "not_checked"),
            "validation_message": validation.get("message", ""),
        }
    fred_status = keys.get("FRED_API_KEY", {}).get("validation_status", "")
    return {
        "keys": keys,
        "has_any_key": any(bool(item["configured"]) for item in keys.values()),
        "has_invalid_key": fred_status == "invalid",
        "has_unverified_key": fred_status == "unverified",
        "has_saved_file": API_ENV_PATH.exists(),
    }


def save_api_env_values(
    fred_api_key: str,
    eia_api_key: str,
) -> list[str]:
    """Save provided API keys to API.env, preserving existing values when inputs are blank."""
    existing = read_api_env_values()
    updates = {
        "FRED_API_KEY": fred_api_key.strip(),
        "EIA_API_KEY": eia_api_key.strip(),
    }
    saved_keys: list[str] = []
    merged = existing.copy()
    for key in API_KEY_ORDER:
        new_value = updates.get(key, "")
        if _api_value_is_filled(new_value):
            merged[key] = new_value
            saved_keys.append(key)

    if not merged:
        return []

    lines = [
        "# API keys for Multiscale Net-Impact Analysis.",
        "# FRED_API_KEY is from Federal Reserve Economic Data: https://fred.stlouisfed.org/docs/api/api_key.html",
        "# EIA_API_KEY is from U.S. Energy Information Administration Open Data: https://www.eia.gov/opendata/register.php",
        "# GPRD does not need an API key; it is downloaded from the official Caldara-Iacoviello daily GPR file.",
    ]
    for key in API_KEY_ORDER:
        value = merged.get(key, "")
        if value:
            lines.append(f"{key}={value}")
            os.environ[key] = value
        else:
            lines.append(f"# {key}=")
    for key in sorted(set(merged) - set(API_KEY_ORDER)):
        value = merged[key]
        if value:
            lines.append(f"{key}={value}")
    API_ENV_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return saved_keys


def cleanup_artifact_groups() -> list[tuple[str, Path, str]]:
    """Return cleanup targets grouped for user-facing reporting."""
    return [
        ("Raw data cache", PROJECT_ROOT / "data" / "raw", "direct_files"),
        ("Processed data", PROJECT_ROOT / "data" / "processed", "directory"),
        ("Manual uploads", PATHS["upload_dir"], "directory"),
        ("Variable-pool raw files", PROJECT_ROOT / "data" / "raw" / "variable_pool", "directory"),
        ("Output tables", PROJECT_ROOT / "outputs" / "tables", "directory"),
        ("Output figures", PROJECT_ROOT / "outputs" / "figures", "directory"),
        ("Output reports", PROJECT_ROOT / "outputs" / "reports", "directory"),
        ("Model outputs", PROJECT_ROOT / "outputs" / "models", "directory"),
    ]


def clear_workspace_artifacts() -> dict[str, Any]:
    """Clear generated data, outputs, caches, and manually uploaded files."""
    deleted: list[str] = []
    group_counts: dict[str, int] = {}
    for group_name, path, mode in cleanup_artifact_groups():
        if mode == "direct_files":
            group_deleted = _delete_files_in_directory(path)
        else:
            group_deleted = _delete_path(path)
        group_counts[group_name] = len(group_deleted)
        deleted.extend(group_deleted)
    for state_key in [
        NET_IMPACT_CONFIRMATION_STATE,
        NET_IMPACT_VMD_CONFIRMATION_STATE,
        NET_IMPACT_TVP_CONFIRMATION_STATE,
        "local_upload_status_message",
        "api_settings_expanded",
    ]:
        st.session_state.pop(state_key, None)
    return {
        "deleted": sorted(set(deleted)),
        "counts": group_counts,
        "total": len(set(deleted)),
    }


def render_api_settings_panel(status: dict[str, Any]) -> None:
    """Render API key save controls in the top tool menu."""
    keys = status.get("keys", {})
    fred_status = keys.get("FRED_API_KEY", {})
    eia_status = keys.get("EIA_API_KEY", {})
    st.markdown(
        ui_text(
        """
        **API keys**

        FRED API key: Federal Reserve Economic Data. It is the preferred source
        for several U.S. financial and macro variables. The app also has
        automatic fallbacks for many variables, including Yahoo Finance, U.S.
        Treasury yield-curve data, New York Fed EFFR, and policyuncertainty.com.
        Register at
        [fred.stlouisfed.org](https://fred.stlouisfed.org/docs/api/api_key.html).

        EIA API key: U.S. Energy Information Administration Open Data. Used for WTI
        futures data refreshes. Register at
        [eia.gov/opendata](https://www.eia.gov/opendata/register.php).

        GPRD does not need an API key. It updates from the official Caldara-Iacoviello
        daily GPR file.

        """,
        """
        **API 密钥**

        FRED 与 EIA 密钥用于市场和宏观数据更新；GPRD 不需要密钥。

        """,
        )
    )
    if fred_status.get("configured"):
        st.caption(f"FRED_API_KEY is configured from {fred_status.get('source')}.")
        validation_status = str(fred_status.get("validation_status") or "")
        validation_message = str(fred_status.get("validation_message") or "")
        if validation_status == "valid":
            st.success(validation_message)
        elif validation_status == "invalid":
            st.error(validation_message)
        elif validation_status == "unverified":
            st.warning(validation_message)
    if eia_status.get("configured"):
        st.caption(f"EIA_API_KEY is configured from {eia_status.get('source')}.")
    with st.form("api_settings_form"):
        fred_key = st.text_input(
            ui_text("FRED API key", "FRED API 密钥"),
            value="",
            placeholder="Already saved" if fred_status.get("configured") else "Paste FRED_API_KEY",
            type="password",
            key="fred_api_key_input",
        )
        eia_key = st.text_input(
            ui_text("EIA API key", "EIA API 密钥"),
            value="",
            placeholder="Already saved" if eia_status.get("configured") else "Paste EIA_API_KEY",
            type="password",
            key="eia_api_key_input",
        )
        submitted = st.form_submit_button(ui_text("Save API keys", "保存 API 密钥"), use_container_width=True)
    if submitted:
        saved = save_api_env_values(fred_key, eia_key)
        if saved:
            st.session_state["api_settings_status"] = (
                ui_text("API.env saved. The current session will use the keys immediately.", "API.env 已保存，当前会话将立即使用这些密钥。")
            )
            st.session_state["api_settings_expanded"] = False
            st.rerun()
        elif status.get("has_any_key"):
            st.info(ui_text("API keys are already configured. No changes were saved.", "API 密钥已配置，本次未保存更改。"))
        else:
            st.warning(ui_text("Paste at least one API key before saving.", "保存前请至少填写一个 API 密钥。"))


def render_top_tool_menu() -> None:
    """Render the compact top-right app tool menu."""
    if is_cloud_runtime():
        return
    status_info = api_key_status()
    api_missing = not bool(status_info.get("has_any_key"))
    api_invalid = bool(status_info.get("has_invalid_key"))
    api_unverified = bool(status_info.get("has_unverified_key"))
    if api_missing:
        badge_class = "missing"
        badge_text = ui_text("API missing", "缺少 API")
    elif api_invalid:
        badge_class = "missing"
        badge_text = ui_text("API invalid", "API 无效")
    elif api_unverified:
        badge_class = "warning"
        badge_text = ui_text("API unverified", "API 未验证")
    else:
        badge_class = "configured"
        badge_text = ui_text("API configured", "API 已配置")

    st.markdown('<div class="top-tool-menu">', unsafe_allow_html=True)
    with st.popover("⋯", use_container_width=False):
        st.markdown(
            f'<span class="api-status-badge {badge_class}">{badge_text}</span>',
            unsafe_allow_html=True,
        )
        api_button_label = ui_text("API setup required", "需要配置 API") if api_missing or api_invalid else ui_text("API settings", "API 设置")
        if st.button(
            api_button_label,
            type="primary" if api_missing or api_invalid else "secondary",
            use_container_width=True,
            key="open_api_settings",
        ):
            st.session_state["api_settings_expanded"] = True

        with st.expander(
            ui_text("API Settings", "API 设置"),
            expanded=api_missing or api_invalid or bool(st.session_state.get("api_settings_expanded", False)),
        ):
            render_api_settings_panel(status_info)

        st.divider()
        st.markdown(ui_text("**Cleanup**", "**清理**"))
        st.caption(
            ui_text(
                "Clear generated data, caches, uploads, tables, figures, reports, and model outputs. API.env is kept.",
                "清理生成数据、缓存、上传文件、表格、图片、报告和模型输出；保留 API.env。",
            )
        )
        if st.button(ui_text("Clear generated files", "清理生成文件"), use_container_width=True, key="open_workspace_cleanup"):
            st.session_state["workspace_cleanup_confirm"] = True

        if st.session_state.get("workspace_cleanup_confirm"):
            st.warning(
                "This deletes generated analysis files and uploaded variable files. API.env is not deleted."
            )
            st.caption(
                "Targets: "
                + ", ".join(group_name for group_name, _, _ in cleanup_artifact_groups())
            )
            confirm_col, cancel_col = st.columns(2)
            if confirm_col.button("Confirm clear", use_container_width=True, key="confirm_workspace_cleanup"):
                result = clear_workspace_artifacts()
                count = int(result.get("total", 0))
                counts = result.get("counts", {})
                nonzero_groups = [
                    f"{group}: {group_count}"
                    for group, group_count in counts.items()
                    if int(group_count or 0) > 0
                ]
                detail = (
                    f"{count} files removed"
                    + (f" ({'; '.join(nonzero_groups)})" if nonzero_groups else "")
                    if count
                    else "nothing to remove"
                )
                st.session_state["workspace_cleanup_status"] = f"Workspace cleanup completed: {detail}."
                st.session_state["workspace_cleanup_confirm"] = False
                st.rerun()
            if cancel_col.button("Cancel", use_container_width=True, key="cancel_workspace_cleanup"):
                st.session_state["workspace_cleanup_confirm"] = False
                st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)


def render_workspace_status_messages() -> None:
    """Render cross-page tool status messages outside the narrow menu column."""
    cleanup_status = st.session_state.pop("workspace_cleanup_status", None)
    api_status_message = st.session_state.pop("api_settings_status", None)
    if cleanup_status:
        st.success(cleanup_status)
    if api_status_message:
        st.success(api_status_message)


def get_latest_complete_market_date(
    path: str | Path = PROJECT_ROOT / "data" / "processed" / "clean_market_data.xlsx",
    required_columns: list[str] | None = None,
) -> pd.Timestamp | None:
    """Return the latest date with complete observations across core market columns."""
    path = Path(path)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    if not path.exists():
        return None

    data = pd.read_excel(path)
    if "Date" not in data.columns:
        return None
    required_columns = required_columns or CORE_MARKET_FRESHNESS_COLUMNS
    if any(column not in data.columns for column in required_columns):
        return None

    prepared = data.copy()
    prepared["Date"] = pd.to_datetime(prepared["Date"], errors="coerce")
    complete = prepared.dropna(subset=["Date", *required_columns])
    dates = complete["Date"].dropna()
    if dates.empty:
        return None
    return dates.max()


def core_market_stale_tolerance_days(variable: str) -> int:
    """Return a calendar-day freshness tolerance for one core market variable."""
    if variable == "WTI":
        return 7
    if variable in {"Brent", "Gold"}:
        return 10
    return 14


def get_core_market_freshness_rows(
    path: str | Path,
    selected_end_date: str | pd.Timestamp,
    required_columns: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Return per-variable freshness rows for core market data."""
    path = Path(path)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    selected_end = pd.to_datetime(selected_end_date).normalize()
    required_columns = required_columns or CORE_MARKET_FRESHNESS_COLUMNS
    if not path.exists():
        return [
            {
                "Variable": variable,
                "LatestDate": pd.NaT,
                "StaleDays": None,
                "ToleranceDays": core_market_stale_tolerance_days(variable),
                "Fresh": False,
            }
            for variable in required_columns
        ]

    data = pd.read_excel(path)
    rows: list[dict[str, Any]] = []
    if "Date" not in data.columns:
        return [
            {
                "Variable": variable,
                "LatestDate": pd.NaT,
                "StaleDays": None,
                "ToleranceDays": core_market_stale_tolerance_days(variable),
                "Fresh": False,
            }
            for variable in required_columns
        ]

    data = data.copy()
    data["Date"] = pd.to_datetime(data["Date"], errors="coerce").dt.normalize()
    for variable in required_columns:
        tolerance = core_market_stale_tolerance_days(variable)
        latest = pd.NaT
        stale_days = None
        fresh = False
        if variable in data.columns:
            valid_dates = data.loc[pd.to_numeric(data[variable], errors="coerce").notna(), "Date"].dropna()
            if not valid_dates.empty:
                latest = valid_dates.max()
                stale_days = int((selected_end - latest).days)
                fresh = stale_days <= tolerance
        rows.append(
            {
                "Variable": variable,
                "LatestDate": latest,
                "StaleDays": stale_days,
                "ToleranceDays": tolerance,
                "Fresh": fresh,
            }
        )
    return rows


def assert_core_market_data_fresh(
    clean_data_path: str | Path,
    selected_end_date: str | pd.Timestamp,
    max_stale_days: int = 7,
) -> pd.Timestamp:
    """Raise ValueError when any core market series is too old for the selected end date."""
    latest_complete_date = get_latest_complete_market_date(clean_data_path)
    rows = get_core_market_freshness_rows(clean_data_path, selected_end_date)
    stale_rows = [row for row in rows if not bool(row.get("Fresh"))]
    if stale_rows:
        details = "; ".join(
            f"{row['Variable']} latest {format_date_text(row.get('LatestDate')) or 'unavailable'} "
            f"(tolerance {row['ToleranceDays']} days)"
            for row in stale_rows
        )
        raise ValueError(
            "Core market data is outdated or unavailable. "
            f"{details}. Selected end date is {pd.to_datetime(selected_end_date):%Y-%m-%d}."
        )
    return latest_complete_date or pd.NaT


def _max_date_from_file(path: Path, candidate_columns: list[str]) -> pd.Timestamp | None:
    """Read a date from an Excel file using the first available date column."""
    if not path.exists():
        return None
    try:
        data = pd.read_excel(path)
    except Exception:  # noqa: BLE001 - freshness check should not break UI.
        return None
    if data.empty:
        return None
    for column in candidate_columns:
        if column in data.columns:
            dates = pd.to_datetime(data[column], errors="coerce").dropna()
            if not dates.empty:
                return dates.max()
    return None


def load_variable_pool_options() -> tuple[list[str], list[str]]:
    """Load variable-pool names and conservative default selections for the sidebar."""
    fallback = [
        "WTI",
        "Brent",
        "GPRD",
        "Gold",
        "OVX",
        "DollarIndex",
        "TNote10Y",
        "VIX",
        "SP500",
        "Nasdaq",
        "NaturalGas",
        "US2Y",
        "FedFunds",
        "CNYUSD",
        "ShanghaiSC",
        "ShanghaiFU",
        "Gasoline",
        "HeatingOil",
        "Copper",
        "Silver",
        "EPU",
        "TPU",
        "EMV",
    ]
    try:
        load_variable_registry = import_function("src.variable_pool", "load_variable_registry")
        registry = load_variable_registry()
    except Exception:
        return fallback, fallback[:12]

    options = [entry["name"] for entry in registry if entry.get("name")]
    defaults = [
        entry["name"]
        for entry in registry
        if bool(entry.get("auto_download", False))
        or any(source.get("type") == "existing_model_ready_column" for source in entry.get("sources", []))
    ]
    defaults = [variable for variable in defaults if variable in options]
    uploaded_names = load_uploaded_variable_names()
    for variable in uploaded_names:
        if variable not in options:
            options.append(variable)
        if variable not in defaults:
            defaults.append(variable)
    return options or fallback, defaults or fallback[:12]


def load_variable_registry_metadata() -> dict[str, dict[str, Any]]:
    """Load variable names, full descriptions, frequencies, and sources for UI labels."""
    try:
        load_variable_registry = import_function("src.variable_pool", "load_variable_registry")
        registry = load_variable_registry()
    except Exception:
        return {}
    metadata: dict[str, dict[str, Any]] = {}
    for entry in registry:
        name = str(entry.get("name", "")).strip()
        if not name:
            continue
        source_types = []
        for source in entry.get("sources", []):
            source_type = str(source.get("type", "")).strip()
            if source_type and source_type not in source_types:
                source_types.append(source_type)
        metadata[name] = {
            "Variable": name,
            "FullName": str(entry.get("description", "") or name),
            "SourceTypes": source_types,
            "Frequency": str(entry.get("frequency", "") or ""),
            "DailyAlignment": str(entry.get("daily_alignment", "") or ""),
            "AutoDownload": bool(entry.get("auto_download", False)),
            "IsProxy": bool(entry.get("is_proxy", False)),
            "Note": str(entry.get("note", "") or ""),
        }
    return metadata


def localized_variable_name(
    variable: str,
    metadata: dict[str, dict[str, Any]],
    language: LanguageCode,
) -> str:
    """Return a localized display name while preserving the stable variable code."""
    if language == "zh":
        return VARIABLE_CHINESE_NAMES.get(variable, str(metadata.get(variable, {}).get("FullName") or variable))
    return str(metadata.get(variable, {}).get("FullName") or variable).rstrip(".")


def clean_display_text(value: Any) -> str:
    """Remove machine-oriented separators from text shown to users."""
    text = str(value or "").replace("_", " ").replace("^", "")
    return " ".join(text.split()).strip(" :;,-")


def localized_source_names(item: dict[str, Any], language: LanguageCode) -> str:
    """Return deduplicated, human-readable provider names without source IDs."""
    source_types = item.get("SourceTypes", [])
    if not source_types and item.get("Sources"):
        source_types = [part.strip().split(":", 1)[0] for part in str(item["Sources"]).split(";")]
    labels: list[str] = []
    for source_type in source_types:
        english, chinese = SOURCE_DISPLAY_NAMES.get(
            str(source_type),
            (clean_display_text(source_type).title(), clean_display_text(source_type)),
        )
        label = localized_text(english, chinese, language)
        if label and label not in labels:
            labels.append(label)
    return ("、" if language == "zh" else ", ").join(labels) or localized_text(
        "Not configured", "未配置", language
    )


def localized_bool(value: Any, language: LanguageCode) -> str:
    """Format metadata flags as readable yes/no labels."""
    return localized_text("Yes", "是", language) if bool(value) else localized_text("No", "否", language)


def format_variable_option(
    variable: str,
    metadata: dict[str, dict[str, Any]],
    language: LanguageCode = "en",
) -> str:
    """Format a concise localized option without machine-oriented source strings."""
    variable_code = clean_display_text(variable)
    display_name = clean_display_text(
        VARIABLE_SHORT_CHINESE_NAMES.get(variable, localized_variable_name(variable, metadata, language))
        if language == "zh"
        else localized_variable_name(variable, metadata, language)
    )
    return f"{variable_code} · {display_name}"


def selected_variable_metadata_frame(
    variables: list[str],
    metadata: dict[str, dict[str, Any]],
    language: LanguageCode = "en",
) -> pd.DataFrame:
    """Build a readable, localized metadata table for selected variables."""
    rows = []
    for variable in variables:
        item = metadata.get(variable, {})
        frequency = item.get("Frequency", "")
        if language == "zh" and str(frequency).lower() == "daily":
            frequency = "日频"
        rows.append(
            {
                localized_text("Variable", "变量代码", language): clean_display_text(variable),
                localized_text("Full name", "变量名称", language): clean_display_text(
                    localized_variable_name(variable, metadata, language)
                ),
                localized_text("Frequency", "频率", language): frequency,
                localized_text("Sources", "数据来源", language): localized_source_names(item, language),
                localized_text("Auto download", "自动下载", language): localized_bool(
                    item.get("AutoDownload", False), language
                ),
                localized_text("Proxy", "代理变量", language): localized_bool(
                    item.get("IsProxy", False), language
                ),
            }
        )
    return pd.DataFrame(rows)


def load_uploaded_variable_names() -> list[str]:
    """Load locally uploaded variable names from the upload manifest."""
    manifest_path = PATHS["uploaded_variable_manifest"]
    if not manifest_path.exists():
        return []
    try:
        manifest = pd.read_excel(manifest_path)
    except Exception:
        return []
    if "VariableName" not in manifest.columns:
        return []
    return [
        str(value)
        for value in manifest["VariableName"].dropna().astype(str).tolist()
        if str(value).strip()
    ]


def render_sidebar() -> dict[str, Any]:
    """Render sidebar controls."""
    st.sidebar.header(ui_text("Analysis Settings", "分析设置"))
    st.sidebar.caption(
        ui_text(
            "Set the analysis/event window. Variables and method settings are configured on the Run Analysis page.",
            "设置分析与事件窗口；变量和方法参数在“运行分析”页面配置。",
        )
    )
    local_start, local_end = get_complete_market_date_range_if_exists(PATHS["clean_market"])
    if local_start is None or local_end is None:
        local_start, local_end = get_date_range_if_exists(PATHS["clean_market"])
    default_start = pd.Timestamp("2020-01-01")
    default_end = local_end if local_end is not None else pd.Timestamp("2024-03-31")
    if local_start is not None and default_start < local_start:
        default_start = local_start
    with st.sidebar.container(border=True):
        st.markdown(ui_text("**Analysis Window**", "**分析窗口**"))
        start_picker_key = "analysis_start_date_picker"
        end_picker_key = "analysis_end_date_picker"
        if start_picker_key not in st.session_state:
            st.session_state[start_picker_key] = default_start.date()
        if end_picker_key not in st.session_state:
            st.session_state[end_picker_key] = default_end.date()

        start_date = st.date_input(
            ui_text("Start date", "开始日期"),
            format="YYYY/MM/DD",
            key=start_picker_key,
        )
        end_date = st.date_input(
            ui_text("End date", "结束日期"),
            format="YYYY/MM/DD",
            key=end_picker_key,
        )
        start_timestamp = pd.Timestamp(start_date).normalize()
        end_timestamp = pd.Timestamp(end_date).normalize()
        if start_timestamp > end_timestamp:
            st.error(ui_text("Start date must be on or before end date. The current run will use the default window.", "开始日期必须早于或等于结束日期，本次将使用默认窗口。"))
            start_timestamp = default_start
            end_timestamp = default_end
        requested_window_end = (start_timestamp - pd.offsets.BDay(1)).normalize()
        default_window_dates = pd.bdate_range(
            end=requested_window_end,
            periods=DEFAULT_PRE_EVENT_WINDOW_TRADING_DAYS,
        )
        default_window_start = pd.Timestamp(default_window_dates.min()).normalize()
        window_start_picker_key = "pre_event_window_start_date_picker"
        if window_start_picker_key not in st.session_state:
            st.session_state[window_start_picker_key] = default_window_start.date()
        current_window_start = pd.to_datetime(
            st.session_state.get(window_start_picker_key, default_window_start.date()),
            errors="coerce",
        )
        if pd.isna(current_window_start) or current_window_start.normalize() > requested_window_end:
            st.session_state[window_start_picker_key] = default_window_start.date()
        window_start_date = st.date_input(
            ui_text("Window period start date", "事件前窗口开始日期"),
            format="YYYY/MM/DD",
            max_value=requested_window_end.date(),
            key=window_start_picker_key,
        )
        window_start_timestamp = pd.Timestamp(window_start_date).normalize()
        if window_start_timestamp > requested_window_end:
            window_start_timestamp = default_window_start
            st.session_state[window_start_picker_key] = default_window_start.date()
            st.warning(ui_text("Window period start date must be before the event start date. The default start date is used.", "事件前窗口开始日期必须早于事件开始日期，已使用默认日期。"))
        window_trading_days = max(1, business_day_count(window_start_timestamp, requested_window_end))
        st.caption(ui_text(f"Selected window: {start_timestamp:%Y-%m-%d} to {end_timestamp:%Y-%m-%d}", f"已选分析窗口：{start_timestamp:%Y-%m-%d} 至 {end_timestamp:%Y-%m-%d}"))
        st.caption(ui_text(f"Pre-event window: {window_start_timestamp:%Y-%m-%d} to {requested_window_end:%Y-%m-%d}.", f"事件前窗口：{window_start_timestamp:%Y-%m-%d} 至 {requested_window_end:%Y-%m-%d}。"))
        st.caption(ui_text(f"Selected pre-event length: {window_trading_days} business days before cleaning.", f"清洗前事件窗口长度：{window_trading_days} 个工作日。"))
        st.caption(
            ui_text(
                "The pre-event length is the baseline window used before the event; it is not the event start date or the data-cleaning start date.",
                "事件前长度是事件发生前的基准窗口，并非事件开始日期或数据清洗开始日期。",
            )
        )
        if local_start is not None and local_end is not None:
            st.caption(ui_text(f"Local complete core market data currently covers {local_start:%Y-%m-%d} to {local_end:%Y-%m-%d}.", f"本地完整核心市场数据覆盖 {local_start:%Y-%m-%d} 至 {local_end:%Y-%m-%d}。"))
    st.sidebar.divider()
    st.sidebar.subheader(ui_text("Workflow", "工作流程"))
    st.sidebar.write(ui_text("This website runs the multiscale net-impact analysis workflow.", "本网站运行多尺度净影响分析流程。"))
    st.sidebar.caption(ui_text("Open Run Analysis to choose targets, explanatory variables, and local uploads.", "在“运行分析”中选择目标变量、解释变量和本地上传文件。"))

    feature_selection_method = "mrgc_then_elasticnet"
    max_lag = 5
    model_type = "ridge"
    enable_feature_selection = True
    train_ratio = 0.8
    horizon = 1
    max_selected_features = 20
    vmd_imf_count = 4
    min_data_coverage = 0.60
    use_uploaded_local_data_first = False
    auto_download_expanded_variable_pool = True
    variable_pool_options, default_variable_pool = load_variable_pool_options()
    default_targets = [variable for variable in ["WTI", "Brent"] if variable in variable_pool_options]
    paper_target_variables = default_targets[:2]
    explanatory_defaults = [
        variable
        for variable in default_variable_pool
        if variable not in paper_target_variables
    ]
    paper_explanatory_variables = explanatory_defaults
    selected_variable_pool = sorted(set(default_variable_pool) | set(paper_target_variables) | set(paper_explanatory_variables))
    show_selected_variables = True

    return {
        "start_date": start_timestamp.strftime("%Y-%m-%d"),
        "end_date": end_timestamp.strftime("%Y-%m-%d"),
        "window_start_date": window_start_timestamp.strftime("%Y-%m-%d"),
        "window_end_date": requested_window_end.strftime("%Y-%m-%d"),
        "window_trading_days": int(window_trading_days),
        "model_type": model_type,
        "train_ratio": float(train_ratio),
        "max_lag": int(max_lag),
        "horizon": int(horizon),
        "enable_feature_selection": bool(enable_feature_selection),
        "feature_selection_method": feature_selection_method,
        "max_selected_features": int(max_selected_features),
        "vmd_imf_count": int(vmd_imf_count),
        "min_data_coverage": float(min_data_coverage),
        "use_uploaded_local_data_first": bool(use_uploaded_local_data_first),
        "auto_download_expanded_variable_pool": bool(auto_download_expanded_variable_pool),
        "paper_target_variables": list(paper_target_variables),
        "paper_explanatory_variables": list(paper_explanatory_variables),
        "selected_variable_pool": sorted(
            set(selected_variable_pool) | set(paper_target_variables) | set(paper_explanatory_variables)
        ),
        "show_selected_variables": bool(show_selected_variables),
    }


def run_update_market_data(options: dict[str, Any]) -> None:
    """Run market data update."""
    build_market_dataset = import_function("src.data_fetcher", "build_market_dataset")

    build_market_dataset(options["start_date"], options["end_date"], force_refresh=True)


def run_prepare_model_data() -> None:
    """Run model-data preparation."""
    from src.data_cleaner import prepare_model_data

    prepare_model_data()


def sanitize_variable_name(name: str) -> str:
    """Convert a user-entered variable name into a safe column identifier."""
    cleaned = re.sub(r"[^0-9A-Za-z_]+", "_", str(name).strip())
    cleaned = re.sub(r"_+", "_", cleaned).strip("_")
    if not cleaned:
        raise ValueError("Variable name cannot be empty.")
    if cleaned[0].isdigit():
        cleaned = f"Var_{cleaned}"
    reserved = {"Date", "date", "Time", "time", "WTI_Reconstructed", "WTI_Reconstruction_Error"}
    if cleaned in reserved:
        raise ValueError(f"{cleaned} is reserved. Please choose another variable name.")
    return cleaned


UPLOADED_COLUMN_DISPLAY_ALIASES = {
    "\u65e5\u671f": "Date",
    "\u65f6\u95f4": "Time",
    "\u4ea4\u6613\u65e5\u671f": "Date",
    "\u6536\u76d8": "Close",
    "\u6536\u76d8\u4ef7": "Close",
    "\u6700\u65b0\u4ef7": "Close",
    "\u4ef7\u683c": "Price",
    "\u5f00\u76d8": "Open",
    "\u5f00\u76d8\u4ef7": "Open",
    "\u9ad8": "High",
    "\u6700\u9ad8": "High",
    "\u6700\u9ad8\u4ef7": "High",
    "\u4f4e": "Low",
    "\u6700\u4f4e": "Low",
    "\u6700\u4f4e\u4ef7": "Low",
    "\u4ea4\u6613\u91cf": "Volume",
    "\u6210\u4ea4\u91cf": "Volume",
    "\u6210\u4ea4\u989d": "Turnover",
    "\u6da8\u8dcc\u5e45": "Percent change",
    "\u6da8\u8dcc\u5e45%": "Percent change",
    "\u6da8\u8dcc\u989d": "Change",
}


def _contains_non_ascii(text: str) -> bool:
    """Return whether a label contains non-ASCII characters."""
    return any(ord(character) > 127 for character in text)


def display_uploaded_column_name(column: Any) -> str:
    """Return an English UI label for an uploaded file column."""
    text = str(column).strip()
    alias = UPLOADED_COLUMN_DISPLAY_ALIASES.get(text)
    if alias:
        return alias
    return "Uploaded column" if _contains_non_ascii(text) else text


def uploaded_column_display_labels(columns: list[str]) -> dict[str, str]:
    """Build unique English labels for uploaded-file columns."""
    labels: dict[str, str] = {}
    used: set[str] = set()
    for index, column in enumerate(columns, start=1):
        base = display_uploaded_column_name(column)
        label = base
        if label in used:
            label = f"{base} {index}"
        used.add(label)
        labels[column] = label
    return labels


def coerce_uploaded_numeric_series(series: pd.Series) -> pd.Series:
    """Parse numeric upload columns, including common market-data text formats."""
    if pd.api.types.is_numeric_dtype(series):
        return pd.to_numeric(series, errors="coerce")

    text = series.astype("string").str.strip()
    text = text.mask(text.str.lower().isin({"", "-", "--", "nan", "none", "null", "n/a", "na"}))
    lower_text = text.str.lower()
    multiplier = pd.Series(1.0, index=series.index)
    multiplier = multiplier.mask(text.str.contains("\u4ebf", regex=False, na=False), 100_000_000.0)
    multiplier = multiplier.mask(text.str.contains("\u4e07", regex=False, na=False), 10_000.0)
    multiplier = multiplier.mask(lower_text.str.contains("b", regex=False, na=False), 1_000_000_000.0)
    multiplier = multiplier.mask(lower_text.str.contains("m", regex=False, na=False), 1_000_000.0)
    multiplier = multiplier.mask(lower_text.str.contains("k", regex=False, na=False), 1_000.0)

    cleaned = (
        text.str.replace(",", "", regex=False)
        .str.replace("，", "", regex=False)
        .str.replace("%", "", regex=False)
        .str.replace("％", "", regex=False)
        .str.replace("$", "", regex=False)
        .str.replace("￥", "", regex=False)
        .str.replace("¥", "", regex=False)
        .str.replace("\u4ebf", "", regex=False)
        .str.replace("\u4e07", "", regex=False)
        .str.replace(r"[Bb]", "", regex=True)
        .str.replace(r"[Mm]", "", regex=True)
        .str.replace(r"[Kk]", "", regex=True)
        .str.replace(r"^\((.*)\)$", r"-\1", regex=True)
    )
    return pd.to_numeric(cleaned, errors="coerce") * multiplier


def coerce_uploaded_date_series(series: pd.Series) -> pd.Series:
    """Parse uploaded date columns, including Excel serial dates."""
    numeric = pd.to_numeric(series, errors="coerce")
    excel_serial = numeric.between(20_000, 60_000)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        parsed = pd.to_datetime(series.astype("string").where(~excel_serial), errors="coerce")
    if excel_serial.any():
        parsed.loc[excel_serial] = pd.to_datetime(
            numeric.loc[excel_serial],
            unit="D",
            origin="1899-12-30",
            errors="coerce",
        )
    return parsed


def automatic_uploaded_column_mapping(columns: list[str]) -> tuple[str, str]:
    """Map manual-upload files by position: first Date, second Value."""
    if len(columns) != 2:
        raise ValueError("Uploaded files must contain exactly two columns: Date and Value.")
    return columns[0], columns[1]


def normalise_uploaded_market_frame(raw: pd.DataFrame, source_name: str) -> pd.DataFrame:
    """Return Date/Value rows after skipping leading non-data header rows."""
    raw = raw.dropna(how="all").dropna(axis=1, how="all").reset_index(drop=True)
    if raw.shape[1] != 2:
        raise ValueError(f"{source_name} must contain exactly two columns: Date and Value.")

    first_two = raw.iloc[:, :2].copy()
    date_values = coerce_uploaded_date_series(first_two.iloc[:, 0])
    value_values = coerce_uploaded_numeric_series(first_two.iloc[:, 1])
    data_rows = date_values.notna() & value_values.notna()
    if not data_rows.any():
        raise ValueError(
            f"{source_name} does not contain a detectable data row. "
            "The first column must contain dates and the second column must contain numeric values."
        )

    first_data_position = int(data_rows[data_rows].index[0])
    data = first_two.iloc[first_data_position:].copy()
    data.columns = ["Date", "Value"]
    data["Date"] = coerce_uploaded_date_series(data["Date"])
    data["Value"] = coerce_uploaded_numeric_series(data["Value"])
    data = data.dropna(subset=["Date"]).sort_values("Date").drop_duplicates(subset=["Date"], keep="last")
    return data


def read_uploaded_file_to_dataframe(uploaded_file: Any) -> pd.DataFrame:
    """Read one Streamlit upload into a DataFrame without saving it first."""
    suffix = Path(uploaded_file.name).suffix.lower()
    if suffix == ".csv":
        raw_bytes = uploaded_file.getvalue()
        last_error: Exception | None = None
        for encoding in ("utf-8-sig", "utf-8", "gb18030", "gbk"):
            try:
                raw = pd.read_csv(BytesIO(raw_bytes), encoding=encoding, header=None)
                data = normalise_uploaded_market_frame(raw, Path(uploaded_file.name).name)
                uploaded_file.seek(0)
                return data
            except UnicodeDecodeError as exc:
                last_error = exc
        raise ValueError(f"Could not decode CSV upload: {last_error}")
    uploaded_file.seek(0)
    if suffix in {".xlsx", ".xls"}:
        raw = pd.read_excel(uploaded_file, header=None)
        data = normalise_uploaded_market_frame(raw, Path(uploaded_file.name).name)
        uploaded_file.seek(0)
        return data
    raise ValueError(f"Unsupported upload file type: {suffix}")


def guess_date_column(columns: list[str]) -> str | None:
    """Guess the date column from common English and Chinese names."""
    aliases = {"date", "datetime", "time", "timestamp", "\u65e5\u671f", "\u65f6\u95f4"}
    for column in columns:
        text = str(column).strip()
        if text.lower() in aliases or text in aliases:
            return column
    for column in columns:
        text = str(column).strip().lower()
        if "date" in text or "time" in text:
            return column
    return None


def numeric_value_columns(data: pd.DataFrame, date_column: str | None) -> list[str]:
    """Find columns that can be interpreted as numeric variable values."""
    candidates: list[str] = []
    for column in data.columns:
        if column == date_column:
            continue
        numeric = coerce_uploaded_numeric_series(data[column])
        if numeric.notna().any():
            candidates.append(str(column))
    return candidates


def preferred_uploaded_value_column_index(value_columns: list[str]) -> int:
    """Prefer a closing price or general price column when uploads expose many numeric fields."""
    priority = ("Close", "Price", "Value", "Percent change", "Volume")
    labels = [display_uploaded_column_name(column).lower() for column in value_columns]
    for preferred in priority:
        preferred_lower = preferred.lower()
        for index, label in enumerate(labels):
            if label == preferred_lower or label.startswith(preferred_lower):
                return index
    return 0


def selected_reference_dates(start_date: str, end_date: str) -> pd.DataFrame:
    """Return model-ready dates for coverage checks, or business days as fallback."""
    start = pd.to_datetime(start_date)
    end = pd.to_datetime(end_date)
    if PATHS["model_ready"].exists():
        try:
            model_ready = pd.read_excel(PATHS["model_ready"])
            if "Date" in model_ready.columns:
                dates = pd.to_datetime(model_ready["Date"], errors="coerce").dropna()
                dates = dates[(dates >= start) & (dates <= end)].drop_duplicates().sort_values()
                if not dates.empty:
                    return pd.DataFrame({"Date": dates})
        except Exception:
            pass
    return pd.DataFrame({"Date": pd.bdate_range(start=start, end=end)})


def standardize_uploaded_variable(
    uploaded_file: Any,
    variable_name: str,
    date_column: str,
    value_column: str,
    start_date: str,
    end_date: str,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Validate and standardize one uploaded local variable file."""
    raw = read_uploaded_file_to_dataframe(uploaded_file)
    if date_column not in raw.columns:
        raise ValueError(f"Date column '{date_column}' was not found in {uploaded_file.name}.")
    if value_column not in raw.columns:
        raise ValueError(f"Value column '{value_column}' was not found in {uploaded_file.name}.")

    variable = sanitize_variable_name(variable_name)
    data = raw[[date_column, value_column]].copy()
    data.columns = ["Date", variable]
    data["Date"] = coerce_uploaded_date_series(data["Date"])
    data[variable] = coerce_uploaded_numeric_series(data[variable])
    data = data.dropna(subset=["Date"])
    data = data.sort_values("Date").drop_duplicates(subset=["Date"], keep="last")

    start = pd.to_datetime(start_date)
    end = pd.to_datetime(end_date)
    selected = data[(data["Date"] >= start) & (data["Date"] <= end)].copy()
    reference_dates = selected_reference_dates(start_date, end_date)
    coverage_frame = reference_dates.merge(selected, on="Date", how="left")
    coverage = float(coverage_frame[variable].notna().mean()) if len(coverage_frame) else 0.0
    latest = selected.loc[selected[variable].notna(), "Date"].max() if selected[variable].notna().any() else pd.NaT
    earliest = selected.loc[selected[variable].notna(), "Date"].min() if selected[variable].notna().any() else pd.NaT

    stats = {
        "OriginalFile": Path(uploaded_file.name).name,
        "VariableName": variable,
        "DateColumn": "Date",
        "ValueColumn": "Value",
        "RowsInFile": int(len(raw)),
        "RowsInSelectedWindow": int(len(selected)),
        "ReferenceDates": int(len(reference_dates)),
        "NonMissingInSelectedWindow": int(coverage_frame[variable].notna().sum()),
        "Coverage": coverage,
        "EarliestDate": earliest,
        "LatestDate": latest,
        "SelectedStartDate": start,
        "SelectedEndDate": end,
        "SavedFile": f"{variable}.csv",
    }
    return data[["Date", variable]], stats


def uploaded_preprocess_failure_row(file_name: str, note: str, variable_name: str = "") -> dict[str, Any]:
    """Build one failed manual-upload preprocessing summary row."""
    return {
        "File": file_name,
        "Variable": variable_name,
        "Status": "Failed",
        "ExtractedStartDate": "",
        "ExtractedEndDate": "",
        "ExtractedRows": 0,
        "SelectedWindowRows": 0,
        "SelectedWindowCoverage": "0.0%",
        "Note": note,
    }


def uploaded_preprocess_summary_row(
    file_name: str,
    variable_name: str,
    prepared: pd.DataFrame,
    start_date: str,
    end_date: str,
    min_coverage: float,
) -> dict[str, Any]:
    """Summarize one preprocessed manual upload before it is saved."""
    data = prepared.copy()
    data["Date"] = pd.to_datetime(data["Date"], errors="coerce")
    data["Value"] = pd.to_numeric(data["Value"], errors="coerce")
    valid_data = data.dropna(subset=["Date"])
    valid_value = valid_data[valid_data["Value"].notna()]
    selected_start = pd.to_datetime(start_date)
    selected_end = pd.to_datetime(end_date)
    selected = valid_data[(valid_data["Date"] >= selected_start) & (valid_data["Date"] <= selected_end)]
    reference_dates = selected_reference_dates(start_date, end_date)
    coverage_frame = reference_dates.merge(valid_data[["Date", "Value"]], on="Date", how="left")
    coverage = float(coverage_frame["Value"].notna().mean()) if len(coverage_frame) else 0.0
    status = "Ready"
    note = "Ready to add after confirmation."
    if selected["Value"].notna().sum() == 0:
        status = "Ready, outside selected window"
        note = "No values were found inside the current analysis window."
    elif coverage < min_coverage:
        status = "Ready, low coverage"
        note = "Coverage is below the current minimum data coverage setting."
    return {
        "File": file_name,
        "Variable": variable_name,
        "Status": status,
        "ExtractedStartDate": format_date_text(valid_value["Date"].min()) if not valid_value.empty else "",
        "ExtractedEndDate": format_date_text(valid_value["Date"].max()) if not valid_value.empty else "",
        "ExtractedRows": int(len(valid_value)),
        "SelectedWindowRows": int(selected["Value"].notna().sum()),
        "SelectedWindowCoverage": f"{coverage * 100:.1f}%",
        "Note": note,
    }


def save_standardized_uploaded_variables(
    upload_jobs: list[dict[str, Any]],
    min_coverage: float,
) -> tuple[list[Path], pd.DataFrame]:
    """Save validated local variables and write upload manifest/report tables."""
    upload_dir = PATHS["upload_dir"]
    original_dir = PATHS["upload_original_dir"]
    upload_dir.mkdir(parents=True, exist_ok=True)
    original_dir.mkdir(parents=True, exist_ok=True)
    PATHS["uploaded_variable_manifest"].parent.mkdir(parents=True, exist_ok=True)

    saved_paths: list[Path] = []
    report_rows: list[dict[str, Any]] = []
    for job in upload_jobs:
        try:
            data, stats = standardize_uploaded_variable(
                uploaded_file=job["uploaded_file"],
                variable_name=job["variable_name"],
                date_column=job["date_column"],
                value_column=job["value_column"],
                start_date=job["start_date"],
                end_date=job["end_date"],
            )
            variable = stats["VariableName"]
            output_path = upload_dir / f"{variable}.csv"
            data.to_csv(output_path, index=False)
            original_path = original_dir / Path(job["uploaded_file"].name).name
            original_path.write_bytes(job["uploaded_file"].getbuffer())
            stats["OriginalSavedFile"] = str(original_path.relative_to(PROJECT_ROOT))
            stats["Status"] = "Kept" if stats["Coverage"] >= min_coverage else "SavedLowCoverage"
            stats["Note"] = (
                "Saved and available for the candidate pool."
                if stats["Coverage"] >= min_coverage
                else "Saved, but current selected-window coverage is below the minimum data coverage setting."
            )
            saved_paths.append(output_path)
            report_rows.append(stats)
        except Exception as exc:  # noqa: BLE001 - report all upload failures.
            report_rows.append(
                {
                    "OriginalFile": Path(job.get("uploaded_file").name).name if job.get("uploaded_file") else "",
                    "VariableName": job.get("variable_name", ""),
                    "DateColumn": job.get("date_column", ""),
                    "ValueColumn": job.get("value_column", ""),
                    "Coverage": 0.0,
                    "Status": "Failed",
                    "Note": str(exc),
                }
            )

    report = pd.DataFrame(report_rows)
    if not report.empty:
        manifest_columns = [
            "VariableName",
            "OriginalFile",
            "SavedFile",
            "OriginalSavedFile",
            "DateColumn",
            "ValueColumn",
            "Coverage",
            "EarliestDate",
            "LatestDate",
            "Status",
            "Note",
        ]
        existing_manifest = load_excel_if_exists(PATHS["uploaded_variable_manifest"])
        manifest = report[[column for column in manifest_columns if column in report.columns]].copy()
        if existing_manifest is not None and not existing_manifest.empty:
            manifest = pd.concat([existing_manifest, manifest], ignore_index=True)
            manifest = manifest.drop_duplicates(subset=["VariableName"], keep="last")
        manifest.to_excel(PATHS["uploaded_variable_manifest"], index=False)
        report.to_excel(PATHS["uploaded_variable_quality_report"], index=False)
    return saved_paths, report


def run_merge_uploaded_variables(options: dict[str, Any]) -> pd.DataFrame | None:
    """Merge uploaded local variables into model_ready_data when enabled."""
    if not options.get("use_uploaded_local_data_first"):
        return None
    merge_uploaded = import_function(
        "src.feature_selector",
        "merge_uploaded_variables_into_model_ready",
    )
    return merge_uploaded(prefer_uploaded=True)


def truthy_value(value: Any) -> bool:
    """Return a reliable boolean for values read back from Excel."""
    if value is None:
        return False
    try:
        if pd.isna(value):
            return False
    except (TypeError, ValueError):
        pass
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y"}
    return bool(value)


def format_date_text(value: Any) -> str:
    """Format one date-like value for status tables."""
    timestamp = pd.to_datetime(value, errors="coerce")
    return "" if pd.isna(timestamp) else timestamp.strftime("%Y-%m-%d")


def business_day_count(start_date: Any, end_date: Any) -> int:
    """Count weekday trading days in a requested date interval."""
    start = pd.to_datetime(start_date, errors="coerce")
    end = pd.to_datetime(end_date, errors="coerce")
    if pd.isna(start) or pd.isna(end) or start > end:
        return 0
    return int(len(pd.bdate_range(start.normalize(), end.normalize())))


def pre_event_window_bounds(
    event_start_date: Any,
    trading_days: int,
) -> tuple[pd.Timestamp | pd.NaT, pd.Timestamp | pd.NaT]:
    """Return the requested pre-event window using only a trading-day count."""
    event_start = pd.to_datetime(event_start_date, errors="coerce")
    if pd.isna(event_start):
        return pd.NaT, pd.NaT
    periods = max(1, int(trading_days or DEFAULT_PRE_EVENT_WINDOW_TRADING_DAYS))
    window_end = event_start.normalize() - pd.offsets.BDay(1)
    window_dates = pd.bdate_range(end=window_end, periods=periods)
    if window_dates.empty:
        return pd.NaT, pd.NaT
    return pd.Timestamp(window_dates.min()).normalize(), pd.Timestamp(window_dates.max()).normalize()


def normalised_available_dates(data: pd.DataFrame | None) -> pd.Series:
    """Return sorted unique dates from a dataframe with a Date column."""
    if data is None or "Date" not in data.columns:
        return pd.Series(dtype="datetime64[ns]")
    dates = pd.to_datetime(data["Date"], errors="coerce").dropna().dt.normalize()
    if dates.empty:
        return pd.Series(dtype="datetime64[ns]")
    return pd.Series(sorted(dates.drop_duplicates().tolist()), dtype="datetime64[ns]")


def first_available_date_on_or_after(dates: pd.Series, start_date: Any) -> pd.Timestamp | pd.NaT:
    """Return the first available date on or after a boundary."""
    start = pd.to_datetime(start_date, errors="coerce")
    if pd.isna(start) or dates.empty:
        return pd.NaT
    candidates = dates[dates >= start.normalize()]
    return pd.NaT if candidates.empty else pd.Timestamp(candidates.iloc[0]).normalize()


def last_available_date_on_or_before(dates: pd.Series, end_date: Any) -> pd.Timestamp | pd.NaT:
    """Return the last available date on or before a boundary."""
    end = pd.to_datetime(end_date, errors="coerce")
    if pd.isna(end) or dates.empty:
        return pd.NaT
    candidates = dates[dates <= end.normalize()]
    return pd.NaT if candidates.empty else pd.Timestamp(candidates.iloc[-1]).normalize()


def available_trading_day_count(dates: pd.Series, start_date: Any, end_date: Any) -> int:
    """Count available rows in the shared model-data calendar."""
    start = pd.to_datetime(start_date, errors="coerce")
    end = pd.to_datetime(end_date, errors="coerce")
    if pd.isna(start) or pd.isna(end) or start > end or dates.empty:
        return 0
    return int(((dates >= start.normalize()) & (dates <= end.normalize())).sum())


def split_cleaned_event_windows(
    available_dates: pd.Series,
    selected_start: Any,
    selected_end: Any,
    selected_window_start: Any,
    selected_window_end: Any,
) -> dict[str, Any]:
    """Split pre-event and event windows after strict complete-case date cleaning."""
    dates = pd.to_datetime(available_dates, errors="coerce").dropna().dt.normalize()
    dates = pd.Series(sorted(dates.drop_duplicates().tolist()), dtype="datetime64[ns]")
    if dates.empty:
        return {
            "event_start": pd.NaT,
            "event_end": pd.NaT,
            "event_days": 0,
            "window_start": pd.NaT,
            "window_end": pd.NaT,
            "window_days": 0,
            "removed_gap_business_days": 0,
        }

    selected_start_ts = pd.to_datetime(selected_start, errors="coerce")
    selected_end_ts = pd.to_datetime(selected_end, errors="coerce")
    selected_window_start_ts = pd.to_datetime(selected_window_start, errors="coerce")
    selected_window_end_ts = pd.to_datetime(selected_window_end, errors="coerce")
    if pd.isna(selected_start_ts):
        selected_start_ts = dates.iloc[0]
    if pd.isna(selected_end_ts):
        selected_end_ts = dates.iloc[-1]
    if pd.isna(selected_window_end_ts):
        selected_window_end_ts = selected_start_ts.normalize() - pd.offsets.BDay(1)
    if pd.isna(selected_window_start_ts):
        selected_window_start_ts = dates.iloc[0]

    event_start = first_available_date_on_or_after(dates, selected_start_ts)
    event_end = last_available_date_on_or_before(dates, selected_end_ts)
    if pd.isna(event_start) or pd.isna(event_end) or event_start > event_end:
        event_start = dates.iloc[0]
        event_end = dates.iloc[-1]

    selected_window_start_ts = selected_window_start_ts.normalize()
    selected_window_end_ts = min(
        selected_window_end_ts.normalize(),
        pd.Timestamp(event_start).normalize() - pd.offsets.BDay(1),
    )
    window_dates = dates[
        (dates >= selected_window_start_ts)
        & (dates <= selected_window_end_ts)
    ]
    if window_dates.empty:
        window_start = pd.NaT
        window_end = pd.NaT
        window_days = 0
        removed_gap_days = 0
    else:
        window_start = pd.Timestamp(window_dates.iloc[0]).normalize()
        window_end = pd.Timestamp(window_dates.iloc[-1]).normalize()
        window_days = int(len(window_dates))
        removed_gap_days = business_day_count(
            pd.Timestamp(window_end) + pd.offsets.BDay(1),
            pd.Timestamp(event_start) - pd.offsets.BDay(1),
        )

    return {
        "event_start": pd.Timestamp(event_start).normalize(),
        "event_end": pd.Timestamp(event_end).normalize(),
        "event_days": available_trading_day_count(dates, event_start, event_end),
        "window_start": window_start,
        "window_end": window_end,
        "window_days": window_days,
        "removed_gap_business_days": int(removed_gap_days),
    }


def optional_float(value: Any) -> float | None:
    """Coerce one scalar to float, preserving missing values as None."""
    parsed = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    return None if pd.isna(parsed) else float(parsed)


def optional_text(value: Any) -> str:
    """Coerce one scalar to display text, preserving missing values as empty text."""
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    return str(value)


def numbered_columns(data: pd.DataFrame, prefix: str) -> list[str]:
    """Return columns like WTI_IMF1, WTI_IMF2 sorted by numeric suffix."""
    columns: list[tuple[int, str]] = []
    for column in data.columns:
        text = str(column)
        if not text.startswith(prefix):
            continue
        suffix = text.replace(prefix, "", 1)
        if suffix.isdigit():
            columns.append((int(suffix), text))
    return [column for _, column in sorted(columns)]


def latest_rows_by_variable(data: pd.DataFrame, required_columns: set[str]) -> pd.DataFrame:
    """Return the latest row per variable from a status-like table."""
    if data.empty or not required_columns.issubset(data.columns):
        return pd.DataFrame()
    latest = data.copy()
    latest["_RowOrder"] = range(len(latest))
    latest["Variable"] = latest["Variable"].astype(str)
    latest = latest.sort_values("_RowOrder").groupby("Variable", as_index=False).tail(1)
    return latest.drop(columns=["_RowOrder"], errors="ignore")


def describe_update_outcome(status_value: Any, auto_download: bool) -> str:
    """Map internal variable-pool statuses to a user-facing outcome."""
    status_text = optional_text(status_value).strip()
    status_key = status_text.lower()
    if status_key == "downloaded":
        return "Auto-updated"
    if status_key == "existingmodelready":
        return "Core/model-ready data"
    if status_key == "localuploadloaded":
        return "Local upload loaded"
    if status_key.startswith("loadedcache"):
        return "Fresh cache used"
    if status_key in {"failed", "missingapikey"}:
        return "Auto-update failed" if auto_download else "Data unavailable"
    if status_key == "localuploadmissing":
        return "Local upload missing"
    if status_key == "noautomaticsource":
        return "No automatic source"
    if status_key == "registryonly":
        return "Registry only"
    if status_key == "notselected":
        return "Not selected"
    return status_text or "Unknown"


def build_variable_update_review_table(
    status: pd.DataFrame,
    coverage: pd.DataFrame,
    quality: pd.DataFrame,
    registry: pd.DataFrame,
    selected_variables: list[str] | None = None,
) -> pd.DataFrame:
    """Build the manual-review table shown before the next workflow step."""
    selected_order = [str(variable) for variable in selected_variables or [] if str(variable).strip()]
    if not selected_order and {"Variable", "SelectedForPool"}.issubset(registry.columns):
        selected_rows = registry[registry["SelectedForPool"].apply(truthy_value)]
        selected_order = selected_rows["Variable"].dropna().astype(str).tolist()
    if not selected_order and "Variable" in registry.columns:
        selected_order = registry["Variable"].dropna().astype(str).tolist()
    selected_order = list(dict.fromkeys(selected_order))

    latest_status = latest_rows_by_variable(status, {"Variable", "Status"})
    latest_quality = latest_rows_by_variable(quality, {"Variable", "Action"})
    status_lookup = (
        latest_status.set_index("Variable").to_dict(orient="index")
        if not latest_status.empty
        else {}
    )
    quality_lookup = (
        latest_quality.set_index("Variable").to_dict(orient="index")
        if not latest_quality.empty
        else {}
    )
    coverage_lookup = (
        coverage.assign(Variable=coverage["Variable"].astype(str)).set_index("Variable").to_dict(orient="index")
        if not coverage.empty and "Variable" in coverage.columns
        else {}
    )
    registry_lookup = (
        registry.assign(Variable=registry["Variable"].astype(str)).set_index("Variable").to_dict(orient="index")
        if not registry.empty and "Variable" in registry.columns
        else {}
    )

    rows: list[dict[str, Any]] = []
    for variable in selected_order:
        status_row = status_lookup.get(variable, {})
        coverage_row = coverage_lookup.get(variable, {})
        quality_row = quality_lookup.get(variable, {})
        registry_row = registry_lookup.get(variable, {})
        auto_download = truthy_value(
            status_row.get("AutoDownload", coverage_row.get("AutoDownload", registry_row.get("AutoDownload", False)))
        )
        status_value = status_row.get("Status", "")
        coverage_value = optional_float(coverage_row.get("Coverage"))
        missing_count_value = optional_float(coverage_row.get("MissingCount"))
        missing_count = None if missing_count_value is None else int(missing_count_value)
        fully_covers = bool(
            coverage_value is not None
            and coverage_value >= 0.999999
            and missing_count == 0
        )
        stale_days_value = optional_float(coverage_row.get("StaleDays", status_row.get("StaleDays")))
        rows.append(
            {
                "Variable": variable,
                "AutoDownload": auto_download,
                "UpdateResult": describe_update_outcome(status_value, auto_download),
                "Status": optional_text(status_value),
                "FullyCoversRequiredDates": fully_covers,
                "DateCoverage": "Complete" if fully_covers else "Incomplete",
                "Coverage": coverage_value,
                "CoveragePercent": "" if coverage_value is None else f"{coverage_value * 100:.1f}%",
                "MissingCount": missing_count,
                "EarliestDate": format_date_text(
                    coverage_row.get("EarliestDate", status_row.get("EarliestDate"))
                ),
                "LatestDate": format_date_text(
                    coverage_row.get("LatestDate", status_row.get("LatestDate"))
                ),
                "StaleDays": None if stale_days_value is None else int(stale_days_value),
                "QualityAction": optional_text(quality_row.get("Action", "")),
                "QualityReason": optional_text(quality_row.get("Reason", "")),
                "ActualSource": optional_text(status_row.get("ActualSource", "")),
                "Note": optional_text(status_row.get("Note", coverage_row.get("Note", ""))),
            }
        )
    return pd.DataFrame(rows)


def summarize_variable_pool_update(
    required_start_date: str | pd.Timestamp | None = None,
    required_end_date: str | pd.Timestamp | None = None,
    selected_start_date: str | pd.Timestamp | None = None,
    selected_end_date: str | pd.Timestamp | None = None,
    selected_variables: list[str] | None = None,
) -> dict[str, Any]:
    """Validate variable-pool outputs and summarize the update outcome."""
    required_paths = [
        PATHS["expanded_variable_pool"],
        PATHS["variable_pool_download_status"],
        PATHS["variable_pool_coverage_report"],
        PATHS["variable_pool_quality_report"],
        PATHS["variable_registry_table"],
    ]
    missing_paths = [path for path in required_paths if not path.exists()]
    if missing_paths:
        missing_names = ", ".join(path.name for path in missing_paths)
        raise FileNotFoundError(f"Variable-pool output files were not created: {missing_names}")

    expanded = load_excel_if_exists(PATHS["expanded_variable_pool"])
    status = load_excel_if_exists(PATHS["variable_pool_download_status"])
    coverage = load_excel_if_exists(PATHS["variable_pool_coverage_report"])
    quality = load_excel_if_exists(PATHS["variable_pool_quality_report"])
    registry = load_excel_if_exists(PATHS["variable_registry_table"])
    date_alignment = load_excel_if_exists(PATHS["variable_pool_date_alignment_report"])
    if expanded is None or status is None or coverage is None or quality is None or registry is None:
        raise ValueError("Variable-pool output files exist but could not be read.")

    summary_warnings: list[str] = []
    date_alignment_note = ""
    effective_start = pd.NaT
    effective_end = pd.NaT
    common_start = pd.NaT
    common_end = pd.NaT
    common_window_status = ""
    common_start_limited_by = ""
    common_end_limited_by = ""
    if "Date" in expanded.columns:
        effective_dates = pd.to_datetime(expanded["Date"], errors="coerce").dropna()
        if not effective_dates.empty:
            effective_start = effective_dates.min()
            effective_end = effective_dates.max()
            common_start = effective_start
            common_end = effective_end

    selected_start = pd.to_datetime(selected_start_date, errors="coerce")
    selected_end = pd.to_datetime(selected_end_date, errors="coerce")
    selected_window_fully_covered = True
    selected_window_coverage_note = ""
    if pd.notna(selected_start) and pd.notna(selected_end) and pd.notna(effective_start) and pd.notna(effective_end):
        selected_window_fully_covered = bool(effective_start <= selected_start and effective_end >= selected_end)
        if not selected_window_fully_covered:
            selected_window_coverage_note = (
                "Prepared common data window "
                f"{effective_start:%Y-%m-%d} to {effective_end:%Y-%m-%d} "
                "does not fully cover the initially selected analysis window "
                f"{selected_start:%Y-%m-%d} to {selected_end:%Y-%m-%d}."
            )
            summary_warnings.append(selected_window_coverage_note)
    if isinstance(date_alignment, pd.DataFrame) and not date_alignment.empty:
        if (
            "CommonWindowStatus" in date_alignment.columns
            and date_alignment["CommonWindowStatus"].astype(str).eq("NoOverlap").any()
        ):
            summary_warnings.append(
                "Selected variables do not share an overlapping non-missing date window."
            )
        if "Status" in date_alignment.columns:
            no_data_variables = date_alignment.loc[
                date_alignment["Status"].astype(str).eq("NoData"),
                "Variable",
            ].dropna().astype(str).tolist()
            if no_data_variables:
                summary_warnings.append(
                    "No usable values were found for: " + ", ".join(no_data_variables)
                )
        if "AlignmentNote" in date_alignment.columns:
            alignment_notes = date_alignment["AlignmentNote"].dropna().astype(str).unique().tolist()
            if alignment_notes:
                date_alignment_note = alignment_notes[0]
        first_alignment_row = date_alignment.iloc[0]
        common_window_status = optional_text(first_alignment_row.get("CommonWindowStatus", ""))
        if "CommonStartDate" in date_alignment.columns:
            alignment_common_start = pd.to_datetime(first_alignment_row.get("CommonStartDate"), errors="coerce")
            if pd.notna(alignment_common_start):
                common_start = alignment_common_start
        if "CommonEndDate" in date_alignment.columns:
            alignment_common_end = pd.to_datetime(first_alignment_row.get("CommonEndDate"), errors="coerce")
            if pd.notna(alignment_common_end):
                common_end = alignment_common_end
        common_start_limited_by = optional_text(first_alignment_row.get("CommonStartLimitedBy", ""))
        common_end_limited_by = optional_text(first_alignment_row.get("CommonEndLimitedBy", ""))

    selected_registry = registry.copy()
    if "SelectedForPool" in selected_registry.columns:
        selected_registry = selected_registry[selected_registry["SelectedForPool"].apply(truthy_value)]
    if selected_variables:
        selected_set = {str(variable) for variable in selected_variables}
        selected_registry = selected_registry[selected_registry["Variable"].astype(str).isin(selected_set)]
    auto_variables = (
        selected_registry.loc[selected_registry["AutoDownload"].apply(truthy_value), "Variable"].astype(str).tolist()
        if "AutoDownload" in selected_registry.columns and "Variable" in selected_registry.columns
        else []
    )
    if not auto_variables:
        summary_warnings.append("No auto-download variables are selected, or registry fields are unavailable.")

    review_table = build_variable_update_review_table(
        status=status,
        coverage=coverage,
        quality=quality,
        registry=registry,
        selected_variables=selected_variables,
    )
    if not review_table.empty:
        PATHS["variable_pool_update_review_report"].parent.mkdir(parents=True, exist_ok=True)
        review_table.to_excel(PATHS["variable_pool_update_review_report"], index=False)

    if {"Variable", "Status"}.issubset(status.columns):
        auto_status = status[status["Variable"].astype(str).isin(auto_variables)].copy()
        latest_auto_status = latest_rows_by_variable(auto_status, {"Variable", "Status"})
        status_by_variable = (
            latest_auto_status.set_index("Variable").to_dict(orient="index")
            if not latest_auto_status.empty
            else {}
        )
        successful_names = []
        failed_names = []
        auto_updated_names = []
        usable_statuses = {
            "downloaded",
            "existingmodelready",
            "loadedfreshcache",
            "loadedcacheaftersourcefailure",
            "loadedcacheaftereiafailure",
            "loadedcachemissingapikey",
        }
        failure_statuses = {"failed", "missingapikey", "noautomaticsource"}
        for variable in auto_variables:
            status_value = optional_text(status_by_variable.get(variable, {}).get("Status", "")).lower()
            if status_value == "downloaded":
                auto_updated_names.append(variable)
            if status_value in usable_statuses:
                successful_names.append(variable)
            elif status_value in failure_statuses:
                failed_names.append(variable)
    else:
        summary_warnings.append("Download status log is missing Variable or Status columns.")
        auto_status = pd.DataFrame()
        successful_names = []
        failed_names = []
        auto_updated_names = []

    if {"Variable", "Action"}.issubset(quality.columns):
        passed_quality = quality[quality["Action"].astype(str).str.lower() == "kept"]
        dropped_quality = quality[quality["Action"].astype(str).str.lower() != "kept"]
        passed_auto_quality = passed_quality[
            passed_quality["Variable"].astype(str).isin(auto_variables)
        ]
    else:
        summary_warnings.append("Quality filter report is missing Variable or Action columns.")
        passed_quality = pd.DataFrame()
        dropped_quality = pd.DataFrame()
        passed_auto_quality = pd.DataFrame()

    added_columns = [
        variable
        for variable in auto_variables
        if variable in expanded.columns and expanded[variable].notna().any()
    ]
    passed_quality_names = (
        passed_quality["Variable"].astype(str).tolist()
        if "Variable" in passed_quality.columns
        else []
    )
    auto_attempts = int(len(auto_variables))
    successful_count = int(len(successful_names))
    failed_count = int(len(failed_names))
    passed_quality_count = int(len(passed_quality))
    dropped_count = int(len(dropped_quality))
    passed_auto_quality_count = int(len(passed_auto_quality))
    full_coverage_count = 0
    incomplete_coverage_count = 0
    incomplete_coverage_names: list[str] = []
    if not review_table.empty and "FullyCoversRequiredDates" in review_table.columns:
        full_coverage_count = int(review_table["FullyCoversRequiredDates"].sum())
        incomplete = review_table[~review_table["FullyCoversRequiredDates"].astype(bool)]
        incomplete_coverage_count = int(len(incomplete))
        incomplete_coverage_names = incomplete["Variable"].astype(str).tolist()
    return {
        "auto_download_attempts": auto_attempts,
        "auto_updated_variables": int(len(auto_updated_names)),
        "successful_variables": successful_count,
        "failed_variables": failed_count,
        "passed_quality_filter": passed_quality_count,
        "dropped_variables": dropped_count,
        "auto_updated_variables_count": int(len(auto_updated_names)),
        "successful_variables_count": successful_count,
        "failed_variables_count": failed_count,
        "passed_quality_filter_count": passed_quality_count,
        "dropped_variables_count": dropped_count,
        "passed_auto_quality_count": passed_auto_quality_count,
        "full_coverage_count": full_coverage_count,
        "incomplete_coverage_count": incomplete_coverage_count,
        "auto_updated_variable_names": auto_updated_names,
        "successful_variable_names": successful_names,
        "failed_variable_names": failed_names,
        "incomplete_coverage_variable_names": incomplete_coverage_names,
        "passed_quality_variables": passed_quality_names,
        "added_auto_columns": added_columns,
        "variable_update_review_table": review_table,
        "expanded_columns": expanded.columns.astype(str).tolist(),
        "expanded_pool_path": str(PATHS["expanded_variable_pool"]),
        "download_status_path": str(PATHS["variable_pool_download_status"]),
        "coverage_report_path": str(PATHS["variable_pool_coverage_report"]),
        "quality_filter_report_path": str(PATHS["variable_pool_quality_report"]),
        "update_review_report_path": str(PATHS["variable_pool_update_review_report"]),
        "date_alignment_report_path": str(PATHS["variable_pool_date_alignment_report"]),
        "registry_path": str(PATHS["variable_registry_table"]),
        "required_start_date": format_date_text(required_start_date),
        "required_end_date": format_date_text(required_end_date),
        "selected_start_date": format_date_text(selected_start_date),
        "selected_end_date": format_date_text(selected_end_date),
        "effective_start_date": format_date_text(effective_start),
        "effective_end_date": format_date_text(effective_end),
        "common_data_start_date": format_date_text(common_start),
        "common_data_end_date": format_date_text(common_end),
        "common_window_status": common_window_status,
        "common_start_limited_by": common_start_limited_by,
        "common_end_limited_by": common_end_limited_by,
        "selected_window_fully_covered": selected_window_fully_covered,
        "selected_window_coverage_note": selected_window_coverage_note,
        "date_alignment_note": date_alignment_note,
        "date_alignment_table": date_alignment if isinstance(date_alignment, pd.DataFrame) else pd.DataFrame(),
        "summary_warnings": summary_warnings,
    }


def dataframe_from_summary_value(value: Any) -> pd.DataFrame:
    """Convert a summary payload to a DataFrame without mutating the source."""
    if isinstance(value, pd.DataFrame):
        return value.copy()
    if value is None:
        return pd.DataFrame()
    try:
        return pd.DataFrame(value)
    except ValueError:
        return pd.DataFrame()


def build_data_refresh_period_summary_table(
    summary: dict[str, Any],
    prepared_data: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Build the period table written to the data-refresh workbook."""
    available_dates = normalised_available_dates(prepared_data)

    def trading_days(start_value: Any, end_value: Any, fallback: Any = None) -> int:
        fallback_number = pd.to_numeric(pd.Series([fallback]), errors="coerce").iloc[0]
        if not available_dates.empty:
            count = available_trading_day_count(available_dates, start_value, end_value)
            if count:
                return count
        if pd.notna(fallback_number):
            return int(fallback_number)
        return business_day_count(start_value, end_value)

    rows = [
        {
            "Period": "Requested pre-event window",
            "Start": summary.get("requested_window_start_date", ""),
            "End": summary.get("requested_window_end_date", ""),
            "TradingDays": int(summary.get("requested_window_trading_days", 0) or 0),
            "Basis": "Requested business-day window before strict complete-case cleaning.",
        },
        {
            "Period": "Requested event window",
            "Start": summary.get("requested_event_start_date", summary.get("selected_start_date", "")),
            "End": summary.get("requested_event_end_date", summary.get("selected_end_date", "")),
            "TradingDays": int(summary.get("requested_event_trading_days", 0) or 0),
            "Basis": "User-selected event window before strict complete-case cleaning.",
        },
        {
            "Period": "Cleaned pre-event window",
            "Start": summary.get("effective_window_start_date", ""),
            "End": summary.get("effective_window_end_date", ""),
            "TradingDays": trading_days(
                summary.get("effective_window_start_date", ""),
                summary.get("effective_window_end_date", ""),
                summary.get("effective_window_trading_days", 0),
            ),
            "Basis": "Rows retained after all selected variables are aligned and missing rows are removed.",
        },
        {
            "Period": "Cleaned event window",
            "Start": summary.get("effective_event_start_date", summary.get("effective_start_date", "")),
            "End": summary.get("effective_event_end_date", summary.get("effective_end_date", "")),
            "TradingDays": trading_days(
                summary.get("effective_event_start_date", summary.get("effective_start_date", "")),
                summary.get("effective_event_end_date", summary.get("effective_end_date", "")),
                summary.get("effective_event_trading_days", 0),
            ),
            "Basis": "Rows retained inside the event window after strict complete-case cleaning.",
        },
        {
            "Period": "Prepared common data window",
            "Start": summary.get("common_data_start_date", summary.get("effective_start_date", "")),
            "End": summary.get("common_data_end_date", summary.get("effective_end_date", "")),
            "TradingDays": trading_days(
                summary.get("common_data_start_date", summary.get("effective_start_date", "")),
                summary.get("common_data_end_date", summary.get("effective_end_date", "")),
                None,
            ),
            "Basis": "Full prepared table after selected variables are retained and missing rows are removed.",
        },
    ]
    return pd.DataFrame(rows)


def build_variable_update_range_table(summary: dict[str, Any]) -> pd.DataFrame:
    """Build a compact per-variable update range table for workbook review."""
    review_table = dataframe_from_summary_value(summary.get("variable_update_review_table"))
    if review_table.empty:
        return pd.DataFrame()

    columns = [
        "Variable",
        "AutoDownload",
        "UpdateResult",
        "Status",
        "EarliestDate",
        "LatestDate",
        "MissingCount",
        "CoveragePercent",
        "QualityAction",
        "QualityReason",
        "ActualSource",
        "Note",
    ]
    range_table = review_table[[column for column in columns if column in review_table.columns]].copy()
    range_table = range_table.rename(
        columns={
            "EarliestDate": "AvailableStart",
            "LatestDate": "AvailableEnd",
        }
    )
    return range_table


def write_data_refresh_preparation_workbook(
    summary: dict[str, Any],
    prepared_data: pd.DataFrame | None = None,
) -> Path:
    """Write the first-step data-refresh and preparation review workbook."""
    workbook_path = PATHS["data_refresh_preparation_workbook"]
    workbook_path.parent.mkdir(parents=True, exist_ok=True)
    prepared = prepared_data.copy() if isinstance(prepared_data, pd.DataFrame) else load_excel_if_exists(PATHS["expanded_variable_pool"])
    if prepared is None:
        prepared = pd.DataFrame()

    sheets: dict[str, pd.DataFrame] = {
        "PreparedData": prepared,
        "PeriodSummary": build_data_refresh_period_summary_table(summary, prepared),
        "VariableUpdateRanges": build_variable_update_range_table(summary),
    }
    optional_sheets = {
        "DownloadStatus": PATHS["variable_pool_download_status"],
        "CoverageReport": PATHS["variable_pool_coverage_report"],
        "QualityReport": PATHS["variable_pool_quality_report"],
        "DateAlignment": PATHS["variable_pool_date_alignment_report"],
        "DataSourceLog": PATHS["data_source_log"],
    }
    for sheet_name, path in optional_sheets.items():
        table = load_excel_if_exists(path)
        if table is not None and not table.empty:
            sheets[sheet_name] = table

    with pd.ExcelWriter(workbook_path, engine="openpyxl") as writer:
        for sheet_name, table in sheets.items():
            table.to_excel(writer, sheet_name=sheet_name[:31], index=False)
    return workbook_path


def display_variable_pool_update_result(summary: dict[str, Any]) -> None:
    """Show a readable variable-pool update summary in Streamlit."""
    auto_attempts = int(summary.get("auto_download_attempts", 0) or 0)
    auto_updated_count = int(summary.get("auto_updated_variables_count", 0) or 0)
    successful_count = int(
        summary.get("successful_variables_count", summary.get("successful_variables", 0)) or 0
    )
    failed_count = int(
        summary.get("failed_variables_count", summary.get("failed_variables", 0)) or 0
    )
    passed_quality_count = int(
        summary.get("passed_quality_filter_count", summary.get("passed_quality_filter", 0)) or 0
    )
    passed_auto_quality_count = int(summary.get("passed_auto_quality_count", 0) or 0)
    full_coverage_count = int(summary.get("full_coverage_count", 0) or 0)
    incomplete_coverage_count = int(summary.get("incomplete_coverage_count", 0) or 0)
    auto_updated_names = summary.get("auto_updated_variable_names", []) or []
    failed_names = summary.get("failed_variable_names", []) or []
    incomplete_coverage_names = summary.get("incomplete_coverage_variable_names", []) or []
    summary_warnings = summary.get("summary_warnings", []) or []
    required_start = str(summary.get("required_start_date") or "")
    required_end = str(summary.get("required_end_date") or "")
    selected_start = str(summary.get("selected_start_date") or "")
    selected_end = str(summary.get("selected_end_date") or "")
    effective_start = str(summary.get("effective_start_date") or "")
    effective_end = str(summary.get("effective_end_date") or "")
    requested_window_days = int(summary.get("requested_window_trading_days", 0) or 0)
    requested_window_start = str(summary.get("requested_window_start_date") or "")
    requested_window_end = str(summary.get("requested_window_end_date") or "")
    requested_event_start = str(summary.get("requested_event_start_date") or selected_start)
    requested_event_end = str(summary.get("requested_event_end_date") or selected_end)
    requested_event_days = int(summary.get("requested_event_trading_days", 0) or 0)
    effective_window_start = str(summary.get("effective_window_start_date") or "")
    effective_window_end = str(summary.get("effective_window_end_date") or "")
    effective_window_days = int(summary.get("effective_window_trading_days", 0) or 0)
    effective_event_start = str(summary.get("effective_event_start_date") or "")
    effective_event_end = str(summary.get("effective_event_end_date") or "")
    effective_event_days = int(summary.get("effective_event_trading_days", 0) or 0)
    common_data_start = str(summary.get("common_data_start_date") or effective_start)
    common_data_end = str(summary.get("common_data_end_date") or effective_end)
    common_window_status = str(summary.get("common_window_status") or "")
    common_start_limited_by = str(summary.get("common_start_limited_by") or "")
    common_end_limited_by = str(summary.get("common_end_limited_by") or "")
    selected_window_coverage_note = str(summary.get("selected_window_coverage_note") or "")
    selected_window_fully_covered = bool(summary.get("selected_window_fully_covered", True))
    date_alignment_note = str(summary.get("date_alignment_note") or "")
    cleaned_gap_note = str(summary.get("cleaned_window_event_gap_note") or "")
    cleaned_shortfall_note = str(summary.get("cleaned_window_shortfall_note") or "")
    raw_review_table = summary.get("variable_update_review_table")
    review_table = (
        raw_review_table
        if isinstance(raw_review_table, pd.DataFrame)
        else pd.DataFrame(raw_review_table or [])
    )
    selected_count = int(len(review_table)) if not review_table.empty else 0
    expanded = load_excel_if_exists(PATHS["expanded_variable_pool"])
    workbook_path_text = str(summary.get("data_refresh_preparation_workbook_path") or "")

    cols = st.columns(6)
    cols[0].metric("Selected variables", selected_count)
    cols[1].metric("Auto-refresh attempts", auto_attempts)
    cols[2].metric("Fresh online updates", auto_updated_count)
    cols[3].metric("Auto-refresh failures", failed_count)
    cols[4].metric("Full pre-clean coverage", full_coverage_count)
    cols[5].metric("Kept for analysis", passed_quality_count)
    if selected_count:
        st.caption(
            f"{auto_attempts} selected variables require an online refresh attempt. "
            f"{selected_count} selected variables are checked after combining targets, existing data, "
            "online refreshes, local uploads, and any usable prior app data."
        )
        st.caption(
            "Rows marked Core/model-ready data are not separate variable-pool downloads; "
            "they are target or core columns already prepared by the market-data step."
        )

    for warning_text in summary_warnings:
        if warning_text in {selected_window_coverage_note, cleaned_shortfall_note}:
            continue
        st.warning(warning_text)

    if required_start and required_end:
        st.caption(f"Requested data refresh period: {required_start} to {required_end}")
    if requested_window_start and requested_window_end:
        st.caption(
            f"Requested pre-event window: {requested_window_start} to {requested_window_end} "
            f"({requested_window_days} business days before strict cleaning)"
        )
    if selected_start and selected_end:
        st.caption(f"Initially selected event window: {selected_start} to {selected_end}")
    period_table = build_data_refresh_period_summary_table(summary, expanded)
    if not period_table.empty:
        st.write("Window and Event Periods")
        st.table(period_table)
    if cleaned_shortfall_note:
        st.warning(cleaned_shortfall_note)
    if cleaned_gap_note:
        st.info(cleaned_gap_note)
    if common_data_start and common_data_end:
        window_cols = st.columns(2)
        window_cols[0].metric("Cleaned common data start", common_data_start)
        window_cols[1].metric("Cleaned common data end", common_data_end)
        st.info(
            "The cleaned common data window is "
            f"{common_data_start} to {common_data_end}. "
            "It is computed after strict complete-case cleaning: the start is the latest first valid date "
            "among retained variables, and the end is the earliest last valid date among retained variables."
        )
        limit_parts = []
        if common_start_limited_by:
            limit_parts.append(f"start limited by: {common_start_limited_by}")
        if common_end_limited_by:
            limit_parts.append(f"end limited by: {common_end_limited_by}")
        if common_window_status:
            limit_parts.append(f"common window status: {common_window_status}")
        if limit_parts:
            st.caption("Common-window limits: " + " | ".join(limit_parts))
        if selected_start and selected_end and not selected_window_fully_covered:
            st.warning(
                f"The initially selected event window was {selected_start} to {selected_end}, "
                f"but the retained variables jointly cover {common_data_start} to {common_data_end}. "
                "VMD, MRGC, and FEVD will use only the complete observations inside the cleaned common window."
            )
    if date_alignment_note:
        st.info(date_alignment_note)

    if auto_updated_names:
        st.success("Automatically updated variables: " + ", ".join(auto_updated_names))
    elif auto_attempts:
        st.info("No selected variable needed a fresh automatic download; existing or cached data may have been used.")

    if failed_names:
        st.error("Automatic update failed for: " + ", ".join(failed_names))
        if not review_table.empty and "Variable" in review_table.columns:
            failed_detail_mask = review_table["Variable"].astype(str).isin([str(name) for name in failed_names])
            if "UpdateResult" in review_table.columns:
                failed_detail_mask |= review_table["UpdateResult"].astype(str).str.contains(
                    "failed",
                    case=False,
                    na=False,
                )
            if "Status" in review_table.columns:
                failed_detail_mask |= review_table["Status"].astype(str).str.contains(
                    "failed",
                    case=False,
                    na=False,
                )
            failed_details = review_table.loc[failed_detail_mask].copy()
            detail_columns = [
                "Variable",
                "UpdateResult",
                "Status",
                "ActualSource",
                "LatestDate",
                "CoveragePercent",
                "Note",
            ]
            detail_columns = [column for column in detail_columns if column in failed_details.columns]
            if detail_columns:
                st.write("Automatic update failure details")
                st.dataframe(failed_details[detail_columns], use_container_width=True, hide_index=True)
    elif auto_attempts:
        st.success("No selected auto-download variable failed.")

    if incomplete_coverage_names:
        st.warning(
            "These selected variables have gaps before strict complete-case cleaning: "
            + ", ".join(incomplete_coverage_names)
            + ". They remain selected; the workflow only removes dates where at least one retained variable is missing."
        )
    elif not review_table.empty:
        st.success("All selected variables fully cover the requested data before strict cleaning.")

    if failed_names:
        st.warning(
            "The variable pool was prepared with available data, but some selected online "
            "variables could not be refreshed. Add a FRED API key, check the network, or "
            "remove the failed variables before running the final analysis."
        )
    elif incomplete_coverage_names:
        st.warning(
            "The variable pool was prepared, but some selected variables have pre-clean date gaps. "
            "Strict complete-case cleaning will remove any date where a retained variable is missing."
        )
    elif successful_count == 0 and auto_attempts:
        st.warning("No selected auto-download variable produced usable online or cached data.")
    elif auto_attempts and passed_auto_quality_count == 0:
        st.warning(
            "Expanded variables were available, but none of the selected auto-download "
            "variables passed the quality filter."
        )
    else:
        st.success("Expanded variable pool is ready for the selected variables.")

    if not review_table.empty:
        st.write("Variable update ranges and date-coverage review")
        display_columns = [
            "Variable",
            "AutoDownload",
            "UpdateResult",
            "Status",
            "DateCoverage",
            "CoveragePercent",
            "MissingCount",
            "EarliestDate",
            "LatestDate",
            "StaleDays",
            "QualityAction",
            "QualityReason",
            "ActualSource",
            "Note",
        ]
        st.dataframe(
            review_table[[column for column in display_columns if column in review_table.columns]],
            use_container_width=True,
            hide_index=True,
        )

    raw_alignment_table = summary.get("date_alignment_table")
    alignment_table = (
        raw_alignment_table
        if isinstance(raw_alignment_table, pd.DataFrame)
        else pd.DataFrame(raw_alignment_table or [])
    )
    if not alignment_table.empty:
        st.write("Variable date-alignment window")
        alignment_columns = [
            "Variable",
            "EarliestDate",
            "LatestDate",
            "NonMissingCount",
            "CommonStartDate",
            "CommonEndDate",
            "CommonStartLimitedBy",
            "CommonEndLimitedBy",
            "CleanedCommonStartDate",
            "CleanedCommonEndDate",
            "CommonWindowStatus",
            "Status",
            "AlignmentNote",
        ]
        st.dataframe(
            alignment_table[[column for column in alignment_columns if column in alignment_table.columns]],
            use_container_width=True,
            hide_index=True,
        )

    status = load_excel_if_exists(PATHS["variable_pool_download_status"])
    quality = load_excel_if_exists(PATHS["variable_pool_quality_report"])
    if workbook_path_text:
        workbook_path = Path(workbook_path_text)
        if workbook_path.exists():
            st.success(f"Data refresh and preparation workbook: {workbook_path}")
            st.download_button(
                "Download Data Refresh and Preparation Workbook",
                data=workbook_path.read_bytes(),
                file_name=workbook_path.name,
                mime=_download_mime(workbook_path),
                key="download_data_refresh_preparation_workbook",
                use_container_width=True,
            )
        else:
            st.warning(f"Data refresh and preparation workbook was expected but is missing: {workbook_path}")
    if expanded is not None:
        st.write("Expanded variable pool preview")
        st.dataframe(expanded.tail(20), use_container_width=True)
    if status is not None:
        st.write("Download status log")
        st.dataframe(status, use_container_width=True)
    if quality is not None:
        st.write("Quality filter report")
        st.dataframe(quality, use_container_width=True)


def quality_filtered_explanatory_variables(
    requested_variables: list[str],
    target_variables: list[str],
) -> tuple[list[str], list[str]]:
    """Keep only explanatory variables that passed the latest pool quality filter."""
    quality = load_excel_if_exists(PATHS["variable_pool_quality_report"])
    if quality is None or quality.empty or "Variable" not in quality.columns:
        return requested_variables, []
    kept_variables = set(
        quality.loc[
            quality.get("Action", pd.Series(index=quality.index, dtype=str)).astype(str).eq("Kept"),
            "Variable",
        ].astype(str)
    )
    target_set = set(target_variables)
    kept = [
        variable
        for variable in requested_variables
        if variable in kept_variables and variable not in target_set
    ]
    dropped = [
        variable
        for variable in requested_variables
        if variable not in kept_variables and variable not in target_set
    ]
    return kept, dropped


def run_paper_replication_setup_workflow(
    options: dict[str, Any],
    status_callback: Any | None = None,
) -> dict[str, Any]:
    """Run the paper workflow through variable-pool update, then pause for review."""
    build_market_dataset = import_function("src.data_fetcher", "build_market_dataset")
    build_expanded_variable_pool = import_function(
        "src.variable_pool",
        "build_expanded_variable_pool",
    )
    prepare_model_data = import_function("src.data_cleaner", "prepare_model_data")

    total_steps = 4

    def report(step: int, message: str, level: str = "info") -> None:
        if status_callback is not None:
            status_callback(message, step, total_steps, level)

    selected_start = pd.to_datetime(options["start_date"])
    selected_end = pd.to_datetime(options["end_date"])
    requested_window_end = pd.to_datetime(
        options.get("window_end_date"),
        errors="coerce",
    )
    if pd.isna(requested_window_end):
        requested_window_end = selected_start.normalize() - pd.offsets.BDay(1)
    requested_window_start = pd.to_datetime(
        options.get("window_start_date"),
        errors="coerce",
    )
    if pd.isna(requested_window_start):
        window_trading_days = int(options.get("window_trading_days", DEFAULT_PRE_EVENT_WINDOW_TRADING_DAYS))
        requested_window_start, requested_window_end = pre_event_window_bounds(
            selected_start,
            window_trading_days,
        )
    else:
        requested_window_start = requested_window_start.normalize()
        requested_window_end = pd.Timestamp(requested_window_end).normalize()
        window_trading_days = max(1, business_day_count(requested_window_start, requested_window_end))
    if pd.notna(requested_window_start) and pd.notna(requested_window_end) and requested_window_start > requested_window_end:
        window_trading_days = int(options.get("window_trading_days", DEFAULT_PRE_EVENT_WINDOW_TRADING_DAYS))
        requested_window_start, requested_window_end = pre_event_window_bounds(
            selected_start,
            window_trading_days,
        )
    if pd.isna(requested_window_start):
        requested_window_start = selected_start
    paper_sample_start_text = requested_window_start.strftime("%Y-%m-%d")
    report(1, "Data refresh and preparation: refreshing market and geopolitical-risk data...")
    build_market_dataset(
        paper_sample_start_text,
        options["end_date"],
        auto_gprd=True,
        force_refresh=True,
        cache_first=False,
    )
    rebuilt_start, rebuilt_end = get_date_range_if_exists(PATHS["clean_market"])
    complete_start, complete_end = get_complete_market_date_range_if_exists(PATHS["clean_market"])
    if rebuilt_start is not None and rebuilt_end is not None:
        refresh_message = (
            "Data refresh completed. "
            f"Clean market data range: {rebuilt_start:%Y-%m-%d} to {rebuilt_end:%Y-%m-%d}."
        )
        if complete_start is not None and complete_end is not None:
            refresh_message += (
                " Complete core-market range: "
                f"{complete_start:%Y-%m-%d} to {complete_end:%Y-%m-%d}."
            )
        else:
            refresh_message += " Complete core-market range could not be verified."
    else:
        refresh_message = "Data refresh completed, but the clean market data range could not be verified."
    report(
        1,
        refresh_message,
        "success",
    )

    report(1, "Data refresh and preparation: checking complete core market data freshness...")
    latest_complete_market_date = assert_core_market_data_fresh(PATHS["clean_market"], options["end_date"])
    report(
        1,
        "Core market data freshness check passed. "
        f"Latest complete core-market row before strict cleaning: {format_date_text(latest_complete_market_date) or 'unavailable'}.",
        "success",
    )

    report(1, "Data refresh and preparation: preparing model-ready data from the refreshed market dataset...")
    prepare_model_data()
    report(1, "Model-ready data prepared.", "success")

    report(1, "Data refresh and preparation: refreshing and aligning the expanded candidate variable pool...")
    expanded = build_expanded_variable_pool(
        start_date=paper_sample_start_text,
        end_date=options["end_date"],
        auto_download=True,
        force_refresh=True,
        prefer_existing=prefer_existing_variable_values(options),
        min_coverage=options["min_data_coverage"],
        selected_variables=options.get("selected_variable_pool"),
        protected_variables=options.get("paper_target_variables"),
    )
    variable_pool_summary = summarize_variable_pool_update(
        required_start_date=paper_sample_start_text,
        required_end_date=options["end_date"],
        selected_start_date=options["start_date"],
        selected_end_date=options["end_date"],
        selected_variables=options.get("selected_variable_pool"),
    )
    variable_pool_summary.update(
        {
            "requested_window_trading_days": int(window_trading_days),
            "requested_window_start_date": format_date_text(requested_window_start),
            "requested_window_end_date": format_date_text(requested_window_end),
            "requested_event_start_date": format_date_text(selected_start),
            "requested_event_end_date": format_date_text(selected_end),
            "requested_event_trading_days": business_day_count(selected_start, selected_end),
        }
    )
    added_columns = []
    if isinstance(expanded, pd.DataFrame):
        added_columns = [
            column
            for column in expanded.columns
            if column not in {"Date", "WTI", "Brent", "GPRD", "Gold", "OVX", "DollarIndex", "TNote10Y"}
        ]
    report(
        1,
        (
            "Expanded variable pool refreshed and merged into model-ready data. "
            f"Additional candidate columns: {', '.join(added_columns) if added_columns else 'none'}."
        ),
        "success" if added_columns else "warning",
    )

    target_variables = list(options.get("paper_target_variables") or [])
    requested_explanatory = list(options.get("paper_explanatory_variables") or [])
    filtered_explanatory, dropped_explanatory = quality_filtered_explanatory_variables(
        requested_explanatory,
        target_variables,
    )
    variable_pool_summary["candidate_variables_for_next_step"] = filtered_explanatory
    variable_pool_summary["dropped_explanatory_variables"] = dropped_explanatory
    if dropped_explanatory:
        report(
            1,
            (
                "The following explanatory variables were excluded before MRGC/FEVD because "
                "they did not pass the data-quality filter: "
                f"{', '.join(dropped_explanatory)}."
            ),
            "warning",
        )
    if not filtered_explanatory:
        report(
            1,
            "No explanatory variable passed the data-quality filter. "
            "Lower the minimum data coverage or select variables with better coverage.",
            "warning",
        )

    effective_options = options.copy()
    paper_sample_start_for_next = paper_sample_start_text
    available_dates = normalised_available_dates(
        expanded if isinstance(expanded, pd.DataFrame) else load_excel_if_exists(PATHS["expanded_variable_pool"])
    )
    effective_start_text = str(variable_pool_summary.get("effective_start_date") or "")
    effective_end_text = str(variable_pool_summary.get("effective_end_date") or "")
    if effective_start_text and effective_end_text:
        effective_start = pd.to_datetime(effective_start_text)
        effective_end = pd.to_datetime(effective_end_text)
        cleaned_split = split_cleaned_event_windows(
            available_dates,
            max(selected_start, effective_start),
            min(selected_end, effective_end),
            requested_window_start,
            requested_window_end,
        )
        adjusted_start = cleaned_split["event_start"]
        adjusted_end = cleaned_split["event_end"]
        effective_window_start = cleaned_split["window_start"]
        effective_window_end = cleaned_split["window_end"]
        effective_window_days = int(cleaned_split["window_days"])
        effective_event_days = int(cleaned_split["event_days"])
        if effective_window_days > 0 and pd.notna(effective_window_start):
            paper_sample_start_for_next = effective_window_start.strftime("%Y-%m-%d")
        else:
            paper_sample_start_for_next = adjusted_start.strftime("%Y-%m-%d")
        effective_options["start_date"] = adjusted_start.strftime("%Y-%m-%d")
        effective_options["end_date"] = adjusted_end.strftime("%Y-%m-%d")
        variable_pool_summary["effective_event_start_date"] = effective_options["start_date"]
        variable_pool_summary["effective_event_end_date"] = effective_options["end_date"]
        variable_pool_summary["effective_event_trading_days"] = int(effective_event_days)
        variable_pool_summary["effective_window_start_date"] = format_date_text(effective_window_start)
        variable_pool_summary["effective_window_end_date"] = format_date_text(effective_window_end)
        variable_pool_summary["effective_window_trading_days"] = int(effective_window_days)
        variable_pool_summary["paper_sample_start_date"] = paper_sample_start_for_next
        summary_warnings = variable_pool_summary.setdefault("summary_warnings", [])
        if effective_window_days < window_trading_days:
            shortfall_note = (
                f"The selected pre-event window ({requested_window_start:%Y-%m-%d} to {requested_window_end:%Y-%m-%d}) "
                f"contains {window_trading_days} business days before strict cleaning, but only "
                f"{effective_window_days} complete observations remain after strict missing-data removal."
            )
            variable_pool_summary["cleaned_window_shortfall_note"] = shortfall_note
            if shortfall_note not in summary_warnings:
                summary_warnings.append(shortfall_note)
        if pd.notna(effective_window_end) and pd.notna(adjusted_start):
            removed_gap_days = int(cleaned_split.get("removed_gap_business_days", 0) or 0)
            if removed_gap_days > 0:
                gap_note = (
                    f"There are {removed_gap_days} business days between the pre-event window end "
                    f"({effective_window_end:%Y-%m-%d}) and the event window start "
                    f"({adjusted_start:%Y-%m-%d}). These dates were removed before period splitting "
                    "because at least one selected retained variable was missing."
                )
                variable_pool_summary["cleaned_window_event_gap_note"] = gap_note
        report(
            1,
            (
                "Prepared cleaned common data window after strict alignment: "
                f"{effective_start:%Y-%m-%d} to {effective_end:%Y-%m-%d}. "
                f"Pre-event window has {effective_window_days} complete observations; "
                f"event window has {effective_event_days} complete observations."
            ),
            "success",
        )
        if not bool(variable_pool_summary.get("selected_window_fully_covered", True)):
            report(1, str(variable_pool_summary.get("selected_window_coverage_note", "")), "warning")

    workbook_path = write_data_refresh_preparation_workbook(
        variable_pool_summary,
        expanded if isinstance(expanded, pd.DataFrame) else load_excel_if_exists(PATHS["expanded_variable_pool"]),
    )
    variable_pool_summary["data_refresh_preparation_workbook_path"] = str(workbook_path)
    report(
        1,
        f"Data refresh and preparation workbook created: {workbook_path.name}.",
        "success",
    )

    return {
        "options": effective_options,
        "paper_sample_start": paper_sample_start_for_next,
        "variable_pool_summary": variable_pool_summary,
    }


def run_paper_replication_after_variable_confirmation(
    options: dict[str, Any],
    paper_sample_start: str,
    status_callback: Any | None = None,
) -> dict[str, pd.DataFrame]:
    """Continue the paper workflow after the user confirms variable update results."""
    run_paper_replication_pipeline = import_function(
        "src.paper_replication",
        "run_paper_replication_pipeline",
    )

    total_steps = 4

    def report(step: int, message: str, level: str = "info") -> None:
        if status_callback is not None:
            status_callback(message, step, total_steps, level)

    target_variables = list(options.get("paper_target_variables") or [])
    requested_explanatory = list(options.get("paper_explanatory_variables") or [])
    filtered_explanatory, dropped_explanatory = quality_filtered_explanatory_variables(
        requested_explanatory,
        target_variables,
    )
    if dropped_explanatory:
        report(
            4,
            (
                "The following explanatory variables were excluded before MRGC/FEVD because "
                "they did not pass the data-quality filter: "
                f"{', '.join(dropped_explanatory)}."
            ),
            "warning",
        )
    if not filtered_explanatory:
        raise ValueError(
            "No explanatory variable passed the data-quality filter. "
            "Lower the minimum data coverage or select variables with better coverage."
        )

    report(
        4,
        "Running final TVP/VAR FEVD contribution and figures using the confirmed h...",
    )
    return run_paper_replication_pipeline(
        start_date=paper_sample_start,
        end_date=options["end_date"],
        event_start_date=options["start_date"],
        allow_thesis_source=False,
        use_thesis_vmd_cache=False,
        target_variables=target_variables,
        candidate_variables=filtered_explanatory,
        vmd_k=int(options.get("vmd_imf_count", 4)),
    )


def run_paper_replication_vmd_review(
    options: dict[str, Any],
    paper_sample_start: str,
    status_callback: Any | None = None,
) -> dict[str, Any]:
    """Run VMD decompositions for selected variables and pause for review."""
    build_vmd_center_frequency_review = import_function(
        "src.paper_replication",
        "build_vmd_center_frequency_review",
    )

    total_steps = 4

    def report(step: int, message: str, level: str = "info") -> None:
        if status_callback is not None:
            status_callback(message, step, total_steps, level)

    target_variables = list(options.get("paper_target_variables") or [])
    requested_explanatory = list(options.get("paper_explanatory_variables") or [])
    filtered_explanatory, dropped_explanatory = quality_filtered_explanatory_variables(
        requested_explanatory,
        target_variables,
    )
    if not filtered_explanatory:
        raise ValueError(
            "No explanatory variable passed the data-quality filter. "
            "Lower the minimum data coverage or select variables with better coverage."
        )
    review_variables = list(dict.fromkeys([*target_variables, *filtered_explanatory]))
    vmd_k = int(options.get("vmd_imf_count", 4))
    report(2, f"Running VMD decomposition review with K = {vmd_k}...")
    review = build_vmd_center_frequency_review(
        start_date=paper_sample_start,
        end_date=options["end_date"],
        variables=review_variables,
        vmd_k=vmd_k,
    )
    if dropped_explanatory:
        report(
            2,
            "Dropped before VMD/MRGC/FEVD: " + ", ".join(dropped_explanatory),
            "warning",
        )
    report(2, "VMD center-frequency review is ready.", "success")
    return {
        "options": options.copy(),
        "paper_sample_start": paper_sample_start,
        "vmd_center_frequencies": review,
        "candidate_variables_for_next_step": filtered_explanatory,
        "dropped_explanatory_variables": dropped_explanatory,
    }


def run_paper_replication_h_review(
    options: dict[str, Any],
    paper_sample_start: str,
    status_callback: Any | None = None,
) -> dict[str, Any]:
    """Run paper workflow until FEVD horizon h is determined, then pause for review."""
    run_paper_replication_h_review_step = import_function(
        "src.paper_replication",
        "run_paper_replication_h_review",
    )

    total_steps = 4

    def report(step: int, message: str, level: str = "info") -> None:
        if status_callback is not None:
            status_callback(message, step, total_steps, level)

    target_variables = list(options.get("paper_target_variables") or [])
    requested_explanatory = list(options.get("paper_explanatory_variables") or [])
    filtered_explanatory, dropped_explanatory = quality_filtered_explanatory_variables(
        requested_explanatory,
        target_variables,
    )
    if not filtered_explanatory:
        raise ValueError(
            "No explanatory variable passed the data-quality filter. "
            "Lower the minimum data coverage or select variables with better coverage."
        )
    if dropped_explanatory:
        report(
            3,
            "Dropped before h review: " + ", ".join(dropped_explanatory),
            "warning",
        )
    report(3, "Determining selected-scale extrema and FEVD horizon h before TVP/FEVD...")
    result = run_paper_replication_h_review_step(
        start_date=paper_sample_start,
        end_date=options["end_date"],
        event_start_date=options["start_date"],
        allow_thesis_source=False,
        use_thesis_vmd_cache=False,
        target_variables=target_variables,
        candidate_variables=filtered_explanatory,
        vmd_k=int(options.get("vmd_imf_count", 4)),
    )
    report(3, "FEVD horizon h review is ready.", "success")
    return {
        "options": options.copy(),
        "paper_sample_start": paper_sample_start,
        "h_review": result.get("h_review"),
        "candidate_variables_for_next_step": filtered_explanatory,
        "dropped_explanatory_variables": dropped_explanatory,
    }


def run_paper_replication_workflow(
    options: dict[str, Any],
    status_callback: Any | None = None,
) -> dict[str, pd.DataFrame]:
    """Run the paper-method replication workflow from data update to outputs."""
    setup = run_paper_replication_setup_workflow(options, status_callback=status_callback)
    run_paper_replication_vmd_review(
        setup["options"],
        setup["paper_sample_start"],
        status_callback=status_callback,
    )
    run_paper_replication_h_review(
        setup["options"],
        setup["paper_sample_start"],
        status_callback=status_callback,
    )
    return run_paper_replication_after_variable_confirmation(
        setup["options"],
        setup["paper_sample_start"],
        status_callback=status_callback,
    )


def format_display_value(value: Any, decimals: int = 3) -> str:
    """Format dates and numeric values for dashboard display."""
    if value is None or pd.isna(value):
        return "NA"
    if isinstance(value, (pd.Timestamp,)):
        return value.strftime("%Y-%m-%d")
    if isinstance(value, (float, int)):
        return f"{float(value):.{decimals}f}"
    parsed_date = pd.to_datetime(value, errors="coerce")
    if pd.notna(parsed_date) and any(token in str(value) for token in ["-", "/", ":"]):
        return parsed_date.strftime("%Y-%m-%d")
    try:
        return f"{float(value):.{decimals}f}"
    except (TypeError, ValueError):
        return str(value)


def render_metric_row(items: list[tuple[str, Any]], columns: int = 4) -> None:
    """Render a row of metric cards."""
    cols = st.columns(columns)
    for col, (label, value) in zip(cols, items):
        col.metric(label, format_display_value(value))


def render_data_tab(options: dict[str, Any], *, show_header: bool = True) -> None:
    """Render the Data tab with summary, sources, and freshness checks."""
    if show_header:
        st.header("Data")

    with st.container(border=True):
        st.subheader("A. Model-Ready Data Summary")
        data = load_excel_if_exists(PATHS["model_ready"])
        data_source_label = "model_ready_data.xlsx"
        if data is None:
            data = load_excel_if_exists(PATHS["clean_market"])
            data_source_label = "clean_market_data.xlsx"
        if data is None:
            st.info("Please run data update first.")
        else:
            st.caption(
                f"Showing {data_source_label}. Rows with any missing retained variable are removed during "
                "model-ready preparation before analysis windows are split."
            )
            date_series = pd.to_datetime(data["Date"], errors="coerce") if "Date" in data.columns else pd.Series(dtype="datetime64[ns]")
            complete_core_columns = [
                column for column in CORE_MARKET_FRESHNESS_COLUMNS if column in data.columns
            ]
            latest_complete_core_date = pd.NaT
            if "Date" in data.columns and complete_core_columns:
                complete_core_data = data.copy()
                complete_core_data["Date"] = pd.to_datetime(complete_core_data["Date"], errors="coerce")
                complete_core_data = complete_core_data.dropna(subset=["Date", *complete_core_columns])
                if not complete_core_data.empty:
                    latest_complete_core_date = complete_core_data["Date"].max()
            wti_rows = data.loc[data["WTI"].notna()].copy() if "WTI" in data.columns else pd.DataFrame()
            latest_wti_value = None
            if not wti_rows.empty:
                wti_rows["Date"] = pd.to_datetime(wti_rows["Date"], errors="coerce")
                latest_index = wti_rows["Date"].idxmax()
                latest_wti_value = wti_rows.loc[latest_index, "WTI"]
            interval = "NA"
            if not date_series.dropna().empty:
                interval = f"{date_series.min():%Y-%m-%d} to {date_series.max():%Y-%m-%d}"
            render_metric_row(
                [
                    ("Data interval", interval),
                    ("Latest complete core date", latest_complete_core_date),
                    ("Latest WTI price", latest_wti_value),
                ],
                columns=3,
            )
            st.write("Missing values")
            missing = (
                data.isna()
                .sum()
                .rename("MissingCount")
                .reset_index()
                .rename(columns={"index": "Variable"})
            )
            st.dataframe(missing, use_container_width=True)
            with st.expander("Displayed data preview"):
                st.dataframe(data.head(10), use_container_width=True)

    with st.container(border=True):
        st.subheader("B. Data Source Log")
        sources = load_excel_if_exists(PATHS["data_source_log"])
        if sources is None:
            st.info("Data source log is not available.")
        else:
            wti_source = sources.loc[sources["Variable"] == "WTI", "ActualSource"]
            if not wti_source.empty:
                st.metric("WTI actual source", str(wti_source.iloc[0]))
            st.dataframe(sources, use_container_width=True)

    with st.container(border=True):
        st.subheader("C. Net-Impact File Status")
        status_rows = []
        for label, path, columns in [
            ("clean_market_data.xlsx", PATHS["clean_market"], ["Date"]),
            ("model_ready_data.xlsx", PATHS["model_ready"], ["Date"]),
            ("expanded_variable_pool.xlsx", PATHS["expanded_variable_pool"], ["Date"]),
            ("paper_replication_dashboard.xlsx", PATHS["paper_dashboard"], ["Date", "EventStartDate", "SelectedEndDate"]),
            ("paper_net_impacts.xlsx", PATHS["paper_net_impacts"], ["Date", "EventStartDate", "SelectedEndDate"]),
        ]:
            checked_date = _max_date_from_file(path, columns)
            status_rows.append(
                {
                    "File": label,
                    "CheckedDate": checked_date,
                    "Status": "Available" if path.exists() else "Missing",
                }
            )
        st.dataframe(pd.DataFrame(status_rows), use_container_width=True)


def render_paper_replication_tab() -> None:
    """Render paper-method replication results."""
    st.header(ui_text("Net-Impact Analysis Results", "净影响分析结果"))
    st.write(
        ui_text(
            "This page reports the generalized EMTV-NEI workflow: VMD decomposition, multiresolution Granger causality, main-scale selection, rolling VAR FEVD contributions, net impacts, and structural-break diagnostics.",
            "本页展示广义 EMTV-NEI 流程结果：VMD 分解、多分辨率 Granger 因果检验、主尺度选择、滚动 VAR FEVD 贡献、净影响与结构突变诊断。",
        )
    )
    summary_for_method_note = load_excel_if_exists(PATHS["paper_summary"])
    vmd_k_note = "selected K"
    if summary_for_method_note is not None and {"Item", "Value"}.issubset(summary_for_method_note.columns):
        value = summary_for_method_note.loc[summary_for_method_note["Item"].astype(str).eq("VMD K"), "Value"]
        if not value.empty:
            vmd_k_note = str(value.iloc[0])
    st.info(ui_text(
        f"Method settings: VMD K = {vmd_k_note}, penalty factor = 1000, MRGC maximum lag = 5 selected by BIC, VAR lag selected by BIC, rolling window = 120, and FEVD horizon h determined by the trading-day interval between selected-scale extrema.",
        f"方法设置：VMD K = {vmd_k_note}，惩罚因子 = 1000，MRGC 最大滞后阶数 5（BIC 选择），VAR 滞后阶数由 BIC 选择，滚动窗口 = 120，FEVD 预测期 h 由所选尺度极值之间的交易日间隔确定。",
    ))

    archive_bytes, archive_names = build_results_archive()
    with st.container(border=True):
        action_col, download_col = st.columns([0.72, 0.28])
        with action_col:
            st.markdown(ui_text("**Result package**", "**结果文件包**"))
            st.caption(
                ui_text(
                    "Cloud-generated files are temporary. Download the ZIP after each completed analysis.",
                    "云端生成文件为临时文件，建议每次分析完成后立即下载 ZIP 保存。",
                )
            )
        with download_col:
            if archive_names:
                st.download_button(
                    ui_text("Download all results", "下载全部结果"),
                    data=archive_bytes,
                    file_name="multiscale_net_impact_results.zip",
                    mime="application/zip",
                    use_container_width=True,
                    key="download_all_result_artifacts",
                )
                st.caption(ui_text(f"{len(archive_names)} files", f"共 {len(archive_names)} 个文件"))
            else:
                st.button(
                    ui_text("No results yet", "暂无结果文件"),
                    disabled=True,
                    use_container_width=True,
                    key="download_all_result_artifacts_empty",
                )

    with st.container(border=True):
        st.subheader(ui_text("A. Method, Sample, and Event Window", "A. 方法、样本与事件窗口"))
        render_downloadable_table(
            ui_text("Net-impact summary", "净影响汇总"),
            PATHS["paper_summary"],
            description=ui_text("Method settings, sample range, targets, candidate variables, and event date.", "方法设置、样本区间、目标变量、候选变量与事件日期。"),
        )
        render_downloadable_image(
            ui_text("Crude-oil price event chart", "原油价格事件图"),
            PATHS["paper_price_event_figure"],
            ui_text("Crude-oil prices with the event start marked.", "展示原油价格并标记事件开始日期。"),
        )

    with st.container(border=True):
        st.subheader(ui_text("B. VMD Decomposition and HHT Frequency", "B. VMD 分解与 HHT 频率"))
        render_downloadable_table(
            ui_text("VMD center-frequency review", "VMD 中心频率审查"),
            PATHS["paper_vmd_center_frequencies"],
            description=ui_text("Center-frequency and period diagnostics for selected variables and IMFs.", "所选变量与 IMF 的中心频率和周期诊断。"),
        )
        vmd_figures = paper_vmd_figure_paths()
        if vmd_figures:
            with st.expander(ui_text(f"VMD decomposition figures ({len(vmd_figures)})", f"VMD 分解图（{len(vmd_figures)}）"), expanded=False):
                for figure_path in vmd_figures:
                    label = figure_path.stem.replace("paper_vmd_decomposition_", "").replace("_", " ").upper()
                    render_downloadable_image(f"VMD decomposition: {label}", figure_path)
        else:
            st.info(ui_text("VMD decomposition figures are not available yet. Re-run the analysis.", "VMD 分解图尚未生成，请重新运行分析。"))
        render_downloadable_image(
            ui_text("HHT IMF1 instantaneous frequency", "HHT IMF1 瞬时频率"),
            PATHS["paper_hht_imf1_figure"],
            "Corresponds to the paper's IMF1 instantaneous-frequency diagnostic.",
        )

    with st.container(border=True):
        st.subheader(ui_text("C. Main Scale Selection", "C. 主尺度选择"))
        render_downloadable_table(ui_text("Scale statistics and IMF interpretation", "尺度统计与 IMF 解释"), PATHS["paper_scale_statistics"])
        render_downloadable_table(ui_text("Selected-scale event effect", "所选尺度事件效应"), PATHS["paper_selected_scale_effect"])
        render_downloadable_table(
            ui_text("FEVD horizon h review", "FEVD 预测期 h 审查"),
            PATHS["paper_h_review"],
            description="This is the manual-confirmation table shown before TVP/FEVD starts.",
        )
        render_downloadable_image(ui_text("Scale statistics figure", "尺度统计图"), PATHS["paper_scale_statistics_figure"])
        render_downloadable_image(
            ui_text("Selected-scale trend figure", "所选尺度趋势图"),
            PATHS["paper_selected_scale_figure"],
            "This is the chart in your screenshot. It is kept because it validates the selected response scale and marks the extrema used to calculate FEVD_h.",
        )

    with st.container(border=True):
        st.subheader(ui_text("D. Multiresolution Granger Causality", "D. 多分辨率 Granger 因果检验"))
        render_downloadable_table(ui_text("MRGC results", "MRGC 结果"), PATHS["paper_mrgc"])
        render_downloadable_table(
            ui_text("Selected-scale Granger tests for contribution-model inclusion", "贡献模型纳入变量的所选尺度 Granger 检验"),
            PATHS["paper_selected_scale_granger"],
        )
        render_downloadable_image(ui_text("MRGC heatmap", "MRGC 热力图"), PATHS["paper_mrgc_figure"])

    with st.container(border=True):
        st.subheader(ui_text("E. TVP/VAR FEVD Contribution Decomposition", "E. TVP/VAR FEVD 贡献分解"))
        render_downloadable_table(ui_text("Model settings and FEVD horizon h", "模型设置与 FEVD 预测期 h"), PATHS["paper_tvp_settings"])
        render_downloadable_table(
            ui_text("External relative contribution weights after excluding own shock", "剔除自身冲击后的外部相对贡献权重"),
            PATHS["paper_contribution_weights"],
        )
        render_downloadable_table(ui_text("Narrow and broad war-related net impacts", "狭义与广义战争相关净影响"), PATHS["paper_net_impacts"])
        contribution_figures = paper_external_contribution_figure_items()
        if contribution_figures:
            for title, figure_path in contribution_figures:
                render_downloadable_image(
                    title,
                    figure_path,
                    "Paper Fig. 4.11/4.12 style external relative contribution chart.",
                )
            if PATHS["paper_contribution_figure"].exists():
                with st.expander("Combined external-contribution overview", expanded=False):
                    render_downloadable_image("External contribution overview", PATHS["paper_contribution_figure"])
        else:
            render_downloadable_image("External contribution figure", PATHS["paper_contribution_figure"])
        render_downloadable_image(ui_text("Net-impact figure", "净影响图"), PATHS["paper_net_impact_figure"])

    with st.container(border=True):
        st.subheader(ui_text("F. Structural-Break Diagnostics", "F. 结构突变诊断"))
        render_downloadable_table(ui_text("Event-start structural-break test", "事件起点结构突变检验"), PATHS["paper_break_test"])
        render_downloadable_table(
            ui_text("Optimal-break RSS profile", "最优突变点 RSS 曲线"),
            PATHS["paper_optimal_break_rss"],
            description="Supports the paper's optimal-break RSS profile figures.",
            max_rows=120,
        )
        render_downloadable_image(ui_text("Event-start trend-break fit", "事件起点趋势突变拟合"), PATHS["paper_break_figure"])
        render_downloadable_image(ui_text("Optimal-break RSS profile", "最优突变点 RSS 曲线"), PATHS["paper_optimal_break_rss_figure"])


def _filter_variable_list_text(value: Any, valid_variables: set[str]) -> str:
    """Filter a comma-separated variable-list string to current valid variables."""
    parts = [part.strip() for part in str(value or "").split(",") if part.strip()]
    kept = [part for part in parts if part in valid_variables]
    return ", ".join(kept)


def filter_variable_pool_display_table(label: str, data: pd.DataFrame) -> pd.DataFrame:
    """Hide stale rows/columns for variables no longer present in the current daily-only pool."""
    if data is None or data.empty:
        return data
    valid_options, _ = load_variable_pool_options()
    valid_variables = set(valid_options)
    filtered = data.copy()
    had_removed_variables = False

    if "Variable" in filtered.columns:
        variable_text = filtered["Variable"].astype(str)
        had_removed_variables = bool((~variable_text.isin(valid_variables)).any())
        filtered = filtered.loc[variable_text.isin(valid_variables)].copy()

    if label == "Expanded Variable Pool":
        keep_columns = [
            column
            for column in filtered.columns
            if column == "Date" or str(column) in valid_variables
        ]
        had_removed_variables = had_removed_variables or len(keep_columns) < len(filtered.columns)
        filtered = filtered[keep_columns].copy()

    for limiter_column in ["CommonStartLimitedBy", "CommonEndLimitedBy"]:
        if limiter_column in filtered.columns:
            filtered[limiter_column] = filtered[limiter_column].apply(
                lambda value: _filter_variable_list_text(value, valid_variables)
            )

    if had_removed_variables and "AlignmentNote" in filtered.columns:
        filtered["AlignmentNote"] = (
            "This stale report is filtered to the current daily-only variable pool. "
            "Re-run the analysis to refresh common-window limit notes."
        )
    return filtered


def render_variable_pool_tab(*, show_header: bool = True) -> None:
    """Render candidate-variable registry and upload diagnostics."""
    if show_header:
        st.header("Variable Pool")
        st.write(
            "This page shows the variables available for multiscale net-impact analysis, "
            "including automatically refreshed variables and locally uploaded variables."
        )
    else:
        with st.container(border=True):
            st.subheader("D. Variable Pool")
            st.write(
                "Variables available for multiscale net-impact analysis, including "
                "automatically refreshed variables and locally uploaded variables."
            )

    outputs = [
        ("Variable Registry", PATHS["variable_registry_table"]),
        ("Data Refresh and Preparation Workbook", PATHS["data_refresh_preparation_workbook"]),
        ("Expanded Variable Pool", PATHS["expanded_variable_pool"]),
        ("Variable Pool Coverage Report", PATHS["variable_pool_coverage_report"]),
        ("Variable Pool Quality Filter Report", PATHS["variable_pool_quality_report"]),
        ("Variable Pool Update Review Report", PATHS["variable_pool_update_review_report"]),
        ("Variable Date-Alignment Report", PATHS["variable_pool_date_alignment_report"]),
        ("Uploaded Variable Manifest", PATHS["uploaded_variable_manifest"]),
        ("Uploaded Variable Quality Report", PATHS["uploaded_variable_quality_report"]),
    ]
    optional_upload_outputs = {
        "Uploaded Variable Manifest",
        "Uploaded Variable Quality Report",
    }
    for label, path in outputs:
        with st.container(border=True):
            st.subheader(label)
            data = load_excel_if_exists(path)
            if data is None:
                if label in optional_upload_outputs:
                    st.info(f"{label} is not used because no local variable has been uploaded.")
                else:
                    st.info(f"{label} is not available yet.")
            else:
                data = filter_variable_pool_display_table(label, data)
                st.dataframe(data, use_container_width=True)


def _download_mime(path: Path) -> str:
    """Return a practical MIME type for a downloadable artifact."""
    suffix = path.suffix.lower()
    if suffix == ".xlsx":
        return "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    if suffix == ".docx":
        return "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    if suffix == ".png":
        return "image/png"
    if suffix == ".pdf":
        return "application/pdf"
    if suffix == ".svg":
        return "image/svg+xml"
    return "application/octet-stream"


def _download_key(prefix: str, path: Path) -> str:
    """Build a stable Streamlit key for an artifact download button."""
    token = re.sub(r"[^A-Za-z0-9]+", "_", str(path.relative_to(PROJECT_ROOT) if path.is_relative_to(PROJECT_ROOT) else path))
    return f"{prefix}_{token}"


def _pdf_variant(path: Path) -> Path:
    """Return the sidecar PDF path for a PNG figure when available."""
    return path.with_suffix(".pdf")


def render_artifact_download_button(path: Path, label: str, key_prefix: str) -> None:
    """Render a compact download button for one artifact."""
    path = Path(path)
    if path.exists():
        st.download_button(
            label,
            data=path.read_bytes(),
            file_name=path.name,
            mime=_download_mime(path),
            use_container_width=True,
            key=_download_key(key_prefix, path),
        )
    else:
        st.button(label, disabled=True, use_container_width=True, key=_download_key(f"missing_{key_prefix}", path))


def render_downloadable_table(
    title: str,
    path: Path,
    data: pd.DataFrame | None = None,
    description: str | None = None,
    max_rows: int | None = None,
) -> None:
    """Render a table with its download button in the same result block."""
    path = Path(path)
    table = data if data is not None else load_excel_if_exists(path)
    title_col, download_col = st.columns([0.74, 0.26])
    with title_col:
        st.write(title)
        if description:
            st.caption(description)
    with download_col:
        render_artifact_download_button(path, ui_text("Download table", "下载表格"), f"table_{title}")
    if table is None:
        st.info(ui_text(f"{title} is not available yet.", f"{title} 尚未生成。"))
        return
    display_table = table.tail(max_rows) if max_rows and len(table) > max_rows else table
    st.dataframe(display_table, use_container_width=True)


def render_downloadable_image(title: str, path: Path, description: str | None = None) -> None:
    """Render a figure with adjacent PNG/PDF download controls."""
    path = Path(path)
    if not path.exists():
        return
    image_col, action_col = st.columns([0.78, 0.22])
    with image_col:
        st.image(str(path), use_container_width=True)
        if description:
            st.caption(description)
    with action_col:
        st.write(title)
        render_artifact_download_button(path, ui_text("Download PNG", "下载 PNG"), f"figure_png_{title}")
        pdf_path = _pdf_variant(path)
        if pdf_path.exists():
            render_artifact_download_button(pdf_path, ui_text("Download PDF", "下载 PDF"), f"figure_pdf_{title}")


def paper_vmd_figure_paths() -> list[Path]:
    """Return generated paper VMD decomposition figures."""
    return sorted((PROJECT_ROOT / "outputs" / "figures").glob("paper_vmd_decomposition_*.png"))


def _safe_figure_token(value: Any) -> str:
    """Return the figure token used by paper_replication dynamic outputs."""
    token = re.sub(r"[^A-Za-z0-9]+", "_", str(value)).strip("_").lower()
    return token or "figure"


def paper_external_contribution_figure_items() -> list[tuple[str, Path]]:
    """Return paper-style single-target external contribution figures."""
    contribution = load_excel_if_exists(PATHS["paper_contribution_weights"])
    figures_dir = PROJECT_ROOT / "outputs" / "figures"
    items: list[tuple[str, Path]] = []
    if contribution is not None and {"Target", "SelectedScale"}.issubset(contribution.columns):
        pairs = contribution[["Target", "SelectedScale"]].drop_duplicates()
        for _, row in pairs.iterrows():
            target = str(row["Target"])
            selected_scale = str(row["SelectedScale"])
            path = figures_dir / (
                "paper_external_contribution_"
                f"{_safe_figure_token(target)}_{_safe_figure_token(selected_scale)}.png"
            )
            if path.exists():
                items.append((f"{target} {selected_scale} external relative contribution", path))
    if items:
        return items
    return [
        (
            path.stem.replace("paper_external_contribution_", "").replace("_", " ").upper(),
            path,
        )
        for path in sorted(figures_dir.glob("paper_external_contribution_*_*.png"))
    ]


def render_upload_controls(options: dict[str, Any]) -> None:
    """Render local variable upload controls for net-impact analysis."""
    with st.container(border=True):
        st.subheader(ui_text("Local Candidate Variable Uploads", "上传本地候选变量"))
        upload_status = st.session_state.pop("local_upload_status_message", None)
        if upload_status:
            status_level = upload_status.get("level", "success")
            status_text = upload_status.get("text", "")
            if status_level == "warning":
                st.warning(status_text)
            elif status_level == "error":
                st.error(status_text)
            else:
                st.success(status_text)
        st.write(
            ui_text(
                "Upload optional CSV or Excel files and register them as candidate variables. Columns are mapped automatically.",
                "上传可选的 CSV 或 Excel 文件并注册为候选变量，系统会按列位置自动映射。",
            )
        )
        st.info(
            ui_text(
                "Rule: leading title or note rows are allowed. The first parseable date/numeric row starts the data; column 1 is Date and column 2 is Value. Extra non-empty columns are rejected. Multiple files are supported. Confirm the preprocessing summary before saving.",
                "规则：允许文件开头包含标题或备注；首个可解析的日期/数值行视为数据起点，第 1 列为日期，第 2 列为数值。存在额外非空列的文件会被拒绝。支持多文件上传，保存前需确认预处理汇总。",
            )
        )
        uploaded_files = st.file_uploader(
            ui_text("Upload local candidate variable files", "上传本地候选变量文件"),
            type=["csv", "xlsx", "xls"],
            accept_multiple_files=True,
        )
        upload_jobs: list[dict[str, Any]] = []
        preprocess_rows: list[dict[str, Any]] = []
        if uploaded_files:
            seen_upload_variable_names: set[str] = set()
            for index, uploaded_file in enumerate(uploaded_files):
                safe_name = Path(uploaded_file.name).name
                with st.expander(ui_text(f"Configure upload: {safe_name}", f"配置上传：{safe_name}"), expanded=True):
                    try:
                        preview = read_uploaded_file_to_dataframe(uploaded_file)
                    except Exception as exc:  # noqa: BLE001 - keep other uploads configurable.
                        error_text = safe_exception_text(exc)
                        st.error(f"Could not read this file: {error_text}")
                        preprocess_rows.append(uploaded_preprocess_failure_row(safe_name, error_text))
                        continue
                    if preview.empty:
                        st.error("This file is empty.")
                        preprocess_rows.append(uploaded_preprocess_failure_row(safe_name, "This file is empty."))
                        continue
                    columns = [str(column) for column in preview.columns]
                    try:
                        date_column, value_column = automatic_uploaded_column_mapping(columns)
                    except ValueError as exc:
                        st.error(str(exc))
                        preprocess_rows.append(uploaded_preprocess_failure_row(safe_name, str(exc)))
                        continue
                    value_values = coerce_uploaded_numeric_series(preview[value_column])
                    if value_values.notna().sum() == 0:
                        st.error(
                            "The second column could not be parsed as numeric values. "
                            "Use numeric values such as 72.35, 1,234.5, or 2.3%."
                        )
                        preprocess_rows.append(
                            uploaded_preprocess_failure_row(
                                safe_name,
                                "The second column could not be parsed as numeric values.",
                            )
                        )
                        continue
                    mapped_preview = pd.DataFrame(
                        {
                            "Date": preview[date_column].head(5),
                            "Value": preview[value_column].head(5),
                        }
                    )
                    try:
                        default_name = sanitize_variable_name(Path(safe_name).stem)
                    except ValueError:
                        default_name = f"UploadedVariable{index + 1}"
                    variable_name = st.text_input(
                        ui_text("Variable name to register", "注册变量名称"),
                        value=default_name,
                        help=ui_text("Use letters, numbers, and underscores.", "请使用字母、数字和下划线。"),
                        key=f"upload_variable_name_{index}_{safe_name}",
                    )
                    try:
                        sanitized_variable_name = sanitize_variable_name(variable_name)
                    except ValueError as exc:
                        st.error(str(exc))
                        preprocess_rows.append(uploaded_preprocess_failure_row(safe_name, str(exc), variable_name))
                        continue
                    if sanitized_variable_name in seen_upload_variable_names:
                        duplicate_note = f"Duplicate variable name '{sanitized_variable_name}'. Use a unique name for each file."
                        st.error(duplicate_note)
                        preprocess_rows.append(
                            uploaded_preprocess_failure_row(safe_name, duplicate_note, sanitized_variable_name)
                        )
                        continue
                    seen_upload_variable_names.add(sanitized_variable_name)
                    st.caption("Preprocessed preview")
                    st.dataframe(mapped_preview, use_container_width=True, hide_index=True)
                    preprocess_rows.append(
                        uploaded_preprocess_summary_row(
                            file_name=safe_name,
                            variable_name=sanitized_variable_name,
                            prepared=preview,
                            start_date=options["start_date"],
                            end_date=options["end_date"],
                            min_coverage=float(options["min_data_coverage"]),
                        )
                    )
                    upload_jobs.append(
                        {
                            "uploaded_file": uploaded_file,
                            "variable_name": sanitized_variable_name,
                            "date_column": date_column,
                            "value_column": value_column,
                            "start_date": options["start_date"],
                            "end_date": options["end_date"],
                        }
                    )
            if preprocess_rows:
                st.subheader("Preprocessing Confirmation")
                st.dataframe(pd.DataFrame(preprocess_rows), use_container_width=True, hide_index=True)
                if len(upload_jobs) < len(uploaded_files):
                    st.warning("Only files with Ready status will be added to the variable pool after confirmation.")
            if st.button("Confirm and Add to Variable Pool", use_container_width=True, disabled=not upload_jobs):
                if not upload_jobs:
                    st.warning("No valid upload is ready. Check that each file has exactly two columns: Date and Value.")
                    return
                saved_paths, upload_report = save_standardized_uploaded_variables(
                    upload_jobs,
                    min_coverage=float(options["min_data_coverage"]),
                )
                if saved_paths:
                    merge_note = ""
                    try:
                        merged = run_merge_uploaded_variables({"use_uploaded_local_data_first": True})
                        if isinstance(merged, pd.DataFrame):
                            merge_note = f" Merged into model-ready data with {len(merged)} rows."
                    except Exception as exc:  # noqa: BLE001 - keep saved uploads usable even if model-ready is absent.
                        merge_note = (
                            " Saved files are registered, but model-ready merge was skipped: "
                            f"{safe_exception_text(exc)}"
                        )
                    st.session_state["local_upload_status_message"] = {
                        "level": "success",
                        "text": (
                            "Uploaded variables saved, registered, and selectors refreshed: "
                            + ", ".join(path.stem for path in saved_paths)
                            + "."
                            + merge_note
                        ),
                    }
                    st.dataframe(upload_report, use_container_width=True)
                    if (upload_report["Coverage"] < float(options["min_data_coverage"])).any():
                        st.warning(
                            "At least one uploaded variable has lower coverage than the current minimum data coverage. "
                            "It is saved, but quality filtering may drop it during analysis."
                        )
                    st.rerun()
                elif not upload_report.empty:
                    st.error("No uploaded variable was saved. Review the validation report below.")
                    st.dataframe(upload_report, use_container_width=True)
                else:
                    st.warning("No uploaded variable was saved. Check that at least one configured upload is valid.")
        else:
            existing_manifest = load_excel_if_exists(PATHS["uploaded_variable_manifest"])
            if existing_manifest is not None and not existing_manifest.empty:
                st.write("Registered uploaded variables")
                st.dataframe(existing_manifest, use_container_width=True)


def render_run_pipeline_tab(options: dict[str, Any]) -> None:
    """Render the net-impact analysis execution tab."""
    st.header(ui_text("Run Net-Impact Analysis", "运行净影响分析"))
    st.write(
        ui_text(
            "Configure targets and explanatory variables, then run EMTV-NEI multiscale screening and net-impact measurement.",
            "配置目标变量与解释变量，然后运行 EMTV-NEI 多尺度筛选和净影响测度。",
        )
    )

    variable_pool_options, default_variable_pool = load_variable_pool_options()
    variable_metadata = load_variable_registry_metadata()
    language = current_language()
    variable_format = lambda variable: format_variable_option(variable, variable_metadata, language)
    net_options = options.copy()
    with st.container(border=True):
        st.subheader(ui_text("Net-Impact Analysis Workflow", "净影响分析流程"))
        st.write(
            ui_text(
                "The workflow refreshes data, runs MRGC, selects main scales, estimates FEVD contributions, and reports net impacts.",
                "该流程更新数据、运行 MRGC、选择主尺度、估计 FEVD 贡献并报告净影响。",
            )
        )
        default_targets = [
            variable
            for variable in options.get("paper_target_variables", ["WTI", "Brent"])
            if variable in variable_pool_options
        ][:2]
        selection_version_key = "net_impact_variable_selection_version"
        if st.session_state.get(selection_version_key) != DEFAULT_VARIABLE_SELECTION_VERSION:
            st.session_state["net_impact_target_variables"] = default_targets
            st.session_state["net_impact_explanatory_variables"] = [
                variable
                for variable in options.get("paper_explanatory_variables", default_variable_pool)
                if variable in variable_pool_options and variable not in default_targets
            ]
            st.session_state[selection_version_key] = DEFAULT_VARIABLE_SELECTION_VERSION
            st.session_state["net_impact_variable_widget_language"] = None
        target_widget_key = f"net_impact_target_variables_{language}"
        explanatory_widget_key = f"net_impact_explanatory_variables_{language}"
        widget_language_key = "net_impact_variable_widget_language"
        if st.session_state.get(widget_language_key) != language:
            st.session_state[target_widget_key] = list(
                st.session_state.get("net_impact_target_variables", default_targets)
            )
            st.session_state[explanatory_widget_key] = list(
                st.session_state.get("net_impact_explanatory_variables", [])
            )
            st.session_state[widget_language_key] = language
        net_targets = st.multiselect(
            ui_text("Target variables to be explained", "待解释的目标变量"),
            options=variable_pool_options,
            help=ui_text("Select one or two targets; each run supports at most two.", "选择一至两个目标变量，每次最多分析两个。"),
            key=target_widget_key,
            format_func=variable_format,
            max_selections=2,
        )
        if len(net_targets) > 2:
            st.warning(ui_text("At most two targets can be analyzed. Only the first two are used.", "每次最多分析两个目标变量，将只使用前两个。"))
            net_targets = net_targets[:2]

        explanatory_default = [
            variable
            for variable in options.get("paper_explanatory_variables", default_variable_pool)
            if variable in variable_pool_options and variable not in net_targets
        ]
        available_explanatory = [variable for variable in variable_pool_options if variable not in net_targets]
        use_all_explanatory = st.toggle(
            ui_text("Use all available explanatory variables", "使用全部可用解释变量"),
            value=True,
            help=ui_text(
                "Turn this off to choose a custom subset.",
                "关闭后可手动选择解释变量。",
            ),
            key="net_use_all_explanatory_variables",
        )
        if use_all_explanatory:
            net_explanatory = available_explanatory
            st.markdown(
                '<div class="variable-selection-summary">'
                f'<strong>{ui_text(f"{len(net_explanatory)} variables selected", f"已选择 {len(net_explanatory)} 个解释变量")}</strong>'
                f'<span>{ui_text("Targets are excluded automatically", "目标变量已自动排除")}</span>'
                "</div>",
                unsafe_allow_html=True,
            )
        else:
            st.session_state[explanatory_widget_key] = [
                variable
                for variable in st.session_state.get(explanatory_widget_key, explanatory_default)
                if variable in available_explanatory
            ]
            net_explanatory = st.multiselect(
                ui_text("Choose explanatory variables", "选择解释变量"),
                options=available_explanatory,
                help=ui_text(
                    "Select any number; selected targets are excluded automatically.",
                    "可选择任意数量，已选目标变量会自动排除。",
                ),
                key=explanatory_widget_key,
                format_func=variable_format,
            )
        st.session_state["net_impact_target_variables"] = list(net_targets)
        st.session_state["net_impact_explanatory_variables"] = list(net_explanatory)
        net_options["auto_download_expanded_variable_pool"] = True
        net_options["use_uploaded_local_data_first"] = True
        n_col1, n_col2 = st.columns(2)
        with n_col1:
            net_options["vmd_imf_count"] = int(
                st.number_input(
                    ui_text("Number of VMD IMFs", "VMD IMF 数量"),
                    min_value=MIN_VMD_IMF_COUNT,
                    max_value=MAX_VMD_IMF_COUNT,
                    value=min(
                        MAX_VMD_IMF_COUNT,
                        max(MIN_VMD_IMF_COUNT, int(options.get("vmd_imf_count", 4))),
                    ),
                    step=1,
                    help=ui_text(
                        "Allowed range: 1 to 100. Large values require substantially more time and memory.",
                        "允许范围：1 到 100。数值越大，计算时间和内存占用会明显增加。",
                    ),
                    key="net_vmd_imf_count",
                )
            )
        with n_col2:
            net_options["min_data_coverage"] = float(
                st.slider(
                    ui_text("Minimum data coverage", "最低数据覆盖率"),
                    min_value=0.10,
                    max_value=1.00,
                    value=float(options.get("min_data_coverage", 0.60)),
                    step=0.05,
                    key="net_min_data_coverage",
                )
            )
        net_options["paper_target_variables"] = list(net_targets)
        net_options["paper_explanatory_variables"] = list(net_explanatory)
        net_options["selected_variable_pool"] = sorted(set(net_targets) | set(net_explanatory))
        st.caption(
            ui_text("Targets: ", "目标变量：")
            + (", ".join(net_targets) if net_targets else ui_text("none", "无"))
            + ui_text(" | Explanatory variables: ", " | 解释变量：")
            + ui_text(
                f"{len(net_explanatory)} selected",
                f"已选择 {len(net_explanatory)} 个",
            )
            + ui_text(
                f" | VMD IMFs: {net_options['vmd_imf_count']}",
                f" | VMD IMF 数量：{net_options['vmd_imf_count']}",
            )
        )
        with st.expander(ui_text("Selected variable full names and data sources", "所选变量全称与数据来源"), expanded=True):
            selected_metadata = selected_variable_metadata_frame(
                list(dict.fromkeys([*net_targets, *net_explanatory])),
                variable_metadata,
                language,
            )
            st.dataframe(selected_metadata, use_container_width=True, hide_index=True)

        def make_paper_status_callback() -> tuple[Any, Any, Callable[[str, int, int, str], None]]:
            progress = st.progress(0)
            status_box = st.empty()
            log_box = st.empty()
            step_logs: dict[int, dict[str, str]] = {}
            level_labels = {
                "info": ui_text("Running", "运行中"),
                "success": ui_text("Done", "完成"),
                "warning": ui_text("Review", "需审查"),
                "error": ui_text("Error", "错误"),
            }

            def paper_status(message: str, step: int, total: int, level: str = "info") -> None:
                progress.progress(min(step / max(total, 1), 1.0))
                translated_message = localized_runtime_message(message, current_language())
                current = ui_text(
                    f"Step {step}/{total}: {translated_message}",
                    f"步骤 {step}/{total}：{translated_message}",
                )
                if level == "success":
                    status_box.success(current)
                elif level == "warning":
                    status_box.warning(current)
                elif level == "error":
                    status_box.error(current)
                else:
                    status_box.info(current)

                step_logs[int(step)] = {
                    ui_text("Step", "步骤"): f"{step}/{total}",
                    ui_text("Status", "状态"): level_labels.get(level, level.title()),
                    ui_text("Latest message", "最新消息"): translated_message,
                }
                ordered_logs = [step_logs[key] for key in sorted(step_logs)]
                with log_box.container():
                    st.dataframe(pd.DataFrame(ordered_logs), use_container_width=True, hide_index=True)

            return progress, status_box, paper_status

        if st.button(ui_text("Run Net-Impact Analysis", "运行净影响分析"), type="primary", use_container_width=True):
            if not net_targets:
                st.error(ui_text("Select at least one target before running.", "运行前请至少选择一个目标变量。"))
                return
            if not net_explanatory:
                st.error(ui_text("Select at least one explanatory variable before running.", "运行前请至少选择一个解释变量。"))
                return
            try:
                st.session_state.pop(NET_IMPACT_VMD_CONFIRMATION_STATE, None)
                st.session_state.pop(NET_IMPACT_TVP_CONFIRMATION_STATE, None)
                progress, status_box, paper_status = make_paper_status_callback()
                setup = run_paper_replication_setup_workflow(net_options, status_callback=paper_status)
                st.session_state[NET_IMPACT_CONFIRMATION_STATE] = setup
                progress.progress(1 / 4)
                status_box.warning(ui_text("Data refresh review is ready. Confirm below before VMD starts.", "数据更新审查已就绪，请确认后开始 VMD。"))
                st.info(ui_text("Review the workbook, period table, and variable coverage, then confirm to continue.", "请检查工作簿、期间表和变量覆盖情况，然后确认继续。"))
            except Exception as exc:  # noqa: BLE001 - keep Streamlit page alive.
                st.error(f"Net-impact analysis failed: {safe_exception_text(exc)}")

        pending_setup = st.session_state.get(NET_IMPACT_CONFIRMATION_STATE)
        if pending_setup:
            pending_options = pending_setup.get("options", {})
            pending_selected = set(pending_options.get("paper_target_variables", [])) | set(
                pending_options.get("paper_explanatory_variables", [])
            )
            unavailable_pending = sorted(str(item) for item in pending_selected if str(item) not in variable_pool_options)
            if unavailable_pending:
                st.session_state.pop(NET_IMPACT_CONFIRMATION_STATE, None)
                st.session_state.pop(NET_IMPACT_VMD_CONFIRMATION_STATE, None)
                st.session_state.pop(NET_IMPACT_TVP_CONFIRMATION_STATE, None)
                st.warning(
                    "The pending run was cleared because it used variables that are no longer available "
                    "in the daily-only variable pool: "
                    + ", ".join(unavailable_pending)
                    + ". Re-run the analysis with the current selections."
                )
                pending_setup = None
        if pending_setup:
            with st.container(border=True):
                st.subheader(ui_text("Confirm Data Refresh and Preparation", "确认数据更新与准备"))
                pending_options = pending_setup.get("options", {})
                variable_summary = pending_setup.get("variable_pool_summary", {})
                saved_targets = pending_options.get("paper_target_variables", [])
                saved_explanatory = pending_options.get("paper_explanatory_variables", [])
                initial_start = str(variable_summary.get("selected_start_date") or pending_options.get("start_date", ""))
                initial_end = str(variable_summary.get("selected_end_date") or pending_options.get("end_date", ""))
                effective_event_start = str(
                    variable_summary.get("effective_event_start_date") or pending_options.get("start_date", "")
                )
                effective_event_end = str(
                    variable_summary.get("effective_event_end_date") or pending_options.get("end_date", "")
                )
                st.caption(
                    "Pending run: effective "
                    f"{effective_event_start} to {effective_event_end} "
                    f"(initially selected {initial_start} to {initial_end}) | "
                    "Targets: "
                    + (", ".join(saved_targets) if saved_targets else "none")
                    + " | Explanatory variables: "
                    + (", ".join(saved_explanatory) if saved_explanatory else "none")
                )
                display_variable_pool_update_result(variable_summary)
                next_step_variables = variable_summary.get("candidate_variables_for_next_step", []) or []
                dropped_variables = variable_summary.get("dropped_explanatory_variables", []) or []
                if next_step_variables:
                    st.success(ui_text("Variables entering VMD/MRGC/FEVD: ", "将进入 VMD/MRGC/FEVD 的变量：") + ", ".join(next_step_variables))
                else:
                    st.error("No explanatory variable passed the quality filter, so the next step cannot run yet.")
                if dropped_variables:
                    st.warning("Dropped before VMD/MRGC/FEVD: " + ", ".join(dropped_variables))

                confirm_col, cancel_col = st.columns(2)
                if confirm_col.button(
                    ui_text("Confirm and Continue to VMD Review", "确认并继续 VMD 审查"),
                    type="primary",
                    use_container_width=True,
                    disabled=not bool(next_step_variables),
                ):
                    try:
                        progress, status_box, paper_status = make_paper_status_callback()
                        vmd_setup = run_paper_replication_vmd_review(
                            pending_options,
                            pending_setup["paper_sample_start"],
                            status_callback=paper_status,
                        )
                        st.session_state[NET_IMPACT_VMD_CONFIRMATION_STATE] = vmd_setup
                        st.session_state.pop(NET_IMPACT_CONFIRMATION_STATE, None)
                        progress.progress(2 / 4)
                        status_box.warning(ui_text("VMD center-frequency review is ready. Confirm before h is determined.", "VMD 中心频率审查已就绪，请确认后确定 h。"))
                        st.info(ui_text("Review the VMD center-frequency table, then confirm.", "请检查 VMD 中心频率表，然后确认。"))
                    except Exception as exc:  # noqa: BLE001 - keep Streamlit page alive.
                        st.error(
                            "VMD decomposition review failed after variable confirmation: "
                            f"{safe_exception_text(exc)}"
                        )
                if cancel_col.button(ui_text("Cancel Pending Analysis", "取消待处理分析"), use_container_width=True):
                    st.session_state.pop(NET_IMPACT_CONFIRMATION_STATE, None)
                    st.session_state.pop(NET_IMPACT_VMD_CONFIRMATION_STATE, None)
                    st.session_state.pop(NET_IMPACT_TVP_CONFIRMATION_STATE, None)
                    st.rerun()

        pending_vmd_setup = st.session_state.get(NET_IMPACT_VMD_CONFIRMATION_STATE)
        if pending_vmd_setup:
            with st.container(border=True):
                st.subheader(ui_text("Confirm VMD Decomposition Before h Review", "在 h 审查前确认 VMD 分解"))
                pending_options = pending_vmd_setup.get("options", {})
                vmd_k = int(pending_options.get("vmd_imf_count", 4))
                st.caption(
                    "Pending VMD review: "
                    f"K = {vmd_k} | "
                    f"{pending_options.get('start_date', '')} to {pending_options.get('end_date', '')}"
                )
                vmd_review = pending_vmd_setup.get("vmd_center_frequencies")
                vmd_review_df = (
                    vmd_review
                    if isinstance(vmd_review, pd.DataFrame)
                    else pd.DataFrame(vmd_review or [])
                )
                if vmd_review_df.empty:
                    st.error("VMD center-frequency table is empty. Re-run the previous step.")
                else:
                    ok_count = int(vmd_review_df.get("Status", pd.Series(dtype=str)).astype(str).eq("OK").sum())
                    failed_count = int((vmd_review_df.get("Status", pd.Series(dtype=str)).astype(str) != "OK").sum())
                    c1, c2, c3 = st.columns(3)
                    c1.metric("VMD K", vmd_k)
                    c2.metric("IMF rows OK", ok_count)
                    c3.metric("Rows needing review", failed_count)
                    display_columns = [
                        "Variable",
                        "IMF",
                        "VMD_K",
                        "CenterFrequencyCyclesPerObservation",
                        "CenterPeriodObservations",
                        "Observations",
                        "SampleStartDate",
                        "SampleEndDate",
                        "Status",
                        "Note",
                    ]
                    st.dataframe(
                        vmd_review_df[[column for column in display_columns if column in vmd_review_df.columns]],
                        use_container_width=True,
                        hide_index=True,
                    )
                    if "Status" in vmd_review_df.columns and not vmd_review_df["Status"].astype(str).eq("OK").all():
                        st.warning("Some selected variables could not be decomposed cleanly. Review the table before continuing.")
                next_step_variables = pending_vmd_setup.get("candidate_variables_for_next_step", []) or []
                if next_step_variables:
                    st.success("Variables that will enter MRGC and h review: " + ", ".join(next_step_variables))
                confirm_col, cancel_col = st.columns(2)
                can_continue_vmd = bool(next_step_variables) and not vmd_review_df.empty
                if confirm_col.button(
                    ui_text("Confirm VMD and Determine FEVD h", "确认 VMD 并确定 FEVD h"),
                    type="primary",
                    use_container_width=True,
                    disabled=not can_continue_vmd,
                ):
                    try:
                        progress, status_box, paper_status = make_paper_status_callback()
                        h_setup = run_paper_replication_h_review(
                            pending_options,
                            pending_vmd_setup["paper_sample_start"],
                            status_callback=paper_status,
                        )
                        progress.progress(3 / 4)
                        status_box.warning(ui_text("FEVD horizon h review is ready. Confirm before TVP/FEVD starts.", "FEVD 预测期 h 审查已就绪，请确认后开始 TVP/FEVD。"))
                        st.session_state[NET_IMPACT_TVP_CONFIRMATION_STATE] = h_setup
                        st.session_state.pop(NET_IMPACT_VMD_CONFIRMATION_STATE, None)
                        st.info(ui_text("Review the FEVD horizon h table, then confirm to start TVP/FEVD.", "请检查 FEVD 预测期 h 表，然后确认开始 TVP/FEVD。"))
                    except Exception as exc:  # noqa: BLE001 - keep Streamlit page alive.
                        st.error(f"FEVD h review failed after VMD confirmation: {safe_exception_text(exc)}")
                if cancel_col.button(ui_text("Cancel Pending VMD Analysis", "取消待处理 VMD 分析"), use_container_width=True):
                    st.session_state.pop(NET_IMPACT_VMD_CONFIRMATION_STATE, None)
                    st.session_state.pop(NET_IMPACT_TVP_CONFIRMATION_STATE, None)
                    st.rerun()

        pending_tvp_setup = st.session_state.get(NET_IMPACT_TVP_CONFIRMATION_STATE)
        if pending_tvp_setup:
            with st.container(border=True):
                st.subheader(ui_text("Confirm FEVD h Before TVP/FEVD", "在 TVP/FEVD 前确认 FEVD h"))
                pending_options = pending_tvp_setup.get("options", {})
                st.caption(
                    "Pending h review: "
                    f"{pending_options.get('start_date', '')} to {pending_options.get('end_date', '')}"
                )
                h_review = pending_tvp_setup.get("h_review")
                h_review_df = (
                    h_review
                    if isinstance(h_review, pd.DataFrame)
                    else pd.DataFrame(h_review or [])
                )
                if h_review_df.empty:
                    st.error("FEVD horizon h table is empty. Re-run the previous step.")
                else:
                    display_columns = [
                        "Target",
                        "SelectedScale",
                        "EventStartDate",
                        "SelectedScaleMinimumDate",
                        "SelectedScaleMaximumDate",
                        "TradingDayInterval",
                        "CalendarDayInterval",
                        "FEVD_h",
                        "Status",
                        "Note",
                    ]
                    h_values = pd.to_numeric(h_review_df.get("FEVD_h", pd.Series(dtype=float)), errors="coerce")
                    c1, c2, c3 = st.columns(3)
                    c1.metric("Targets ready", int(h_values.notna().sum()))
                    c2.metric("Minimum h", int(h_values.min()) if h_values.notna().any() else "NA")
                    c3.metric("Maximum h", int(h_values.max()) if h_values.notna().any() else "NA")
                    st.dataframe(
                        h_review_df[[column for column in display_columns if column in h_review_df.columns]],
                        use_container_width=True,
                        hide_index=True,
                    )
                    st.info(
                        "TVP/VAR FEVD will use FEVD_h as the forecast-error variance "
                        "decomposition horizon. Confirm this table to start the final step."
                    )
                    if PATHS["paper_h_review"].exists():
                        st.download_button(
                            "Download FEVD h Review",
                            data=PATHS["paper_h_review"].read_bytes(),
                            file_name=PATHS["paper_h_review"].name,
                            mime=_download_mime(PATHS["paper_h_review"]),
                            key="download_paper_h_review_inline",
                            use_container_width=True,
                        )

                next_step_variables = pending_tvp_setup.get("candidate_variables_for_next_step", []) or []
                if next_step_variables:
                    st.success("Variables that will enter TVP/FEVD: " + ", ".join(next_step_variables))
                confirm_col, cancel_col = st.columns(2)
                can_continue_tvp = bool(next_step_variables) and not h_review_df.empty
                if confirm_col.button(
                    ui_text("Confirm h and Start TVP/FEVD", "确认 h 并开始 TVP/FEVD"),
                    type="primary",
                    use_container_width=True,
                    disabled=not can_continue_tvp,
                ):
                    try:
                        progress, status_box, paper_status = make_paper_status_callback()
                        result = run_paper_replication_after_variable_confirmation(
                            pending_options,
                            pending_tvp_setup["paper_sample_start"],
                            status_callback=paper_status,
                        )
                        progress.progress(1.0)
                        status_box.success(ui_text("Net-impact analysis completed.", "净影响分析已完成。"))
                        st.session_state.pop(NET_IMPACT_TVP_CONFIRMATION_STATE, None)
                        st.success(ui_text("Net-impact analysis completed.", "净影响分析已完成。"))
                        if "net_impacts" in result:
                            st.dataframe(result["net_impacts"], use_container_width=True)
                        st.info(ui_text("Open Net-Impact Results to review all tables and figures.", "打开“净影响结果”查看全部表格与图形。"))
                    except Exception as exc:  # noqa: BLE001 - keep Streamlit page alive.
                        st.error(f"TVP/FEVD analysis failed after h confirmation: {safe_exception_text(exc)}")
                if cancel_col.button(ui_text("Cancel Pending TVP/FEVD Analysis", "取消待处理 TVP/FEVD 分析"), use_container_width=True):
                    st.session_state.pop(NET_IMPACT_TVP_CONFIRMATION_STATE, None)
                    st.rerun()

    render_upload_controls(net_options)


def main() -> None:
    """Run the Streamlit application."""
    configure_page()
    apply_custom_css()
    render_language_switcher()
    options = render_sidebar()

    render_main_header()

    tabs = st.tabs([
        ui_text("Run Analysis", "运行分析"),
        ui_text("Net-Impact Results", "净影响结果"),
    ])
    with tabs[0]:
        render_run_pipeline_tab(options)
    with tabs[1]:
        render_paper_replication_tab()


if __name__ == "__main__":
    main()
