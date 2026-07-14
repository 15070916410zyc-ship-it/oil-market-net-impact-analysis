"""Expanded candidate-variable registry and optional download utilities.

This module is intentionally separate from the core WTI data-fetching logic.
WTI freshness remains controlled by ``src.data_fetcher`` and the Streamlit
pipeline. Expanded explanatory variables are optional: failures are logged, but
they never interrupt the forecasting pipeline.
"""

from __future__ import annotations

import json
import os
import re
from io import BytesIO
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
import warnings

import pandas as pd
import requests


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = PROJECT_ROOT / "config" / "variable_sources.yaml"
MODEL_READY_PATH = PROJECT_ROOT / "data" / "processed" / "model_ready_data.xlsx"
RAW_VARIABLE_POOL_DIR = PROJECT_ROOT / "data" / "raw" / "variable_pool"
TABLES_DIR = PROJECT_ROOT / "outputs" / "tables"
UPLOADED_VARIABLE_MANIFEST = TABLES_DIR / "uploaded_variable_manifest.xlsx"

OUTPUT_PATHS = {
    "expanded_pool": TABLES_DIR / "expanded_variable_pool.xlsx",
    "download_status": TABLES_DIR / "variable_pool_download_status.xlsx",
    "coverage_report": TABLES_DIR / "variable_pool_coverage_report.xlsx",
    "quality_report": TABLES_DIR / "variable_pool_quality_filter_report.xlsx",
    "registry_table": TABLES_DIR / "variable_registry.xlsx",
    "date_alignment_report": TABLES_DIR / "variable_pool_date_alignment_report.xlsx",
}


def _safe_exception_text(exc: BaseException) -> str:
    """Return an ASCII-only exception summary for UI and reports."""
    message = str(exc).encode("ascii", errors="ignore").decode("ascii").strip()
    message = re.sub(r"\s+", " ", message)
    if message:
        return f"{type(exc).__name__}: {message}"
    return type(exc).__name__


def quality_filter_variables(
    data: pd.DataFrame,
    candidate_vars: list[str],
    end_date: str | pd.Timestamp | None = None,
    min_coverage: float = 0.6,
    max_missing_rate: float | None = None,
    max_stale_days: int = 14,
    min_variance: float = 1e-10,
) -> tuple[list[str], pd.DataFrame]:
    """Flag coverage issues while dropping only unusable variables.

    ``src.feature_selector`` also exposes a similar helper, but importing that
    module pulls in scikit-learn. The variable-pool update is part of the
    net-impact workflow and should not fail when a local Windows policy blocks
    sklearn DLL loading.
    Selected variables with date gaps are kept; strict complete-case cleaning
    removes only the dates where retained variables are missing.
    """
    if "Date" not in data.columns:
        raise ValueError("Data must contain Date for variable-pool quality screening.")

    prepared = data.copy()
    prepared["Date"] = pd.to_datetime(prepared["Date"], errors="coerce")
    prepared = prepared.dropna(subset=["Date"])
    if max_missing_rate is None:
        max_missing_rate = 1 - min_coverage
    end_timestamp = prepared["Date"].max() if end_date is None else pd.to_datetime(end_date)

    kept: list[str] = []
    rows: list[dict[str, Any]] = []
    for variable in candidate_vars:
        if variable not in prepared.columns:
            rows.append(
                {
                    "Variable": variable,
                    "Coverage": 0.0,
                    "MissingRate": 1.0,
                    "LatestDate": pd.NaT,
                    "Variance": pd.NA,
                    "Action": "Dropped_missing_column",
                    "Reason": "Variable column is not available.",
                }
            )
            continue

        series = pd.to_numeric(prepared[variable], errors="coerce")
        coverage = float(series.notna().mean()) if len(series) else 0.0
        missing_rate = 1 - coverage
        latest_date = prepared.loc[series.notna(), "Date"].max() if series.notna().any() else pd.NaT
        variance = float(series.dropna().var(ddof=0)) if series.notna().sum() else pd.NA

        drop_reasons: list[str] = []
        coverage_below_threshold = coverage < min_coverage or missing_rate > max_missing_rate
        if pd.isna(latest_date):
            drop_reasons.append("no_usable_values")
        elif end_timestamp - latest_date > pd.Timedelta(days=max_stale_days):
            drop_reasons.append("stale_latest_date")
        if pd.isna(variance) or float(variance) <= min_variance:
            drop_reasons.append("near_zero_variance")

        action = "Kept" if not drop_reasons else "Dropped_quality_filter"
        if action == "Kept":
            kept.append(variable)
        if drop_reasons:
            reason = "; ".join(drop_reasons)
        elif coverage_below_threshold:
            reason = (
                "Kept with coverage below threshold; missing dates will be removed "
                "during strict complete-case cleaning."
            )
        else:
            reason = "Passed quality filter."
        rows.append(
            {
                "Variable": variable,
                "Coverage": coverage,
                "MissingRate": missing_rate,
                "LatestDate": latest_date,
                "Variance": variance,
                "Action": action,
                "Reason": reason,
            }
        )

    return kept, pd.DataFrame(rows)


DEFAULT_VARIABLE_REGISTRY: list[dict[str, Any]] = [
    {
        "name": "WTI",
        "description": "WTI crude oil futures price.",
        "auto_download": False,
        "is_proxy": False,
        "frequency": "Daily",
        "daily_alignment": "Native daily series from market-data workflow.",
        "sources": [{"type": "existing_model_ready_column", "id": "WTI"}],
        "cache_file": "",
        "note": "Always loaded by the market-data workflow. It can be used as a target or as a candidate driver for another target.",
    },
    {
        "name": "GPRD",
        "description": "Traditional Caldara-Iacoviello daily geopolitical risk index.",
        "auto_download": False,
        "is_proxy": False,
        "frequency": "Daily",
        "daily_alignment": "Native daily series from the GPR workflow.",
        "sources": [{"type": "existing_model_ready_column", "id": "GPRD"}],
        "cache_file": "",
        "note": "Loaded by the existing GPRD workflow or local upload.",
    },
    {
        "name": "OVX",
        "description": "CBOE Crude Oil ETF Volatility Index.",
        "auto_download": True,
        "is_proxy": False,
        "frequency": "Daily",
        "daily_alignment": "Native daily series from FRED or Yahoo fallback via market-data workflow.",
        "sources": [
            {"type": "existing_model_ready_column", "id": "OVX"},
            {"type": "fred", "id": "OVXCLS"},
            {"type": "yfinance", "id": "^OVX"},
        ],
        "cache_file": "",
        "note": "FRED OVXCLS is preferred; Yahoo Finance OVX is used when FRED is unreachable.",
    },
    {
        "name": "DollarIndex",
        "description": "Broad U.S. dollar index.",
        "auto_download": True,
        "is_proxy": False,
        "frequency": "Daily",
        "daily_alignment": "Native daily series from FRED via market-data workflow.",
        "sources": [
            {"type": "existing_model_ready_column", "id": "DollarIndex"},
            {"type": "fred", "id": "DTWEXBGS"},
            {"type": "yfinance", "id": "DX-Y.NYB"},
            {"type": "yfinance", "id": "DX=F"},
        ],
        "cache_file": "data/raw/variable_pool/DollarIndex_FRED_DTWEXBGS.csv",
        "note": "Loaded from model-ready data when present; otherwise FRED DTWEXBGS is preferred with Yahoo DXY futures/index fallbacks when FRED is unreachable.",
    },
    {
        "name": "TNote10Y",
        "description": "10-year U.S. Treasury yield.",
        "auto_download": True,
        "is_proxy": False,
        "frequency": "Daily",
        "daily_alignment": "Native daily series from FRED, U.S. Treasury, or Yahoo fallback.",
        "sources": [
            {"type": "existing_model_ready_column", "id": "TNote10Y"},
            {"type": "fred", "id": "DGS10"},
            {"type": "treasury_yield_curve", "id": "10 Yr"},
            {"type": "yfinance", "id": "^TNX"},
        ],
        "cache_file": "",
        "note": "FRED DGS10 is preferred; the U.S. Treasury daily yield curve and Yahoo ^TNX are fallbacks.",
    },
    {
        "name": "Gold",
        "description": "Gold futures or London gold price proxy when futures data are unavailable.",
        "auto_download": False,
        "is_proxy": True,
        "frequency": "Daily",
        "daily_alignment": "Native daily market series when available.",
        "sources": [{"type": "existing_model_ready_column", "id": "Gold"}],
        "cache_file": "",
        "note": "Loaded by the existing gold workflow when available.",
    },
    {
        "name": "VIX",
        "description": "CBOE equity market volatility index.",
        "auto_download": True,
        "is_proxy": False,
        "frequency": "Daily",
        "daily_alignment": "Native daily series aligned to the analysis calendar.",
        "sources": [{"type": "fred", "id": "VIXCLS"}, {"type": "yfinance", "id": "^VIX"}],
        "cache_file": "data/raw/variable_pool/VIX_FRED_VIXCLS.csv",
        "note": "FRED VIXCLS is preferred; Yahoo Finance VIX is used when FRED is unreachable.",
    },
    {
        "name": "SP500",
        "description": "S&P 500 index.",
        "auto_download": True,
        "is_proxy": False,
        "frequency": "Daily",
        "daily_alignment": "Native daily series aligned to the analysis calendar.",
        "sources": [{"type": "fred", "id": "SP500"}, {"type": "yfinance", "id": "^GSPC"}],
        "cache_file": "data/raw/variable_pool/SP500_FRED_SP500.csv",
        "note": "FRED SP500 is preferred; Yahoo Finance S&P 500 is used when FRED is unreachable.",
    },
    {
        "name": "Nasdaq",
        "description": "NASDAQ Composite index.",
        "auto_download": True,
        "is_proxy": False,
        "frequency": "Daily",
        "daily_alignment": "Native daily series aligned to the analysis calendar.",
        "sources": [{"type": "fred", "id": "NASDAQCOM"}, {"type": "yfinance", "id": "^IXIC"}],
        "cache_file": "data/raw/variable_pool/Nasdaq_FRED_NASDAQCOM.csv",
        "note": "FRED NASDAQCOM is preferred; Yahoo Finance NASDAQ Composite is used when FRED is unreachable.",
    },
    {
        "name": "NaturalGas",
        "description": "Henry Hub natural gas spot price.",
        "auto_download": True,
        "is_proxy": True,
        "frequency": "Daily",
        "daily_alignment": "Native daily series aligned to the analysis calendar.",
        "sources": [{"type": "fred", "id": "DHHNGSP"}, {"type": "yfinance", "id": "NG=F"}],
        "cache_file": "data/raw/variable_pool/NaturalGas_FRED_DHHNGSP.csv",
        "note": "FRED Henry Hub spot price is preferred; Yahoo natural-gas futures are used as a daily proxy when FRED is unreachable.",
    },
    {
        "name": "US2Y",
        "description": "2-year U.S. Treasury yield.",
        "auto_download": True,
        "is_proxy": False,
        "frequency": "Daily",
        "daily_alignment": "Native daily series aligned to the analysis calendar.",
        "sources": [{"type": "fred", "id": "DGS2"}, {"type": "treasury_yield_curve", "id": "2 Yr"}],
        "cache_file": "data/raw/variable_pool/US2Y_FRED_DGS2.csv",
        "note": "FRED DGS2 is preferred; the U.S. Treasury daily yield curve is used when FRED is unreachable.",
    },
    {
        "name": "FedFunds",
        "description": "Effective federal funds rate.",
        "auto_download": True,
        "is_proxy": False,
        "frequency": "Daily",
        "daily_alignment": "Native daily series aligned to the analysis calendar.",
        "sources": [{"type": "fred", "id": "DFF"}, {"type": "nyfed_rate", "id": "EFFR"}],
        "cache_file": "data/raw/variable_pool/FedFunds_FRED_DFF.csv",
        "note": "FRED DFF is preferred; New York Fed EFFR is used when FRED is unreachable.",
    },
    {
        "name": "CNYUSD",
        "description": "Chinese yuan per U.S. dollar spot exchange rate.",
        "auto_download": True,
        "is_proxy": False,
        "frequency": "Daily",
        "daily_alignment": "Native daily series aligned to the analysis calendar.",
        "sources": [{"type": "fred", "id": "DEXCHUS"}, {"type": "yfinance", "id": "CNY=X"}],
        "cache_file": "data/raw/variable_pool/CNYUSD_FRED_DEXCHUS.csv",
        "note": "FRED DEXCHUS is preferred; Yahoo USD/CNY is used when FRED is unreachable.",
    },
    {
        "name": "ShanghaiSC",
        "description": "Shanghai INE crude oil futures main-contract settlement price.",
        "auto_download": True,
        "is_proxy": False,
        "frequency": "Daily",
        "daily_alignment": "Native daily futures series aligned to the analysis calendar.",
        "sources": [
            {"type": "exchange_futures_daily", "id": "INE:SC"},
            {"type": "sina_main_futures", "id": "SC0"},
        ],
        "cache_file": "data/raw/variable_pool/ShanghaiSC_INE_SC.csv",
        "note": (
            "Shanghai International Energy Exchange SC crude oil futures. The fast "
            "default uses daily main-continuous futures quotes; set "
            "PREFER_OFFICIAL_EXCHANGE_FUTURES=1 to force official exchange daily files."
        ),
    },
    {
        "name": "ShanghaiFU",
        "description": "Shanghai Futures Exchange fuel oil futures main-contract settlement price.",
        "auto_download": True,
        "is_proxy": False,
        "frequency": "Daily",
        "daily_alignment": "Native daily futures series aligned to the analysis calendar.",
        "sources": [
            {"type": "exchange_futures_daily", "id": "SHFE:FU"},
            {"type": "sina_main_futures", "id": "FU0"},
        ],
        "cache_file": "data/raw/variable_pool/ShanghaiFU_SHFE_FU.csv",
        "note": (
            "Shanghai Futures Exchange FU fuel oil futures. The fast default uses "
            "daily main-continuous futures quotes; set PREFER_OFFICIAL_EXCHANGE_FUTURES=1 "
            "to force official exchange daily files."
        ),
    },
    {
        "name": "Brent",
        "description": "Brent crude oil candidate variable.",
        "auto_download": True,
        "is_proxy": False,
        "frequency": "Daily",
        "daily_alignment": "Native daily futures series aligned to the analysis calendar.",
        "sources": [
            {"type": "existing_model_ready_column", "id": "Brent"},
            {"type": "fred", "id": "DCOILBRENTEU"},
            {"type": "yfinance", "id": "BZ=F"},
            {"type": "stooq", "id": "CB.F"},
            {"type": "stooq", "id": "SC.F"},
        ],
        "cache_file": "data/raw/variable_pool/Brent_BZ_F.csv",
        "note": "Brent crude oil futures. Existing market-data column is preferred; FRED API, yfinance, and Stooq are automatic fallbacks.",
    },
    {
        "name": "Gasoline",
        "description": "RBOB gasoline futures price.",
        "auto_download": True,
        "is_proxy": False,
        "frequency": "Daily",
        "daily_alignment": "Native daily futures series aligned to the analysis calendar.",
        "sources": [{"type": "yfinance", "id": "RB=F"}, {"type": "stooq", "id": "RB.F"}],
        "cache_file": "data/raw/variable_pool/Gasoline_RB_F.csv",
        "note": "RBOB gasoline futures from Yahoo Finance with Stooq fallback.",
    },
    {
        "name": "HeatingOil",
        "description": "Heating oil futures price.",
        "auto_download": True,
        "is_proxy": False,
        "frequency": "Daily",
        "daily_alignment": "Native daily futures series aligned to the analysis calendar.",
        "sources": [{"type": "yfinance", "id": "HO=F"}, {"type": "stooq", "id": "HO.F"}],
        "cache_file": "data/raw/variable_pool/HeatingOil_HO_F.csv",
        "note": "Heating oil futures from Yahoo Finance with Stooq fallback.",
    },
    {
        "name": "Copper",
        "description": "COMEX copper futures price.",
        "auto_download": True,
        "is_proxy": False,
        "frequency": "Daily",
        "daily_alignment": "Native daily futures series aligned to the analysis calendar.",
        "sources": [{"type": "yfinance", "id": "HG=F"}, {"type": "stooq", "id": "HG.F"}],
        "cache_file": "data/raw/variable_pool/Copper_HG_F.csv",
        "note": "COMEX copper futures from Yahoo Finance with Stooq fallback.",
    },
    {
        "name": "Silver",
        "description": "COMEX silver futures price.",
        "auto_download": True,
        "is_proxy": False,
        "frequency": "Daily",
        "daily_alignment": "Native daily futures series aligned to the analysis calendar.",
        "sources": [{"type": "yfinance", "id": "SI=F"}, {"type": "stooq", "id": "SI.F"}],
        "cache_file": "data/raw/variable_pool/Silver_SI_F.csv",
        "note": "COMEX silver futures from Yahoo Finance with Stooq fallback.",
    },
    {
        "name": "EPU",
        "description": "U.S. daily news-based economic policy uncertainty index.",
        "auto_download": True,
        "is_proxy": False,
        "frequency": "Daily",
        "daily_alignment": "Native daily series aligned to the analysis calendar.",
        "sources": [{"type": "fred", "id": "USEPUINDXD"}, {"type": "policy_uncertainty_daily", "id": "US"}],
        "cache_file": "data/raw/variable_pool/EPU_FRED_USEPUINDXD.csv",
        "note": "FRED USEPUINDXD is preferred; policyuncertainty.com daily U.S. EPU CSV is used when FRED is unreachable.",
    },
    {
        "name": "TPU",
        "description": "U.S. daily trade policy uncertainty index.",
        "auto_download": True,
        "is_proxy": False,
        "frequency": "Daily",
        "daily_alignment": "Native daily series aligned to the analysis calendar.",
        "sources": [{"type": "policy_uncertainty_daily", "id": "TPU"}],
        "cache_file": "data/raw/variable_pool/TPU_policy_uncertainty_daily.csv",
        "note": "Official policyuncertainty.com daily trade policy uncertainty index.",
    },
    {
        "name": "EMV",
        "description": "U.S. daily infectious disease equity-market volatility tracker.",
        "auto_download": True,
        "is_proxy": False,
        "frequency": "Daily",
        "daily_alignment": "Native daily series aligned to the analysis calendar.",
        "sources": [{"type": "policy_uncertainty_daily", "id": "EMV"}],
        "cache_file": "data/raw/variable_pool/EMV_policy_uncertainty_daily.csv",
        "note": "Official policyuncertainty.com daily infectious-disease EMV index.",
    },
]


def _resolve_project_path(path: str | Path) -> Path:
    """Resolve a relative path against the project root."""
    path = Path(path)
    if path.is_absolute():
        return path
    return PROJECT_ROOT / path


def ensure_variable_pool_dirs() -> None:
    """Create directories used by the variable-pool workflow."""
    RAW_VARIABLE_POOL_DIR.mkdir(parents=True, exist_ok=True)
    TABLES_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)


def _load_yaml_registry(path: Path) -> list[dict[str, Any]]:
    """Load a YAML registry when PyYAML is available."""
    try:
        import yaml  # type: ignore
    except ImportError as exc:
        raise RuntimeError("PyYAML is not installed; using the built-in registry.") from exc

    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if isinstance(raw, dict):
        entries = raw.get("variables", [])
    else:
        entries = raw
    if not isinstance(entries, list):
        raise ValueError("variable_sources.yaml must contain a variables list.")
    return [entry for entry in entries if isinstance(entry, dict)]


def _normalise_registry_entry(entry: dict[str, Any]) -> dict[str, Any]:
    """Fill optional registry fields with conservative defaults."""
    name = str(entry.get("name", "")).strip()
    sources = entry.get("sources") or []
    if isinstance(sources, dict):
        sources = [sources]
    return {
        "name": name,
        "description": str(entry.get("description", "")).strip(),
        "auto_download": bool(entry.get("auto_download", False)),
        "is_proxy": bool(entry.get("is_proxy", False)),
        "frequency": str(entry.get("frequency", "") or "").strip(),
        "daily_alignment": str(entry.get("daily_alignment", "") or "").strip(),
        "sources": [
            {"type": str(source.get("type", "")).strip(), "id": str(source.get("id", "")).strip()}
            for source in sources
            if isinstance(source, dict)
        ],
        "cache_file": str(entry.get("cache_file", "") or "").strip(),
        "note": str(entry.get("note", "")).strip(),
    }


def _load_uploaded_registry_entries() -> list[dict[str, Any]]:
    """Create registry entries for user-uploaded local variables."""
    if not UPLOADED_VARIABLE_MANIFEST.exists():
        return []
    try:
        manifest = pd.read_excel(UPLOADED_VARIABLE_MANIFEST)
    except Exception:
        return []
    if "VariableName" not in manifest.columns:
        return []

    entries: list[dict[str, Any]] = []
    for _, row in manifest.dropna(subset=["VariableName"]).iterrows():
        variable = str(row.get("VariableName", "")).strip()
        if not variable:
            continue
        saved_file = str(row.get("SavedFile", "") or "").strip()
        entries.append(
            {
                "name": variable,
                "description": f"User-uploaded local variable: {variable}.",
                "auto_download": False,
                "is_proxy": False,
                "sources": [{"type": "local_upload", "id": saved_file or variable}],
                "cache_file": f"data/raw/uploads/{saved_file}" if saved_file else "",
                "note": str(row.get("Note", "Registered from a local user upload.") or ""),
            }
        )
    return entries


def load_variable_registry(
    registry_path: str | Path = CONFIG_PATH,
) -> list[dict[str, Any]]:
    """Load the candidate-variable registry.

    The YAML file is preferred when it can be read. If it is missing or PyYAML is
    unavailable, a built-in registry is used so the application remains usable.
    """
    ensure_variable_pool_dirs()
    path = _resolve_project_path(registry_path)
    entries = DEFAULT_VARIABLE_REGISTRY
    if path.exists():
        try:
            yaml_entries = _load_yaml_registry(path)
            merged: dict[str, dict[str, Any]] = {
                str(entry.get("name", "")): entry for entry in DEFAULT_VARIABLE_REGISTRY
            }
            for entry in yaml_entries:
                name = str(entry.get("name", "")).strip()
                if name:
                    merged[name] = entry
            entries = [entry for entry in merged.values() if entry.get("name")]
        except Exception as exc:  # noqa: BLE001 - registry fallback should not block UI.
            warnings.warn(f"Could not read {path.name}: {_safe_exception_text(exc)}")

    normalised = [_normalise_registry_entry(entry) for entry in entries]
    uploaded_entries = [_normalise_registry_entry(entry) for entry in _load_uploaded_registry_entries()]
    merged: dict[str, dict[str, Any]] = {}
    for entry in [*normalised, *uploaded_entries]:
        if entry["name"]:
            merged[entry["name"]] = entry
    return list(merged.values())


def registry_to_dataframe(registry: list[dict[str, Any]]) -> pd.DataFrame:
    """Convert registry entries into a displayable table."""
    rows: list[dict[str, Any]] = []
    for entry in registry:
        sources = "; ".join(
            f"{source.get('type')}:{source.get('id')}"
            for source in entry.get("sources", [])
            if source.get("type") or source.get("id")
        )
        rows.append(
            {
                "Variable": entry["name"],
                "Description": entry.get("description", ""),
                "AutoDownload": entry.get("auto_download", False),
                "IsProxy": entry.get("is_proxy", False),
                "SourceFrequency": entry.get("frequency", ""),
                "DailyAlignment": entry.get("daily_alignment", ""),
                "Sources": sources,
                "CacheFile": entry.get("cache_file", ""),
                "Note": entry.get("note", ""),
            }
        )
    return pd.DataFrame(rows)


def _read_model_ready_data(model_ready_path: str | Path) -> pd.DataFrame:
    """Read model-ready data without dropping explanatory-variable tail gaps."""
    path = _resolve_project_path(model_ready_path)
    if not path.exists():
        raise FileNotFoundError(f"Model-ready data file not found: {path}")
    data = pd.read_excel(path)
    if "Date" not in data.columns or "WTI" not in data.columns:
        raise ValueError("model_ready_data.xlsx must contain Date and WTI.")
    data = data.copy()
    data["Date"] = _normalise_date_series(data["Date"])
    data = data.dropna(subset=["Date"])
    data = data.sort_values("Date").drop_duplicates(subset=["Date"], keep="last")
    return data.reset_index(drop=True)


def _normalise_date_series(values: pd.Series | list[Any]) -> pd.Series:
    """Return dates as a consistent pandas datetime64[ns] midnight series.

    Pandas can preserve different datetime resolutions after Excel/CSV/API
    reads, such as ``datetime64[s]`` and ``datetime64[us]``. Every
    variable-pool merge normalizes Date to the same nanosecond-resolution
    daily calendar before exact-date merging.
    """
    return pd.to_datetime(values, errors="coerce").dt.normalize().astype("datetime64[ns]")


def _series_has_values(data: pd.DataFrame, variable: str) -> bool:
    """Return True when a variable has at least one non-missing value."""
    return variable in data.columns and pd.to_numeric(data[variable], errors="coerce").notna().any()


def _variable_stats(data: pd.DataFrame, variable: str, selected_end_date: str | pd.Timestamp) -> dict[str, Any]:
    """Compute simple coverage and freshness statistics for one variable."""
    if variable not in data.columns or data.empty:
        return {
            "Coverage": 0.0,
            "MissingCount": len(data),
            "EarliestDate": pd.NaT,
            "LatestDate": pd.NaT,
            "StaleDays": None,
        }

    prepared = data[["Date", variable]].copy()
    prepared["Date"] = pd.to_datetime(prepared["Date"], errors="coerce")
    series = pd.to_numeric(prepared[variable], errors="coerce")
    coverage = float(series.notna().mean()) if len(series) else 0.0
    earliest = prepared.loc[series.notna(), "Date"].min() if series.notna().any() else pd.NaT
    latest = prepared.loc[series.notna(), "Date"].max() if series.notna().any() else pd.NaT
    end_timestamp = pd.to_datetime(selected_end_date)
    stale_days = None if pd.isna(latest) else int((end_timestamp - latest).days)
    return {
        "Coverage": coverage,
        "MissingCount": int(series.isna().sum()),
        "EarliestDate": earliest,
        "LatestDate": latest,
        "StaleDays": stale_days,
    }


def _variable_available_window(data: pd.DataFrame, variable: str) -> tuple[pd.Timestamp | pd.NaT, pd.Timestamp | pd.NaT, int]:
    """Return first/last non-missing dates for one variable."""
    if "Date" not in data.columns or variable not in data.columns or data.empty:
        return pd.NaT, pd.NaT, 0

    prepared = data[["Date", variable]].copy()
    prepared["Date"] = pd.to_datetime(prepared["Date"], errors="coerce")
    series = pd.to_numeric(prepared[variable], errors="coerce")
    valid_dates = prepared.loc[series.notna(), "Date"].dropna()
    if valid_dates.empty:
        return pd.NaT, pd.NaT, 0
    return valid_dates.min(), valid_dates.max(), int(valid_dates.count())


def _build_date_alignment_report(
    data: pd.DataFrame,
    variables: list[str],
) -> tuple[pd.DataFrame, pd.Timestamp | None, pd.Timestamp | None]:
    """Build a report and common non-missing date window across variables."""
    rows: list[dict[str, Any]] = []
    for variable in list(dict.fromkeys(str(item) for item in variables if str(item).strip())):
        earliest, latest, count = _variable_available_window(data, variable)
        rows.append(
            {
                "Variable": variable,
                "EarliestDate": earliest,
                "LatestDate": latest,
                "NonMissingCount": count,
                "Status": "Available" if count else "NoData",
            }
        )

    report = pd.DataFrame(rows)
    available = report[report["Status"].eq("Available")].copy() if not report.empty else pd.DataFrame()
    if available.empty:
        return report, None, None

    common_start = pd.to_datetime(available["EarliestDate"], errors="coerce").max()
    common_end = pd.to_datetime(available["LatestDate"], errors="coerce").min()
    start_limiters = available.loc[
        pd.to_datetime(available["EarliestDate"], errors="coerce").eq(common_start),
        "Variable",
    ].astype(str).tolist()
    end_limiters = available.loc[
        pd.to_datetime(available["LatestDate"], errors="coerce").eq(common_end),
        "Variable",
    ].astype(str).tolist()
    report["CommonStartDate"] = common_start
    report["CommonEndDate"] = common_end
    report["CommonWindowStatus"] = "OK" if common_start <= common_end else "NoOverlap"
    report["CommonStartLimitedBy"] = ", ".join(start_limiters)
    report["CommonEndLimitedBy"] = ", ".join(end_limiters)
    report["AlignmentNote"] = (
        "Common window starts at the latest first available date "
        f"({common_start:%Y-%m-%d}, limited by {', '.join(start_limiters)}) "
        "and ends at the earliest last available date "
        f"({common_end:%Y-%m-%d}, limited by {', '.join(end_limiters)})."
    )
    return report, common_start, common_end


def _trim_to_common_available_window(
    data: pd.DataFrame,
    variables: list[str],
) -> tuple[pd.DataFrame, pd.DataFrame, pd.Timestamp | None, pd.Timestamp | None]:
    """Trim rows to the common first/last available dates for selected variables."""
    if "Date" not in data.columns or data.empty:
        return data, pd.DataFrame(), None, None

    prepared = data.copy()
    prepared["Date"] = _normalise_date_series(prepared["Date"])
    report, common_start, common_end = _build_date_alignment_report(prepared, variables)
    if common_start is None or common_end is None or common_start > common_end:
        return prepared, report, common_start, common_end

    trimmed = prepared[
        (prepared["Date"] >= common_start)
        & (prepared["Date"] <= common_end)
    ].copy()
    return trimmed.reset_index(drop=True), report, common_start, common_end


def _merge_variable(
    base: pd.DataFrame,
    variable_data: pd.DataFrame,
    variable: str,
    prefer_existing: bool = True,
    align_to_base_dates: bool = False,
) -> pd.DataFrame:
    """Merge one variable into the base model-ready data without filling missing dates."""
    if variable_data.empty or "Date" not in variable_data.columns or variable not in variable_data.columns:
        return base

    data = variable_data[["Date", variable]].copy()
    data["Date"] = _normalise_date_series(data["Date"])
    data[variable] = pd.to_numeric(data[variable], errors="coerce")
    data = data.dropna(subset=["Date"])
    data = data.sort_values("Date").drop_duplicates(subset=["Date"], keep="last")
    merged_base = base.copy()
    merged_base["Date"] = _normalise_date_series(merged_base["Date"])
    data["Date"] = _normalise_date_series(data["Date"])
    merged = merged_base.merge(data, on="Date", how="left", suffixes=("", "_downloaded"))
    downloaded_column = f"{variable}_downloaded"
    if downloaded_column in merged.columns:
        if prefer_existing and variable in merged.columns:
            merged[variable] = merged[variable].combine_first(merged[downloaded_column])
        elif variable in merged.columns:
            merged[variable] = merged[downloaded_column].combine_first(merged[variable])
        else:
            merged[variable] = merged[downloaded_column]
        merged = merged.drop(columns=[downloaded_column])
    return merged


def _fetch_eia_excel_registry_variable(
    entry: dict[str, Any],
    start_date: str,
    end_date: str,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Fetch an EIA historical Excel series and return a two-column DataFrame."""
    variable = entry["name"]
    source = next(
        (source for source in entry.get("sources", []) if source.get("type") == "eia_excel"),
        {},
    )
    series_id = str(source.get("id") or variable).strip()
    cache_file = entry.get("cache_file") or f"data/raw/variable_pool/{variable}_{series_id}.csv"
    status_row: dict[str, Any] = {
        "Variable": variable,
        "AutoDownload": True,
        "ActualSource": f"eia_excel:{series_id}",
        "Status": "Failed",
        "IsProxy": bool(entry.get("is_proxy", False)),
        "SourceFrequency": entry.get("frequency", "Weekly"),
        "DailyAligned": True,
        "LatestDate": pd.NaT,
        "MissingCount": None,
        "Coverage": None,
        "Note": "",
    }
    url = f"https://www.eia.gov/dnav/pet/hist_xls/{series_id}w.xls"
    try:
        response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
        response.raise_for_status()
        raw = pd.read_excel(BytesIO(response.content), sheet_name="Data 1", header=None)
        date_values = pd.to_datetime(raw.iloc[:, 0], errors="coerce")
        value_values = pd.to_numeric(raw.iloc[:, 1], errors="coerce")
        data = pd.DataFrame({"Date": date_values, variable: value_values})
        data = data.dropna(subset=["Date", variable])
        data = data.sort_values("Date").drop_duplicates(subset=["Date"], keep="last")
        start_timestamp = pd.to_datetime(start_date)
        end_timestamp = pd.to_datetime(end_date)
        data = data[(data["Date"] >= start_timestamp) & (data["Date"] <= end_timestamp)]
        data = data.reset_index(drop=True)
        if not _series_has_values(data, variable):
            raise ValueError(f"EIA Excel {series_id} returned no usable values.")
        cache_path = _resolve_project_path(cache_file)
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        data.to_csv(cache_path, index=False)
        stats = _variable_stats(data, variable, end_date)
        status_row.update(
            {
                "Status": "Downloaded",
                "LatestDate": stats["LatestDate"],
                "MissingCount": stats["MissingCount"],
                "Coverage": stats["Coverage"],
                "Note": (
                    "Downloaded from the official EIA historical Excel file. "
                    "The weekly source is forward-filled to the daily analysis calendar."
                ),
            }
        )
        return data, status_row
    except Exception as exc:  # noqa: BLE001 - candidate failures must not interrupt the pipeline.
        cached = _load_variable_cache(cache_file, variable, start_date, end_date)
        if _series_has_values(cached, variable):
            stats = _variable_stats(cached, variable, end_date)
            status_row.update(
                {
                    "ActualSource": f"cache:{Path(cache_file).name}",
                    "Status": "LoadedCacheAfterEIAFailure",
                    "LatestDate": stats["LatestDate"],
                    "MissingCount": stats["MissingCount"],
                    "Coverage": stats["Coverage"],
                    "Note": f"EIA Excel download failed; loaded local cache. {_safe_exception_text(exc)}",
                }
            )
            return cached, status_row
        status_row["Note"] = (
            "EIA Excel download failed and no usable cache was available: "
            f"{_safe_exception_text(exc)}"
        )
        return pd.DataFrame(columns=["Date", variable]), status_row


def _fetch_local_upload_variable(
    entry: dict[str, Any],
    start_date: str,
    end_date: str,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Load a user-uploaded variable registered in the local manifest."""
    variable = entry["name"]
    status_row: dict[str, Any] = {
        "Variable": variable,
        "AutoDownload": False,
        "ActualSource": "local_upload",
        "Status": "LocalUploadMissing",
        "IsProxy": bool(entry.get("is_proxy", False)),
        "SourceFrequency": entry.get("frequency", "UserUpload"),
        "DailyAligned": False,
        "LatestDate": pd.NaT,
        "MissingCount": None,
        "Coverage": None,
        "Note": entry.get("note", ""),
    }
    upload_sources = [
        source
        for source in entry.get("sources", [])
        if source.get("type") == "local_upload" and source.get("id")
    ]
    candidate_paths: list[Path] = []
    for source in upload_sources:
        source_id = str(source.get("id", "")).strip()
        if not source_id:
            continue
        candidate_paths.append(PROJECT_ROOT / "data" / "raw" / "uploads" / source_id)
        candidate_paths.append(PROJECT_ROOT / "data" / "raw" / "uploads" / f"{source_id}.csv")
    cache_file = str(entry.get("cache_file", "") or "").strip()
    if cache_file:
        candidate_paths.append(_resolve_project_path(cache_file))
    candidate_paths.append(PROJECT_ROOT / "data" / "raw" / "uploads" / f"{variable}.csv")

    for path in candidate_paths:
        if not path.exists() or not path.is_file():
            continue
        try:
            if path.suffix.lower() == ".csv":
                raw = pd.read_csv(path)
            elif path.suffix.lower() in {".xlsx", ".xls"}:
                raw = pd.read_excel(path)
            else:
                continue
            if "Date" not in raw.columns or variable not in raw.columns:
                continue
            data = raw[["Date", variable]].copy()
            data["Date"] = pd.to_datetime(data["Date"], errors="coerce")
            data[variable] = pd.to_numeric(data[variable], errors="coerce")
            data = data.dropna(subset=["Date"])
            data = data.sort_values("Date").drop_duplicates(subset=["Date"], keep="last")
            start_timestamp = pd.to_datetime(start_date)
            end_timestamp = pd.to_datetime(end_date)
            data = data[(data["Date"] >= start_timestamp) & (data["Date"] <= end_timestamp)]
            data = data.reset_index(drop=True)
            if _series_has_values(data, variable):
                stats = _variable_stats(data, variable, end_date)
                status_row.update(
                    {
                        "ActualSource": f"local_upload:{path.name}",
                        "Status": "LocalUploadLoaded",
                        "LatestDate": stats["LatestDate"],
                        "MissingCount": stats["MissingCount"],
                        "Coverage": stats["Coverage"],
                        "Note": "Loaded from a user-uploaded local variable file.",
                    }
                )
                return data, status_row
        except Exception as exc:  # noqa: BLE001 - try the next candidate path.
            status_row["Note"] = f"Could not read local upload {path.name}: {_safe_exception_text(exc)}"
            continue
    return pd.DataFrame(columns=["Date", variable]), status_row


def _load_variable_cache(
    cache_file: str | Path,
    variable: str,
    start_date: str,
    end_date: str,
) -> pd.DataFrame:
    """Load a cached two-column variable file when an online source is unavailable."""
    cache_path = _resolve_project_path(cache_file)
    if not cache_path.exists() or not cache_path.is_file():
        return pd.DataFrame(columns=["Date", variable])
    try:
        if cache_path.suffix.lower() == ".csv":
            data = pd.read_csv(cache_path)
        elif cache_path.suffix.lower() in {".xlsx", ".xls"}:
            data = pd.read_excel(cache_path)
        else:
            return pd.DataFrame(columns=["Date", variable])
        if "Date" not in data.columns or variable not in data.columns:
            return pd.DataFrame(columns=["Date", variable])
        prepared = data[["Date", variable]].copy()
        prepared["Date"] = pd.to_datetime(prepared["Date"], errors="coerce")
        prepared[variable] = pd.to_numeric(prepared[variable], errors="coerce")
        prepared = prepared.dropna(subset=["Date"])
        prepared = prepared.sort_values("Date").drop_duplicates(subset=["Date"], keep="last")
        start_timestamp = pd.to_datetime(start_date)
        end_timestamp = pd.to_datetime(end_date)
        prepared = prepared[
            (prepared["Date"] >= start_timestamp) & (prepared["Date"] <= end_timestamp)
        ]
        return prepared.reset_index(drop=True)
    except Exception as exc:  # noqa: BLE001 - cache failures should be reported as empty.
        warnings.warn(f"Could not read cached variable {variable}: {_safe_exception_text(exc)}")
        return pd.DataFrame(columns=["Date", variable])


def _exchange_daily_url(market: str, date_text: str) -> str:
    """Return the official SHFE/INE daily futures JSON URL."""
    market = market.upper().strip()
    if market == "INE":
        return f"https://www.ine.cn/data/tradedata/future/dailydata/kx{date_text}.dat"
    if market == "SHFE":
        return f"https://www.shfe.com.cn/data/tradedata/future/dailydata/kx{date_text}.dat"
    raise ValueError(f"Unsupported exchange futures market: {market}")


def _rows_from_exchange_payload(payload: dict[str, Any], market: str, trade_date: pd.Timestamp) -> pd.DataFrame:
    """Parse one official SHFE/INE daily JSON payload into a normalized table."""
    rows = payload.get("o_curinstrument") or []
    if not rows:
        return pd.DataFrame()
    raw = pd.DataFrame(rows)
    if raw.empty:
        return pd.DataFrame()
    raw = raw[
        ~raw.astype(str)
        .apply(lambda col: col.str.contains("\u5c0f\u8ba1|\u5408\u8ba1|\u603b\u8ba1", na=False))
        .any(axis=1)
    ]
    product_group = raw.get("PRODUCTGROUPID")
    if product_group is None:
        product_group = raw.get("PRODUCTID", pd.Series(index=raw.index, dtype=object))
    delivery = raw.get("DELIVERYMONTH", pd.Series(index=raw.index, dtype=object))
    variety = product_group.astype(str).str.upper().str.strip().str.split("_", expand=True).iloc[:, 0]
    parsed = pd.DataFrame(
        {
            "Date": trade_date.normalize(),
            "symbol": variety + delivery.astype(str).str.strip(),
            "variety": variety,
            "close": pd.to_numeric(raw.get("CLOSEPRICE"), errors="coerce"),
            "settle": pd.to_numeric(raw.get("SETTLEMENTPRICE"), errors="coerce"),
            "volume": pd.to_numeric(raw.get("VOLUME"), errors="coerce").fillna(0),
            "open_interest": pd.to_numeric(raw.get("OPENINTEREST"), errors="coerce"),
        }
    )
    return parsed.dropna(subset=["variety"])


def _fetch_exchange_futures_direct(
    market: str,
    variety: str,
    variable: str,
    start_date: str,
    end_date: str,
    max_consecutive_failures: int = 3,
) -> pd.DataFrame:
    """Fetch an official exchange main-contract daily series.

    The main contract is selected independently each trading day as the contract
    with the largest volume for the requested variety. Settlement price is used
    first; close price is used only when settlement is absent or zero.
    """
    start_timestamp = pd.to_datetime(start_date).normalize()
    end_timestamp = pd.to_datetime(end_date).normalize()
    if pd.isna(start_timestamp) or pd.isna(end_timestamp) or start_timestamp > end_timestamp:
        return pd.DataFrame(columns=["Date", variable])

    import requests

    headers = {"User-Agent": "Mozilla/4.0 (compatible; MSIE 5.5; Windows NT)"}
    frames: list[pd.DataFrame] = []
    consecutive_failures = 0
    for trade_date in pd.bdate_range(start_timestamp, end_timestamp):
        date_text = trade_date.strftime("%Y%m%d")
        try:
            response = requests.get(
                _exchange_daily_url(market, date_text),
                headers=headers,
                timeout=6,
            )
            if response.status_code in {403, 404}:
                continue
            response.raise_for_status()
            payload = response.json()
            parsed = _rows_from_exchange_payload(payload, market, trade_date)
            if parsed.empty:
                continue
            selected = parsed[parsed["variety"].astype(str).str.upper().eq(variety.upper())].copy()
            if selected.empty:
                continue
            selected = selected.sort_values(["volume", "open_interest"], ascending=False)
            row = selected.iloc[0]
            value = row.get("settle")
            if pd.isna(value) or float(value) == 0:
                value = row.get("close")
            if pd.notna(value):
                frames.append(
                    pd.DataFrame(
                        {
                            "Date": [trade_date.normalize()],
                            variable: [float(value)],
                            "SelectedContract": [row.get("symbol")],
                            "Volume": [row.get("volume")],
                        }
                    )
                )
            consecutive_failures = 0
        except Exception:
            consecutive_failures += 1
            if consecutive_failures >= max_consecutive_failures:
                raise
            continue
    if not frames:
        return pd.DataFrame(columns=["Date", variable])
    data = pd.concat(frames, ignore_index=True)
    data = data.sort_values("Date").drop_duplicates(subset=["Date"], keep="last")
    return data[["Date", variable]].reset_index(drop=True)


def _fetch_sina_main_futures(
    symbol: str,
    variable: str,
    start_date: str,
    end_date: str,
) -> pd.DataFrame:
    """Fetch a fast daily main-continuous futures series from Sina via AKShare."""
    try:
        import akshare as ak
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError("akshare is required for Sina futures fallback. Install akshare.") from exc
    raw = ak.futures_zh_daily_sina(symbol=symbol)
    if raw is None or raw.empty:
        return pd.DataFrame(columns=["Date", variable])
    data = raw.copy()
    data["Date"] = pd.to_datetime(data.get("date"), errors="coerce")
    settle = pd.to_numeric(data.get("settle"), errors="coerce")
    close = pd.to_numeric(data.get("close"), errors="coerce")
    data[variable] = settle.where(settle.notna() & (settle != 0), close)
    start_timestamp = pd.to_datetime(start_date).normalize()
    end_timestamp = pd.to_datetime(end_date).normalize()
    data = data.dropna(subset=["Date", variable])
    data["Date"] = _normalise_date_series(data["Date"])
    data = data[(data["Date"] >= start_timestamp) & (data["Date"] <= end_timestamp)]
    data = data.sort_values("Date").drop_duplicates(subset=["Date"], keep="last")
    return data[["Date", variable]].reset_index(drop=True)


def _fetch_exchange_main_futures_variable(
    entry: dict[str, Any],
    start_date: str,
    end_date: str,
    force_refresh: bool = False,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Download Shanghai SC/FU main-contract futures from official/fallback sources."""
    variable = entry["name"]
    cache_file = entry.get("cache_file") or f"data/raw/variable_pool/{variable}.csv"
    status_row: dict[str, Any] = {
        "Variable": variable,
        "AutoDownload": True,
        "ActualSource": "not_attempted",
        "Status": "Failed",
        "IsProxy": bool(entry.get("is_proxy", False)),
        "SourceFrequency": entry.get("frequency", "Daily"),
        "DailyAligned": bool(entry.get("daily_alignment", "")),
        "LatestDate": pd.NaT,
        "MissingCount": None,
        "Coverage": None,
        "Note": "",
    }

    sources = entry.get("sources", [])
    exchange_source = next((source for source in sources if source.get("type") == "exchange_futures_daily"), None)
    sina_source = next((source for source in sources if source.get("type") == "sina_main_futures"), None)
    cached = _load_variable_cache(cache_file, variable, start_date, end_date)
    prefer_official = str(os.getenv("PREFER_OFFICIAL_EXCHANGE_FUTURES", "")).strip().lower() in {
        "1",
        "true",
        "yes",
    }

    start_timestamp = pd.to_datetime(start_date).normalize()
    end_timestamp = pd.to_datetime(end_date).normalize()
    fetch_start = start_timestamp
    if _series_has_values(cached, variable):
        valid_cache_dates = pd.to_datetime(
            cached.loc[pd.to_numeric(cached[variable], errors="coerce").notna(), "Date"]
        )
        latest_cached = valid_cache_dates.max()
        earliest_cached = valid_cache_dates.min()
        covers_requested_start = pd.notna(earliest_cached) and earliest_cached <= start_timestamp + pd.Timedelta(days=7)
        covers_requested_end = pd.notna(latest_cached) and latest_cached >= end_timestamp - pd.Timedelta(days=3)
        if covers_requested_start and covers_requested_end:
            stats = _variable_stats(cached, variable, end_date)
            status_row.update(
                {
                    "ActualSource": f"cache:{Path(cache_file).name}",
                    "Status": "LoadedFreshCache",
                    "LatestDate": stats["LatestDate"],
                    "MissingCount": stats["MissingCount"],
                    "Coverage": stats["Coverage"],
                    "Note": "Loaded a fresh cached exchange futures series.",
                }
            )
            return cached, status_row
        if pd.notna(latest_cached) and covers_requested_start:
            fetch_start = max(start_timestamp, latest_cached + pd.Timedelta(days=1))

    errors: list[str] = []
    downloaded = pd.DataFrame(columns=["Date", variable])
    actual_source = ""

    if not prefer_official and sina_source is not None:
        try:
            downloaded = _fetch_sina_main_futures(
                str(sina_source.get("id")),
                variable,
                start_date,
                end_date,
            )
            if _series_has_values(downloaded, variable):
                actual_source = f"sina_main_futures:{sina_source.get('id')}"
        except Exception as exc:  # noqa: BLE001
            errors.append(f"Sina main futures source failed: {_safe_exception_text(exc)}")

    if not _series_has_values(downloaded, variable) and exchange_source is not None:
        try:
            market, variety = str(exchange_source.get("id", "")).split(":", 1)
            downloaded = _fetch_exchange_futures_direct(
                market=market,
                variety=variety,
                variable=variable,
                start_date=fetch_start.strftime("%Y-%m-%d"),
                end_date=end_timestamp.strftime("%Y-%m-%d"),
            )
            if _series_has_values(downloaded, variable):
                actual_source = f"official_exchange:{market.upper()}:{variety.upper()}"
        except Exception as exc:  # noqa: BLE001 - fallback below keeps pipeline usable.
            errors.append(f"official exchange source failed: {_safe_exception_text(exc)}")

    if not _series_has_values(downloaded, variable) and sina_source is not None:
        try:
            downloaded = _fetch_sina_main_futures(
                str(sina_source.get("id")),
                variable,
                start_date,
                end_date,
            )
            if _series_has_values(downloaded, variable):
                actual_source = f"sina_main_futures:{sina_source.get('id')}"
        except Exception as exc:  # noqa: BLE001
            errors.append(f"Sina main futures fallback failed: {_safe_exception_text(exc)}")

    if _series_has_values(cached, variable) and _series_has_values(downloaded, variable):
        combined = pd.concat([cached, downloaded], ignore_index=True)
    elif _series_has_values(downloaded, variable):
        combined = downloaded
    else:
        combined = cached

    if _series_has_values(combined, variable):
        combined["Date"] = _normalise_date_series(combined["Date"])
        combined[variable] = pd.to_numeric(combined[variable], errors="coerce")
        combined = combined.dropna(subset=["Date"])
        combined = combined.sort_values("Date").drop_duplicates(subset=["Date"], keep="last")
        combined = combined[(combined["Date"] >= start_timestamp) & (combined["Date"] <= end_timestamp)]
        cache_path = _resolve_project_path(cache_file)
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        combined.to_csv(cache_path, index=False)
        stats = _variable_stats(combined, variable, end_date)
        status_row.update(
            {
                "ActualSource": actual_source or f"cache:{Path(cache_file).name}",
                "Status": "Downloaded" if actual_source else "LoadedCacheAfterSourceFailure",
                "LatestDate": stats["LatestDate"],
                "MissingCount": stats["MissingCount"],
                "Coverage": stats["Coverage"],
                "Note": (
                    "Daily main-contract futures series. The fast default uses the daily "
                    "main-continuous quote source to avoid long official per-day downloads; "
                    "set PREFER_OFFICIAL_EXCHANGE_FUTURES=1 to force the official exchange "
                    f"daily-file path. {' | '.join(errors)}"
                ).strip(),
            }
        )
        return combined[["Date", variable]].reset_index(drop=True), status_row

    status_row["Note"] = "No usable exchange futures data were available. " + " | ".join(errors)
    return pd.DataFrame(columns=["Date", variable]), status_row


def _fetch_registry_variable(
    entry: dict[str, Any],
    start_date: str,
    end_date: str,
    force_refresh: bool = False,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Try to download one registry variable and return data plus status row."""
    variable = entry["name"]
    status_row: dict[str, Any] = {
        "Variable": variable,
        "AutoDownload": bool(entry.get("auto_download", False)),
        "ActualSource": "not_attempted",
        "Status": "RegistryOnly",
        "IsProxy": bool(entry.get("is_proxy", False)),
        "SourceFrequency": entry.get("frequency", ""),
        "DailyAligned": bool(entry.get("daily_alignment", "")),
        "LatestDate": pd.NaT,
        "MissingCount": None,
        "Coverage": None,
        "Note": entry.get("note", ""),
    }
    if not entry.get("auto_download", False):
        return pd.DataFrame(columns=["Date", variable]), status_row

    if any(source.get("type") == "exchange_futures_daily" for source in entry.get("sources", [])):
        return _fetch_exchange_main_futures_variable(entry, start_date, end_date, force_refresh=force_refresh)
    if any(source.get("type") == "eia_excel" for source in entry.get("sources", [])):
        return _fetch_eia_excel_registry_variable(entry, start_date, end_date)

    sources = [
        {"type": source["type"], "id": source["id"]}
        for source in entry.get("sources", [])
        if source.get("type")
        and source.get("id")
        and source.get("type") not in {"existing_model_ready_column", "local_upload"}
    ]
    if not sources:
        status_row["Status"] = "NoAutomaticSource"
        status_row["Note"] = f"{entry.get('note', '')} No automatic source is configured."
        return pd.DataFrame(columns=["Date", variable]), status_row

    cache_file = entry.get("cache_file") or f"data/raw/variable_pool/{variable}.csv"
    if not force_refresh:
        cached = _load_variable_cache(cache_file, variable, start_date, end_date)
        if _series_has_values(cached, variable):
            stats = _variable_stats(cached, variable, end_date)
            latest_date = stats.get("LatestDate")
            stale_days = stats.get("StaleDays")
            if pd.notna(latest_date) and (stale_days is None or stale_days <= 14):
                status_row.update(
                    {
                        "ActualSource": f"cache:{Path(cache_file).name}",
                        "Status": "LoadedFreshCache",
                        "LatestDate": stats["LatestDate"],
                        "MissingCount": stats["MissingCount"],
                        "Coverage": stats["Coverage"],
                        "Note": "Loaded a fresh cached variable-pool series to avoid repeated slow online refresh.",
                    }
                )
                return cached, status_row

    try:
        from src.data_fetcher import LAST_SOURCE_NOTES, LAST_SOURCE_USED, fetch_series_with_fallback

        data = fetch_series_with_fallback(
            variable,
            sources,
            start_date,
            end_date,
            _resolve_project_path(cache_file),
            force_refresh=force_refresh,
        )
        if _series_has_values(data, variable):
            stats = _variable_stats(data, variable, end_date)
            actual_source = LAST_SOURCE_USED.get(variable, "automatic")
            status_row.update(
                {
                    "ActualSource": actual_source,
                    "Status": _status_for_returned_source(actual_source),
                    "LatestDate": stats["LatestDate"],
                    "MissingCount": stats["MissingCount"],
                    "Coverage": stats["Coverage"],
                    "Note": LAST_SOURCE_NOTES.get(variable, entry.get("note", "")),
                }
            )
            return data, status_row

        fred_sources = [source for source in sources if source.get("type") == "fred"]
        for source in fred_sources:
            try:
                data = _fetch_fred_series_http(
                    series_id=source["id"],
                    name=variable,
                    start_date=start_date,
                    end_date=end_date,
                    cache_file=_resolve_project_path(cache_file),
                )
            except Exception as exc:  # noqa: BLE001 - keep trying other registry sources.
                status_row["Note"] = (
                    f"{status_row.get('Note', '')} FRED HTTP fallback failed: "
                    f"{_safe_exception_text(exc)}"
                )
                continue
            if _series_has_values(data, variable):
                stats = _variable_stats(data, variable, end_date)
                status_row.update(
                    {
                        "ActualSource": f"fred_http:{source['id']}",
                        "Status": "Downloaded",
                        "LatestDate": stats["LatestDate"],
                        "MissingCount": stats["MissingCount"],
                        "Coverage": stats["Coverage"],
                        "Note": "Downloaded with FRED HTTP API fallback.",
                    }
                )
                return data, status_row

        status_row.update(
            {
                "ActualSource": LAST_SOURCE_USED.get(variable, "automatic_failed"),
                "Status": "Failed",
                "Note": LAST_SOURCE_NOTES.get(variable, "Automatic source and cache did not provide usable data."),
            }
        )
        return pd.DataFrame(columns=["Date", variable]), status_row
    except Exception as exc:  # noqa: BLE001 - candidate failures must not break the pipeline.
        status_row.update(
            {
                "ActualSource": "automatic_failed",
                "Status": "Failed",
                "Note": f"{entry.get('note', '')} Download failed: {_safe_exception_text(exc)}",
            }
        )
        warnings.warn(f"Expanded variable {variable} was not downloaded: {_safe_exception_text(exc)}")
        return pd.DataFrame(columns=["Date", variable]), status_row


def _fetch_fred_series_http(
    series_id: str,
    name: str,
    start_date: str,
    end_date: str,
    cache_file: str | Path,
) -> pd.DataFrame:
    """Download one FRED series through the shared robust FRED downloader."""
    from src.data_fetcher import fetch_fred_series

    return fetch_fred_series(
        series_id=series_id,
        name=name,
        start_date=start_date,
        end_date=end_date,
        cache_file=_resolve_project_path(cache_file),
    )


def _build_coverage_report(
    data: pd.DataFrame,
    registry: list[dict[str, Any]],
    end_date: str | pd.Timestamp,
) -> pd.DataFrame:
    """Build a variable coverage report for current model-ready rows."""
    rows: list[dict[str, Any]] = []
    for entry in registry:
        variable = entry["name"]
        stats = _variable_stats(data, variable, end_date)
        rows.append(
            {
                "Variable": variable,
                "InExpandedPool": variable in data.columns,
                "Coverage": stats["Coverage"],
                "MissingCount": stats["MissingCount"],
                "EarliestDate": stats["EarliestDate"],
                "LatestDate": stats["LatestDate"],
                "StaleDays": stats["StaleDays"],
                "AutoDownload": entry.get("auto_download", False),
                "IsProxy": entry.get("is_proxy", False),
                "SourceFrequency": entry.get("frequency", ""),
                "DailyAligned": bool(entry.get("daily_alignment", "")),
                "Note": entry.get("note", ""),
            }
        )
    return pd.DataFrame(rows)


def _status_for_returned_source(actual_source: str) -> str:
    """Map a returned source label to the status shown in review tables."""
    source_key = str(actual_source or "").strip().lower()
    if source_key.startswith("cache:"):
        return "LoadedCacheAfterSourceFailure"
    if source_key in {"empty", "outdated", "automatic_failed"}:
        return "Failed"
    return "Downloaded"


def build_expanded_variable_pool(
    start_date: str,
    end_date: str,
    model_ready_path: str | Path = MODEL_READY_PATH,
    registry_path: str | Path = CONFIG_PATH,
    output_path: str | Path = OUTPUT_PATHS["expanded_pool"],
    auto_download: bool = True,
    force_refresh: bool = False,
    prefer_existing: bool = True,
    merge_to_model_ready: bool = True,
    min_coverage: float = 0.6,
    max_stale_days: int = 14,
    selected_variables: list[str] | None = None,
    protected_variables: list[str] | None = None,
) -> pd.DataFrame:
    """Build and optionally merge the expanded explanatory-variable pool.

    WTI rows are preserved. Candidate variable download failures are recorded in
    the status log and do not interrupt the caller.
    """
    ensure_variable_pool_dirs()
    full_registry = load_variable_registry(registry_path)
    selected_set = {str(variable) for variable in selected_variables or []}
    if selected_variables is None:
        registry = full_registry
    else:
        registry = [entry for entry in full_registry if entry["name"] in selected_set]

    registry_df = registry_to_dataframe(full_registry)
    if selected_variables is None:
        registry_df["SelectedForPool"] = True
    else:
        registry_df["SelectedForPool"] = registry_df["Variable"].astype(str).isin(selected_set)
    registry_df.to_excel(OUTPUT_PATHS["registry_table"], index=False)

    expanded = _read_model_ready_data(model_ready_path)
    status_rows: list[dict[str, Any]] = []
    if selected_variables is not None:
        for entry in full_registry:
            if entry["name"] not in selected_set:
                status_rows.append(
                    {
                        "Variable": entry["name"],
                        "AutoDownload": bool(entry.get("auto_download", False)),
                        "ActualSource": "not_selected",
                        "Status": "NotSelected",
                        "IsProxy": bool(entry.get("is_proxy", False)),
                        "SourceFrequency": entry.get("frequency", ""),
                        "DailyAligned": bool(entry.get("daily_alignment", "")),
                        "LatestDate": pd.NaT,
                        "MissingCount": None,
                        "Coverage": None,
                        "Note": "Variable was not selected for the candidate pool in the UI.",
                    }
                )

    for entry in registry:
        variable = entry["name"]
        existing = _series_has_values(expanded, variable)
        if existing:
            stats = _variable_stats(expanded, variable, end_date)
            status_rows.append(
                {
                    "Variable": variable,
                    "AutoDownload": bool(entry.get("auto_download", False)),
                    "ActualSource": "model_ready_data.xlsx",
                    "Status": "ExistingModelReady",
                    "IsProxy": bool(entry.get("is_proxy", False)),
                    "SourceFrequency": entry.get("frequency", ""),
                    "DailyAligned": bool(entry.get("daily_alignment", "")),
                    "LatestDate": stats["LatestDate"],
                    "MissingCount": stats["MissingCount"],
                    "Coverage": stats["Coverage"],
                    "Note": "Existing model-ready column retained.",
                }
            )
            existing_is_usable = (
                stats.get("Coverage", 0.0) >= min_coverage
                and (
                    stats.get("StaleDays") is None
                    or stats.get("StaleDays") <= max_stale_days
                )
            )
            if prefer_existing and existing_is_usable and not force_refresh:
                continue

        has_local_upload_source = any(
            source.get("type") == "local_upload" for source in entry.get("sources", [])
        )
        if has_local_upload_source:
            uploaded, status = _fetch_local_upload_variable(entry, start_date, end_date)
            expanded = _merge_variable(
                expanded,
                uploaded,
                variable,
                prefer_existing=prefer_existing,
            )
            if _series_has_values(expanded, variable):
                stats = _variable_stats(expanded, variable, end_date)
                status.update(
                    {
                        "LatestDate": stats["LatestDate"],
                        "MissingCount": stats["MissingCount"],
                        "Coverage": stats["Coverage"],
                    }
                )
            status_rows.append(status)
            if status.get("Status") == "LocalUploadLoaded":
                continue

        if auto_download and entry.get("auto_download", False):
            downloaded, status = _fetch_registry_variable(
                entry,
                start_date,
                end_date,
                force_refresh=force_refresh,
            )
            expanded = _merge_variable(
                expanded,
                downloaded,
                variable,
                prefer_existing=prefer_existing and not force_refresh,
            )
            if _series_has_values(expanded, variable):
                stats = _variable_stats(expanded, variable, end_date)
                status.update(
                    {
                        "LatestDate": stats["LatestDate"],
                        "MissingCount": stats["MissingCount"],
                        "Coverage": stats["Coverage"],
                    }
                )
            status_rows.append(status)
        elif not existing:
            status_rows.append(
                {
                    "Variable": variable,
                    "AutoDownload": bool(entry.get("auto_download", False)),
                    "ActualSource": "registry_placeholder",
                    "Status": "RegistryOnly",
                    "IsProxy": bool(entry.get("is_proxy", False)),
                    "SourceFrequency": entry.get("frequency", ""),
                    "DailyAligned": bool(entry.get("daily_alignment", "")),
                    "LatestDate": pd.NaT,
                    "MissingCount": len(expanded),
                    "Coverage": 0.0,
                    "Note": entry.get("note", ""),
                }
            )

    expanded["Date"] = _normalise_date_series(expanded["Date"])
    expanded = expanded.sort_values("Date").drop_duplicates(subset=["Date"], keep="last")
    expanded = expanded.reset_index(drop=True)
    start_timestamp = pd.to_datetime(start_date).normalize()
    end_timestamp = pd.to_datetime(end_date).normalize()
    expanded = expanded[
        (expanded["Date"] >= start_timestamp)
        & (expanded["Date"] <= end_timestamp)
    ].reset_index(drop=True)
    if selected_variables is not None:
        protected_columns = ["Date", "WTI"]
        selected_columns = [
            variable
            for variable in selected_variables
            if variable in expanded.columns and variable not in protected_columns
        ]
        expanded = expanded[[*protected_columns, *selected_columns]].copy()

    effective_end_date: str | pd.Timestamp = end_date
    coverage_df = _build_coverage_report(expanded, registry, end_date)
    coverage_df.to_excel(OUTPUT_PATHS["coverage_report"], index=False)

    if selected_variables is None:
        candidate_vars = [
            column
            for column in expanded.columns
            if column not in {"Date", "Delta_WTI", "LogReturn_WTI"}
        ]
    else:
        candidate_vars = [
            variable
            for variable in selected_variables
            if variable in expanded.columns and variable not in {"Date", "Delta_WTI", "LogReturn_WTI"}
        ]
    kept_by_quality, quality_df = quality_filter_variables(
        expanded,
        candidate_vars,
        end_date=end_date,
        min_coverage=min_coverage,
        max_stale_days=max_stale_days,
    )
    quality_df.to_excel(OUTPUT_PATHS["quality_report"], index=False)

    protected_set = {"WTI"}
    protected_set.update(str(variable) for variable in protected_variables or [] if str(variable).strip())
    retained_after_quality = set(kept_by_quality) | protected_set
    dropped_by_quality = [
        variable
        for variable in candidate_vars
        if variable not in retained_after_quality and variable in expanded.columns
    ]
    if dropped_by_quality:
        expanded = expanded.drop(columns=dropped_by_quality, errors="ignore")

    alignment_variables: list[str] = []
    alignment_report_to_write = pd.DataFrame()
    if selected_variables is not None:
        alignment_variables = [
            variable
            for variable in selected_variables
            if str(variable) != "Date" and variable in expanded.columns
        ]
        expanded, alignment_report, common_start, common_end = _trim_to_common_available_window(
            expanded,
            alignment_variables,
        )
        alignment_report_to_write = alignment_report.copy()
        if common_start is not None and common_end is not None and common_start <= common_end:
            effective_end_date = common_end
        else:
            warnings.warn(
                "Selected variables do not have an overlapping non-missing date window; "
                "expanded variable pool was not trimmed."
            )
    elif OUTPUT_PATHS["date_alignment_report"].exists():
        OUTPUT_PATHS["date_alignment_report"].unlink()

    strict_columns = [column for column in expanded.columns if column != "Date"]
    if strict_columns:
        expanded = expanded.dropna(subset=strict_columns).reset_index(drop=True)

    if selected_variables is not None:
        cleaned_alignment_report, cleaned_common_start, cleaned_common_end = _build_date_alignment_report(
            expanded,
            alignment_variables,
        )
        report_to_write = alignment_report_to_write if not alignment_report_to_write.empty else cleaned_alignment_report
        if not report_to_write.empty:
            report_to_write = report_to_write.copy()
            report_to_write["CleanedCommonStartDate"] = cleaned_common_start
            report_to_write["CleanedCommonEndDate"] = cleaned_common_end
            if "AlignmentNote" in report_to_write.columns:
                report_to_write["AlignmentNote"] = (
                    report_to_write["AlignmentNote"].astype(str)
                    + " Strict complete-case cleaning was applied before the pre-event and event windows were split."
                )
            report_to_write.to_excel(OUTPUT_PATHS["date_alignment_report"], index=False)
        if (
            cleaned_common_start is not None
            and cleaned_common_end is not None
            and cleaned_common_start <= cleaned_common_end
        ):
            effective_end_date = cleaned_common_end

    output_path = _resolve_project_path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    expanded.to_excel(output_path, index=False)

    if merge_to_model_ready:
        model_ready_output = _resolve_project_path(model_ready_path)
        model_ready_output.parent.mkdir(parents=True, exist_ok=True)
        expanded.to_excel(model_ready_output, index=False)

    coverage_lookup = (
        coverage_df.set_index("Variable").to_dict(orient="index")
        if not coverage_df.empty and "Variable" in coverage_df.columns
        else {}
    )
    for row in status_rows:
        variable = str(row.get("Variable", ""))
        stats = coverage_lookup.get(variable)
        if not stats or str(row.get("Status", "")).lower() == "notselected":
            continue
        row.update(
            {
                "LatestDate": stats.get("LatestDate", row.get("LatestDate")),
                "MissingCount": stats.get("MissingCount", row.get("MissingCount")),
                "Coverage": stats.get("Coverage", row.get("Coverage")),
            }
        )

    status_df = pd.DataFrame(status_rows).drop_duplicates(
        subset=["Variable", "Status", "ActualSource"],
        keep="last",
    )
    status_df.to_excel(OUTPUT_PATHS["download_status"], index=False)

    return expanded


def read_variable_pool_outputs() -> dict[str, pd.DataFrame | None]:
    """Read variable-pool output tables when available."""
    outputs: dict[str, pd.DataFrame | None] = {}
    for key, path in OUTPUT_PATHS.items():
        outputs[key] = pd.read_excel(path) if path.exists() else None
    return outputs
