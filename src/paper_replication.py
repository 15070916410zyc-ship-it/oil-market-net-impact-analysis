"""Paper-method multiscale net-impact analysis for selectable target variables.

This module implements a dashboard-oriented workflow based on the paper method:

1. VMD decomposition with configurable K, alpha=1000, tau=0, tol=1e-7.
2. Multiresolution Granger causality with BIC lag selection, max lag = 5.
3. Selected-scale selection from VMD results and MRGC evidence.
4. Selected-scale net effect extraction within the event window.
5. Rolling-window VAR FEVD contribution decomposition with FEVD horizon h
   set by the trading-day interval between selected-scale extrema.
"""

from __future__ import annotations

from functools import reduce
from pathlib import Path
import re
from typing import Any
import warnings

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from src.mrgc_selector import run_mrgc_screening, significance_stars
from src.plot_utils import apply_publication_plot_style, save_figure_pair
from src.vmd_module import estimate_center_frequency, run_vmd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MODEL_READY_PATH = PROJECT_ROOT / "data" / "processed" / "model_ready_data.xlsx"
THESIS_RAW_DATA_DIR = Path.home() / "Desktop" / "\u8bba\u6587" / "\u539f\u59cb\u6570\u636e"
THESIS_VMD_RESULTS_PATH = (
    Path.home()
    / "Desktop"
    / "\u8bba\u6587"
    / "Step01_RawData_VMD_BICGranger_HHT_From20250102"
    / "Data"
    / "Step01_VMD_Results_Raw.mat"
)
TABLES_DIR = PROJECT_ROOT / "outputs" / "tables"
FIGURES_DIR = PROJECT_ROOT / "outputs" / "figures"

OUTPUT_PATHS = {
    "summary": TABLES_DIR / "paper_replication_summary.xlsx",
    "mrgc": TABLES_DIR / "paper_mrgc_results.xlsx",
    "scale_statistics": TABLES_DIR / "paper_scale_statistics.xlsx",
    "selected_scale_effect": TABLES_DIR / "paper_selected_scale_effect.xlsx",
    "h_review": TABLES_DIR / "paper_fevd_h_review.xlsx",
    "selected_scale_granger": TABLES_DIR / "paper_selected_scale_granger.xlsx",
    "tvp_settings": TABLES_DIR / "paper_tvp_var_settings.xlsx",
    "contribution_weights": TABLES_DIR / "paper_external_contribution_weights.xlsx",
    "net_impacts": TABLES_DIR / "paper_net_impacts.xlsx",
    "break_test": TABLES_DIR / "paper_structural_break_test.xlsx",
    "optimal_break_rss": TABLES_DIR / "paper_optimal_break_rss_profile.xlsx",
    "selected_scale_series": TABLES_DIR / "paper_selected_scale_series.xlsx",
    "vmd_center_frequencies": TABLES_DIR / "paper_vmd_center_frequencies.xlsx",
    "dashboard": TABLES_DIR / "paper_replication_dashboard.xlsx",
    "price_event_figure": FIGURES_DIR / "paper_price_event.png",
    "price_event_figure_pdf": FIGURES_DIR / "paper_price_event.pdf",
    "hht_imf1_figure": FIGURES_DIR / "paper_hht_imf1_frequency.png",
    "hht_imf1_figure_pdf": FIGURES_DIR / "paper_hht_imf1_frequency.pdf",
    "scale_figure": FIGURES_DIR / "paper_selected_scale_trend.png",
    "scale_figure_pdf": FIGURES_DIR / "paper_selected_scale_trend.pdf",
    "mrgc_figure": FIGURES_DIR / "paper_mrgc_heatmap.png",
    "mrgc_figure_pdf": FIGURES_DIR / "paper_mrgc_heatmap.pdf",
    "stats_figure": FIGURES_DIR / "paper_scale_statistics.png",
    "stats_figure_pdf": FIGURES_DIR / "paper_scale_statistics.pdf",
    "contribution_figure": FIGURES_DIR / "paper_external_contribution.png",
    "contribution_figure_pdf": FIGURES_DIR / "paper_external_contribution.pdf",
    "net_impact_figure": FIGURES_DIR / "paper_net_impacts.png",
    "net_impact_figure_pdf": FIGURES_DIR / "paper_net_impacts.pdf",
    "break_figure": FIGURES_DIR / "paper_structural_break_fit.png",
    "break_figure_pdf": FIGURES_DIR / "paper_structural_break_fit.pdf",
    "optimal_break_rss_figure": FIGURES_DIR / "paper_optimal_break_rss_profile.png",
    "optimal_break_rss_figure_pdf": FIGURES_DIR / "paper_optimal_break_rss_profile.pdf",
}

DEFAULT_CANDIDATES = ["GPRD", "Gold", "OVX", "DollarIndex", "TNote10Y"]
THESIS_MARKET_FILES = {
    "WTI": "WTI\u539f\u6cb9\u671f\u8d27\u5386\u53f2\u6570\u636e (2).csv",
    "Brent": "\u4f26\u6566\u5e03\u4f26\u7279\u539f\u6cb9\u671f\u8d27\u5386\u53f2\u6570\u636e.csv",
    "Gold": "\u9ec4\u91d1\u671f\u8d27\u5386\u53f2\u6570\u636e.csv",
    "OVX": "CBOE Crude Oil Volatility\u5386\u53f2\u6570\u636e.csv",
    "DollarIndex": "\u7f8e\u5143\u6307\u6570\u5386\u53f2\u6570\u636e.csv",
    "TNote10Y": "\u7f8e\u56fd10\u5e74\u671fT-Note\u671f\u8d27\u5386\u53f2\u6570\u636e.csv",
}
WAR_RELATED_VARIABLES = {"GPRD", "Gold", "OVX"}
VMD_LEVELS = ["IMF1", "IMF2", "IMF3", "IMF4"]
MAIN_SCALE_CANDIDATES = VMD_LEVELS
FALLBACK_DRIVER_MAP = {
    "WTI": ["GPRD", "Gold", "OVX", "TNote10Y"],
    "Brent": ["GPRD", "Gold", "OVX", "DollarIndex", "TNote10Y"],
}
PAPER_ROLLING_WINDOW = 120
SELECTED_SCALE_SCORE_RATIO = 0.50
LEVEL_INTERPRETATION = {
    "IMF1": "High-frequency disturbance",
    "IMF2": "Short-run adjustment",
    "IMF3": "Medium-run adjustment",
    "IMF4": "Low-frequency trend layer",
}
_THESIS_VMD_ACTIVE = False
_THESIS_VMD_CACHE: dict[str, np.ndarray] | None = None

def _resolve_project_path(path: str | Path) -> Path:
    """Resolve a relative path against the project root."""
    path = Path(path)
    if path.is_absolute():
        return path
    return PROJECT_ROOT / path


def _ensure_dirs() -> None:
    """Create output directories."""
    TABLES_DIR.mkdir(parents=True, exist_ok=True)
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)


def _load_thesis_vmd_results() -> dict[str, np.ndarray]:
    """Load MATLAB Step01 VMD matrices for exact thesis-sample replication."""
    global _THESIS_VMD_CACHE
    if _THESIS_VMD_CACHE is not None:
        return _THESIS_VMD_CACHE
    if not THESIS_VMD_RESULTS_PATH.exists():
        _THESIS_VMD_CACHE = {}
        return _THESIS_VMD_CACHE
    try:
        from scipy.io import loadmat

        mat = loadmat(str(THESIS_VMD_RESULTS_PATH), squeeze_me=True, struct_as_record=False)
        vmd_results = mat.get("vmdResults")
        if vmd_results is None or not hasattr(vmd_results, "_fieldnames"):
            _THESIS_VMD_CACHE = {}
            return _THESIS_VMD_CACHE
        cache: dict[str, np.ndarray] = {}
        for field in vmd_results._fieldnames:
            values = np.asarray(getattr(vmd_results, field), dtype=float)
            if values.ndim == 2 and values.shape[1] >= 4:
                cache[str(field)] = values[:, :4]
        _THESIS_VMD_CACHE = cache
    except Exception as exc:  # noqa: BLE001
        warnings.warn(f"Could not load MATLAB Step01 VMD results: {exc}")
        _THESIS_VMD_CACHE = {}
    return _THESIS_VMD_CACHE


def _maybe_enable_thesis_vmd(data: pd.DataFrame) -> None:
    """Enable MATLAB VMD cache only for the exact thesis sample length and dates."""
    global _THESIS_VMD_ACTIVE
    _THESIS_VMD_ACTIVE = False
    cache = _load_thesis_vmd_results()
    wti_imfs = cache.get("WTI")
    if wti_imfs is None:
        return
    min_date = pd.to_datetime(data["Date"]).min()
    max_date = pd.to_datetime(data["Date"]).max()
    _THESIS_VMD_ACTIVE = (
        len(data) == wti_imfs.shape[0]
        and min_date == pd.Timestamp("2025-01-02")
        and max_date == pd.Timestamp("2026-04-30")
    )


def _vmd_source_note() -> str:
    """Return the VMD source used by the current paper-replication run."""
    if _THESIS_VMD_ACTIVE:
        return "MATLAB Step01 cached VMD results for exact thesis-sample replication."
    return "Python vmdpy recomputed for the selected sample."


def _imf_levels(vmd_k: int = 4) -> list[str]:
    """Return IMF labels for the selected VMD K."""
    vmd_k = max(1, int(vmd_k))
    return [f"IMF{idx}" for idx in range(1, vmd_k + 1)]


def _level_interpretation(level: str, vmd_k: int = 4) -> str:
    """Return a readable interpretation for an IMF level."""
    if level in LEVEL_INTERPRETATION and int(vmd_k) == 4:
        return LEVEL_INTERPRETATION[level]
    match = re.search(r"(\d+)$", str(level))
    if not match:
        return "VMD component"
    index = int(match.group(1))
    if index == 1:
        return "Highest-frequency VMD component"
    if index == int(vmd_k):
        return "Lowest-frequency VMD component"
    return "Intermediate-frequency VMD component"


def _scale_rule_text(vmd_k: int = 4) -> str:
    """Return method text for dynamic main-scale selection."""
    levels = _imf_levels(vmd_k)
    return (
        f"Dynamic paper-style selection from {levels[0]}-{levels[-1]} using "
        "MRGC/GPRD significance, event-window range share, variance contribution, "
        "and correlation; one or multiple IMFs may be retained"
    )


def _format_date(value: Any) -> str:
    """Format a date-like value as yyyy-mm-dd."""
    ts = pd.to_datetime(value, errors="coerce")
    return "" if pd.isna(ts) else ts.strftime("%Y-%m-%d")


def _read_thesis_market_csv(variable: str) -> pd.DataFrame:
    """Read one thesis Investing-style CSV and keep the Date/close columns."""
    file_name = THESIS_MARKET_FILES[variable]
    path = THESIS_RAW_DATA_DIR / file_name
    if not path.exists():
        raise FileNotFoundError(path)

    data = pd.read_csv(path, encoding="utf-8-sig")
    if data.shape[1] < 2:
        raise ValueError(f"Thesis CSV does not contain enough columns: {path}")

    output = pd.DataFrame(
        {
            "Date": pd.to_datetime(data.iloc[:, 0], errors="coerce"),
            variable: pd.to_numeric(
                data.iloc[:, 1].astype(str).str.replace(",", "", regex=False),
                errors="coerce",
            ),
        }
    )
    return output.dropna(subset=["Date"]).drop_duplicates(subset=["Date"], keep="last")


def _read_thesis_gprd() -> pd.DataFrame:
    """Read the traditional daily GPRD file used by the thesis MATLAB code."""
    path = THESIS_RAW_DATA_DIR / "data_gpr_daily_recent.xls"
    if not path.exists():
        raise FileNotFoundError(path)

    data = pd.read_excel(path)
    if "date" in data.columns:
        dates = pd.to_datetime(data["date"], errors="coerce")
    elif "DAY" in data.columns:
        dates = pd.to_datetime(
            pd.to_numeric(data["DAY"], errors="coerce").astype("Int64").astype(str),
            format="%Y%m%d",
            errors="coerce",
        )
    else:
        raise ValueError("Thesis GPRD file must contain date or DAY.")

    output = pd.DataFrame(
        {
            "Date": dates,
            "GPRD": pd.to_numeric(data["GPRD"], errors="coerce"),
        }
    )
    return output.dropna(subset=["Date"]).drop_duplicates(subset=["Date"], keep="last")


def load_thesis_source_data(
    start_date: str | None = None,
    end_date: str | None = None,
) -> pd.DataFrame | None:
    """Load the thesis raw close-price data when the local thesis folder is available."""
    if not THESIS_RAW_DATA_DIR.exists():
        return None

    frames: list[pd.DataFrame] = []
    for variable in THESIS_MARKET_FILES:
        try:
            frames.append(_read_thesis_market_csv(variable))
        except Exception:
            if variable == "WTI":
                return None
    try:
        frames.append(_read_thesis_gprd())
    except Exception:
        return None

    data = reduce(lambda left, right: pd.merge(left, right, on="Date", how="outer"), frames)
    data["Date"] = pd.to_datetime(data["Date"], errors="coerce")
    data = data.dropna(subset=["Date"]).drop_duplicates(subset=["Date"], keep="last")
    data = data.sort_values("Date").reset_index(drop=True)

    if start_date:
        data = data.loc[data["Date"] >= pd.to_datetime(start_date)]
    if end_date:
        data = data.loc[data["Date"] <= pd.to_datetime(end_date)]
    data = data.reset_index(drop=True)
    if data.empty:
        return None
    return data


def load_paper_replication_data(
    input_path: str | Path = MODEL_READY_PATH,
    start_date: str | None = None,
    end_date: str | None = None,
    allow_thesis_source: bool = False,
) -> pd.DataFrame:
    """Load model-ready data for the selected net-impact period."""
    path = _resolve_project_path(input_path)
    thesis_data = None
    if path.exists():
        data = pd.read_excel(path)
        source_note = str(path)
    elif allow_thesis_source:
        thesis_data = load_thesis_source_data(start_date=start_date, end_date=end_date)
        if thesis_data is not None and "WTI" in thesis_data.columns:
            data = thesis_data
            source_note = "local thesis raw close-price files"
        else:
            raise FileNotFoundError(f"Model-ready data not found and thesis raw data is unavailable: {path}")
    else:
        raise FileNotFoundError(
            f"Model-ready data not found: {path}. Run market data update and Prepare Model Data first."
        )

    if "Date" not in data.columns:
        if not allow_thesis_source:
            raise ValueError("Net-impact data must contain a Date column.")
        thesis_data = thesis_data if thesis_data is not None else load_thesis_source_data(start_date=start_date, end_date=end_date)
        if thesis_data is None or "WTI" not in thesis_data.columns:
            raise ValueError("Net-impact data must contain Date and WTI columns.")
        data = thesis_data
        source_note = "local thesis raw close-price files fallback"
    data = data.copy()
    data["Date"] = pd.to_datetime(data["Date"], errors="coerce")
    required_subset = ["Date"] + (["WTI"] if "WTI" in data.columns else [])
    data = data.dropna(subset=required_subset)
    data = data.drop_duplicates(subset=["Date"], keep="last")
    data = data.sort_values("Date").reset_index(drop=True)

    if start_date:
        data = data.loc[data["Date"] >= pd.to_datetime(start_date)]
    if end_date:
        data = data.loc[data["Date"] <= pd.to_datetime(end_date)]
    data = data.reset_index(drop=True)
    if len(data) < 40:
        raise ValueError("The selected period is too short for paper-method replication.")

    for column in data.columns:
        if column != "Date":
            data[column] = pd.to_numeric(data[column], errors="coerce")
    data.attrs["source_note"] = source_note
    if len(data) < 40:
        raise ValueError("The complete-case paper-method sample is too short.")
    return data


def _vmd_frame(series: pd.Series, prefix: str, vmd_k: int = 4) -> pd.DataFrame:
    """Return Date-free VMD columns for one numeric series."""
    vmd_k = max(1, int(vmd_k))
    values = pd.to_numeric(series, errors="coerce").to_numpy(dtype=float)
    if np.isnan(values).any():
        raise ValueError(f"{prefix} contains NaN values after alignment.")
    if _THESIS_VMD_ACTIVE and vmd_k == 4:
        thesis_imfs = _load_thesis_vmd_results().get(prefix)
        if thesis_imfs is not None and thesis_imfs.shape[0] == len(values):
            return pd.DataFrame(thesis_imfs[:, :4], columns=[f"{prefix}_IMF{i}" for i in range(1, 5)])
    # MATLAB's vmd output in the thesis labels IMF1 as the highest-frequency
    # component and higher IMF numbers as lower-frequency components. vmdpy with init=0 returns
    # the same decomposition in the opposite column order, so this is a
    # library-compatibility label mapping, not a frequency-based reselection.
    imfs = run_vmd(values, K=vmd_k, alpha=1000, tau=0, DC=0, init=0, tol=1e-7)[:, ::-1]
    return pd.DataFrame(imfs, columns=[f"{prefix}_IMF{i}" for i in range(1, vmd_k + 1)])


def build_vmd_center_frequency_review(
    start_date: str | None = None,
    end_date: str | None = None,
    input_path: str | Path = MODEL_READY_PATH,
    variables: list[str] | None = None,
    vmd_k: int = 4,
    output_path: str | Path = OUTPUT_PATHS["vmd_center_frequencies"],
) -> pd.DataFrame:
    """Build a VMD center-frequency review table for selected variables."""
    vmd_k = max(1, int(vmd_k))
    data = load_paper_replication_data(
        input_path=input_path,
        start_date=start_date,
        end_date=end_date,
        allow_thesis_source=False,
    )
    requested = [
        str(variable)
        for variable in (variables or _numeric_variable_columns(data))
        if str(variable) in data.columns
    ]
    requested = list(dict.fromkeys(requested))
    rows: list[dict[str, Any]] = []
    for variable in requested:
        series_df = data[["Date", variable]].copy()
        series_df[variable] = pd.to_numeric(series_df[variable], errors="coerce")
        series_df = series_df.dropna(subset=["Date", variable]).reset_index(drop=True)
        if len(series_df) <= vmd_k + 5 or series_df[variable].std() <= 1e-12:
            rows.append(
                {
                    "Variable": variable,
                    "IMF": "",
                    "VMD_K": vmd_k,
                    "CenterFrequencyCyclesPerObservation": np.nan,
                    "CenterPeriodObservations": np.nan,
                    "Observations": len(series_df),
                    "SampleStartDate": series_df["Date"].min() if not series_df.empty else pd.NaT,
                    "SampleEndDate": series_df["Date"].max() if not series_df.empty else pd.NaT,
                    "Status": "Skipped",
                    "Note": "Too few observations or near-zero variance for VMD.",
                }
            )
            continue
        try:
            imfs = _vmd_frame(series_df[variable], variable, vmd_k=vmd_k)
            for index, column in enumerate(imfs.columns, start=1):
                level = f"IMF{index}"
                frequency, period = estimate_center_frequency(imfs[column])
                rows.append(
                    {
                        "Variable": variable,
                        "IMF": level,
                        "VMD_K": vmd_k,
                        "CenterFrequencyCyclesPerObservation": frequency,
                        "CenterPeriodObservations": period,
                        "Observations": len(series_df),
                        "SampleStartDate": series_df["Date"].min(),
                        "SampleEndDate": series_df["Date"].max(),
                        "Status": "OK",
                        "Note": _level_interpretation(level, vmd_k),
                    }
                )
        except Exception as exc:  # noqa: BLE001 - show review failures per variable.
            rows.append(
                {
                    "Variable": variable,
                    "IMF": "",
                    "VMD_K": vmd_k,
                    "CenterFrequencyCyclesPerObservation": np.nan,
                    "CenterPeriodObservations": np.nan,
                    "Observations": len(series_df),
                    "SampleStartDate": series_df["Date"].min() if not series_df.empty else pd.NaT,
                    "SampleEndDate": series_df["Date"].max() if not series_df.empty else pd.NaT,
                    "Status": "Failed",
                    "Note": str(exc),
                }
            )
    result = pd.DataFrame(rows)
    output_path = _resolve_project_path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    result.round(6).to_excel(output_path, index=False)
    return result


def _average_period(values: pd.Series | np.ndarray) -> float:
    """Compute the paper-style HHT mean period used by the MATLAB scripts."""
    array = np.asarray(values, dtype=float)
    if len(array) < 3 or np.nanstd(array) <= 1e-12:
        return np.nan
    try:
        from scipy.signal import hilbert

        analytic = hilbert(array)
    except Exception:  # noqa: BLE001 - deterministic FFT fallback mirrors MATLAB fallback.
        spectrum = np.fft.fft(array)
        n_obs = len(array)
        multiplier = np.zeros(n_obs)
        if n_obs % 2 == 0:
            multiplier[0] = 1
            multiplier[n_obs // 2] = 1
            multiplier[1 : n_obs // 2] = 2
        else:
            multiplier[0] = 1
            multiplier[1 : (n_obs + 1) // 2] = 2
        analytic = np.fft.ifft(spectrum * multiplier)
    phase = np.unwrap(np.angle(analytic))
    freq = np.abs(np.diff(phase)) / (2 * np.pi)
    freq = freq[np.isfinite(freq) & (freq > np.finfo(float).eps)]
    if len(freq) == 0:
        return np.nan
    return float(1 / np.mean(freq))


def _target_scale_statistics(
    data: pd.DataFrame,
    target: str,
    screening: pd.DataFrame,
    event_start_date: str | pd.Timestamp | None,
    vmd_k: int = 4,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Compute IMF statistics and choose paper-style selected-scale IMFs."""
    levels = _imf_levels(vmd_k)
    target_values = pd.to_numeric(data[target], errors="coerce")
    target_imfs = _vmd_frame(target_values, target, vmd_k=vmd_k)
    result = data[["Date", target]].copy()
    result = pd.concat([result, target_imfs], axis=1)

    imf_columns = [f"{target}_IMF{i}" for i in range(1, vmd_k + 1)]
    variances = np.array([np.nanvar(result[column].to_numpy(dtype=float), ddof=1) for column in imf_columns])
    variance_sum = float(np.nansum(variances)) or np.nan

    event_start = pd.to_datetime(event_start_date) if event_start_date is not None else result["Date"].min()
    event_part = result.loc[result["Date"] >= event_start].copy()
    event_ranges = []
    for idx in range(1, vmd_k + 1):
        column = f"{target}_IMF{idx}"
        values = pd.to_numeric(event_part[column], errors="coerce").dropna()
        if values.empty:
            event_ranges.append(np.nan)
        else:
            event_ranges.append(float(values.max() - values.min()))
    total_event_range = float(np.nansum(event_ranges)) or np.nan

    rows: list[dict[str, Any]] = []
    for idx, level in enumerate(levels, start=1):
        column = f"{target}_{level}"
        gprd_rows = screening.loc[
            (screening["Target"].astype(str) == target)
            & (screening["CandidateVariable"].astype(str) == "GPRD")
            & (screening["Level"].astype(str) == level)
        ]
        gprd_significant = bool(gprd_rows["Retained"].fillna(False).any()) if not gprd_rows.empty else False
        corr = result[[target, column]].corr().iloc[0, 1]
        contribution = variances[idx - 1] / variance_sum * 100 if np.isfinite(variance_sum) else np.nan
        event_values = pd.to_numeric(event_part[column], errors="coerce").dropna()
        event_min = float(event_values.min()) if not event_values.empty else np.nan
        event_max = float(event_values.max()) if not event_values.empty else np.nan
        event_range = event_ranges[idx - 1]
        event_range_share = (
            event_range / total_event_range * 100
            if np.isfinite(event_range) and np.isfinite(total_event_range) and total_event_range > 0
            else np.nan
        )
        rows.append(
            {
                "Target": target,
                "IMF": level,
                "VMD_K": vmd_k,
                "MeanPeriod": _average_period(result[column]),
                "CorrelationWithOriginal": corr,
                "VarianceContributionPercent": contribution,
                "EventMinimum": event_min,
                "EventMaximum": event_max,
                "EventRange": event_range,
                "EventRangeShare": event_range_share,
                "EconomicInterpretation": _level_interpretation(level, vmd_k),
                "GPRDSignificant": gprd_significant,
                "IncludedInModel": False,
                "SelectionReason": "",
            }
        )

    stats = pd.DataFrame(rows)
    stats["SelectionScore"] = (
        pd.to_numeric(stats["VarianceContributionPercent"], errors="coerce").fillna(0)
        + pd.to_numeric(stats["CorrelationWithOriginal"], errors="coerce").abs().fillna(0) * 100
        + pd.to_numeric(stats["EventRangeShare"], errors="coerce").fillna(0)
        + stats["GPRDSignificant"].astype(float) * 50
    )

    main_stats = stats.loc[stats["IMF"].isin(levels)].copy()
    significant_stats = main_stats.loc[main_stats["GPRDSignificant"]].copy()
    selection_pool = significant_stats if not significant_stats.empty else main_stats
    strongest = selection_pool.sort_values("SelectionScore", ascending=False).head(1)
    top_score = float(strongest["SelectionScore"].iloc[0]) if not strongest.empty else np.nan
    if np.isfinite(top_score) and top_score > 0:
        retained = selection_pool.loc[
            pd.to_numeric(selection_pool["SelectionScore"], errors="coerce")
            >= top_score * SELECTED_SCALE_SCORE_RATIO
        ].copy()
    else:
        retained = strongest.copy()
    if retained.empty:
        retained = strongest.copy()
    reason = (
        f"Selected by paper-style dominant-scale criteria across {levels[0]}-{levels[-1]}: the "
        "dominant event-response IMF is selected using MRGC/GPRD evidence where "
        "available, event-window range share, variance contribution, and "
        "correlation with the original oil-price series. Additional IMFs are "
        "retained only when their composite score reaches the unified retention threshold; "
        "therefore the selected scale may contain one or multiple IMFs."
    )

    selected_levels = [level for level in levels if level in set(retained["IMF"].astype(str))]

    stats.loc[stats["IMF"].isin(selected_levels), "IncludedInModel"] = True
    stats.loc[stats["IMF"].isin(selected_levels), "SelectionReason"] = reason
    selected_columns = [f"{target}_{level}" for level in selected_levels]
    result[f"{target}_SelectedScale"] = result[selected_columns].sum(axis=1)
    result["SelectedScale"] = "+".join(selected_levels)
    return stats, result


def _run_mrgc_for_target(
    data: pd.DataFrame,
    target: str,
    candidate_variables: list[str],
    vmd_k: int = 4,
) -> tuple[pd.DataFrame, list[str]]:
    """Run paper-style MRGC for one target."""
    return run_mrgc_screening(
        data=data[["Date", target] + candidate_variables].dropna(subset=[target]),
        target_col=target,
        candidate_variables=candidate_variables,
        max_lag=5,
        lag_selection="bic",
        K=vmd_k,
        p_threshold=0.10,
        target_label=target,
        save_outputs=False,
    )


def _selected_scale_extreme_effect(
    scale_df: pd.DataFrame,
    target: str,
    event_start_date: str | pd.Timestamp | None,
) -> dict[str, Any]:
    """Compute event-window selected-scale extremes and FEVD horizon h."""
    column = f"{target}_SelectedScale"
    ordered = scale_df[["Date", target, column]].dropna().sort_values("Date").reset_index(drop=True)
    event_start = pd.to_datetime(event_start_date) if event_start_date is not None else ordered["Date"].min()
    event_df = ordered.loc[ordered["Date"] >= event_start].reset_index(drop=True)
    if len(event_df) < 5:
        raise ValueError("Event-window selected-scale observations are insufficient.")

    min_idx = int(event_df[column].idxmin())
    max_idx = int(event_df[column].idxmax())
    min_row = event_df.loc[min_idx]
    max_row = event_df.loc[max_idx]
    target_min_idx = int(event_df[target].idxmin())
    target_max_idx = int(event_df[target].idxmax())
    target_min_row = event_df.loc[target_min_idx]
    target_max_row = event_df.loc[target_max_idx]

    calendar_days = abs((pd.to_datetime(max_row["Date"]) - pd.to_datetime(min_row["Date"])).days)
    trading_days = abs(max_idx - min_idx)
    if trading_days < 1:
        raise ValueError(
            f"{target} selected-scale trading-day interval is less than 1. "
            "Please check selected-scale extrema."
        )
    h = int(trading_days)
    net_effect = float(max_row[column] - min_row[column])
    target_response = float(target_max_row[target] - target_min_row[target])
    share = net_effect / target_response * 100 if abs(target_response) > 1e-12 else np.nan
    return {
        "Target": target,
        "SelectedScale": str(scale_df["SelectedScale"].iloc[0]),
        "EventStartDate": event_start,
        "OriginalMinDate": target_min_row["Date"],
        "OriginalMinValue": float(target_min_row[target]),
        "OriginalMaxDate": target_max_row["Date"],
        "OriginalMaxValue": float(target_max_row[target]),
        "OriginalTotalResponse": target_response,
        "MinimumDate": min_row["Date"],
        "MinimumValue": float(min_row[column]),
        "MaximumDate": max_row["Date"],
        "MaximumValue": float(max_row[column]),
        "TradingDayInterval": int(trading_days),
        "CalendarDayInterval": int(calendar_days),
        "FEVD_h": h,
        "NEI_M": net_effect,
        "NetEffect": net_effect,
        "ShareInOriginalResponse": share,
        "Note": (
            "FEVD horizon h is the trading-day interval between the selected main "
            "mode extrema; the calendar-day interval is reported only as a reference."
        ),
    }


def _level_sum_from_imfs(
    data: pd.DataFrame,
    variable: str,
    selected_levels: list[str],
    vmd_k: int = 4,
) -> pd.Series:
    """Return the sum of selected IMF levels for one variable."""
    imfs = _vmd_frame(data[variable], variable, vmd_k=vmd_k)
    selected_columns = [f"{variable}_{level}" for level in selected_levels]
    return imfs[selected_columns].sum(axis=1)


def _selected_scale_granger(
    data: pd.DataFrame,
    target: str,
    selected_levels: list[str],
    candidate_variables: list[str],
    p_threshold: float = 0.10,
    vmd_k: int = 4,
) -> tuple[pd.DataFrame, list[str]]:
    """Run MATLAB Step01-style Granger tests on the selected scale."""
    from src.mrgc_selector import granger_test_bic

    aligned = data[["Date", target] + candidate_variables].dropna().sort_values("Date").reset_index(drop=True)
    y = _level_sum_from_imfs(aligned, target, selected_levels, vmd_k=vmd_k)
    rows = []
    included = []
    scale_name = "+".join(selected_levels)
    for candidate in candidate_variables:
        x = _level_sum_from_imfs(aligned, candidate, selected_levels, vmd_k=vmd_k)
        result = granger_test_bic(y, x, max_lag=5)
        p_value = float(result["PValue"]) if pd.notna(result["PValue"]) else np.nan
        stars = significance_stars(p_value)
        is_included = bool(np.isfinite(p_value) and p_value < p_threshold)
        if is_included:
            included.append(candidate)
        rows.append(
            {
                "Target": target,
                "Cause": candidate,
                "SelectedScale": scale_name,
                "Lag": result["SelectedLagByBIC"],
                "FStat": result["FStatistic"],
                "FStatisticWithStars": (
                    f"{result['FStatistic']:.3f}{stars}"
                    if pd.notna(result["FStatistic"])
                    else ""
                ),
                "PValue": p_value,
                "Significance": stars,
                "IncludedInContributionModel": "Yes" if is_included else "No",
                "LagCriterion": "BIC",
                "MaxLag": 5,
            }
        )
    return pd.DataFrame(rows), included


def _var_design(values: np.ndarray, lag: int) -> tuple[np.ndarray, np.ndarray]:
    """Build multivariate VAR design matrices."""
    rows_y = []
    rows_x = []
    for idx in range(lag, len(values)):
        rows_y.append(values[idx])
        lagged = [values[idx - step] for step in range(1, lag + 1)]
        rows_x.append(np.concatenate([[1.0], np.concatenate(lagged)]))
    return np.asarray(rows_y, dtype=float), np.asarray(rows_x, dtype=float)


def _fit_var(values: np.ndarray, lag: int) -> tuple[list[np.ndarray], np.ndarray, float]:
    """Fit VAR(p) with OLS and return coefficient matrices, covariance, and BIC."""
    y, x = _var_design(values, lag)
    if len(y) <= x.shape[1] + 2:
        raise ValueError("Too few observations for VAR lag selection.")
    beta, *_ = np.linalg.lstsq(x, y, rcond=None)
    residuals = y - x @ beta
    sigma = residuals.T @ residuals / max(len(residuals) - x.shape[1], 1)
    sign, logdet = np.linalg.slogdet(sigma + np.eye(sigma.shape[0]) * 1e-10)
    if sign <= 0:
        logdet = np.log(np.maximum(np.linalg.det(sigma + np.eye(sigma.shape[0]) * 1e-8), 1e-12))
    n_obs, n_vars = y.shape
    param_count = n_vars * n_vars * lag + n_vars
    bic = float(logdet + np.log(n_obs) * param_count / n_obs)
    matrices = []
    coef_no_const = beta[1:, :].T
    for step in range(lag):
        matrices.append(coef_no_const[:, step * n_vars : (step + 1) * n_vars])
    return matrices, sigma, bic


def _select_var_lag(values: np.ndarray, max_lag: int = 5) -> tuple[int, list[np.ndarray], np.ndarray, pd.DataFrame]:
    """Select VAR lag by BIC in 1..max_lag."""
    rows = []
    best: tuple[int, list[np.ndarray], np.ndarray, float] | None = None
    for lag in range(1, max_lag + 1):
        try:
            matrices, sigma, bic = _fit_var(values, lag)
            rows.append({"Lag": lag, "BIC": bic, "Status": "OK"})
            if best is None or bic < best[3]:
                best = (lag, matrices, sigma, bic)
        except Exception as exc:  # noqa: BLE001 - try smaller/larger feasible lags.
            rows.append({"Lag": lag, "BIC": np.nan, "Status": f"Failed: {exc}"})
    if best is None:
        raise ValueError("No feasible VAR lag was available for contribution decomposition.")
    return best[0], best[1], best[2], pd.DataFrame(rows)


def _ma_matrices(var_matrices: list[np.ndarray], horizon: int) -> list[np.ndarray]:
    """Compute VAR moving-average coefficient matrices."""
    n_vars = var_matrices[0].shape[0]
    phi = [np.eye(n_vars)]
    for step in range(1, horizon):
        current = np.zeros((n_vars, n_vars))
        for lag_idx, matrix in enumerate(var_matrices, start=1):
            if step - lag_idx >= 0:
                current += matrix @ phi[step - lag_idx]
        phi.append(current)
    return phi


def _safe_cholesky(sigma: np.ndarray) -> np.ndarray:
    """Return a numerically safe lower Cholesky factor, matching the MATLAB fallback."""
    sigma = (sigma + sigma.T) / 2
    jitter = 1e-10
    for _ in range(8):
        try:
            return np.linalg.cholesky(sigma + np.eye(sigma.shape[0]) * jitter)
        except np.linalg.LinAlgError:
            jitter *= 10
    values, vectors = np.linalg.eigh(sigma)
    values = np.clip(values, 1e-10, None)
    repaired = vectors @ np.diag(values) @ vectors.T
    return np.linalg.cholesky((repaired + repaired.T) / 2)


def _cholesky_fevd_share(
    var_matrices: list[np.ndarray],
    sigma: np.ndarray,
    horizon: int,
    target_index: int = 0,
) -> np.ndarray:
    """Compute MATLAB-style orthogonal FEVD shares for one target row."""
    if horizon < 1:
        raise ValueError("FEVD horizon must be at least 1.")
    p_factor = _safe_cholesky(sigma)
    phi = _ma_matrices(var_matrices, horizon)
    numerator = np.zeros(sigma.shape[0], dtype=float)
    for matrix in phi:
        response = matrix @ p_factor
        numerator += response[target_index, :] ** 2
    denominator = float(np.sum(numerator))
    if denominator <= 0 or not np.isfinite(denominator):
        return np.repeat(np.nan, sigma.shape[0])
    return numerator / denominator


def _rolling_var_fevd(
    dates: pd.Series,
    values: np.ndarray,
    lag: int,
    rolling_window: int,
    horizon: int,
    event_start: pd.Timestamp,
    event_end: pd.Timestamp,
) -> tuple[pd.Series, np.ndarray]:
    """Run MATLAB-style rolling VAR FEVD over the event window."""
    ordered_dates = pd.to_datetime(dates).reset_index(drop=True)
    values = np.asarray(values, dtype=float)
    event_positions = np.where((ordered_dates >= event_start) & (ordered_dates <= event_end))[0]
    out_dates: list[pd.Timestamp] = []
    out_shares: list[np.ndarray] = []
    n_vars = values.shape[1]
    for position in event_positions:
        window_start = position - rolling_window + 1
        if window_start < 0:
            continue
        window = values[window_start : position + 1, :]
        good = np.isfinite(window).all(axis=1)
        window = window[good, :]
        if window.shape[0] <= lag + n_vars + 5:
            continue
        try:
            matrices, sigma, _ = _fit_var(window, lag)
            shares = _cholesky_fevd_share(matrices, sigma, horizon, target_index=0)
        except Exception as exc:  # noqa: BLE001
            warnings.warn(f"Rolling FEVD skipped at {ordered_dates.iloc[position].date()}: {exc}")
            continue
        if np.isfinite(shares).all():
            out_dates.append(ordered_dates.iloc[position])
            out_shares.append(shares)
    if not out_dates:
        raise ValueError("No rolling FEVD results were produced. Check rolling window, lag order, and data availability.")
    return pd.Series(out_dates), np.vstack(out_shares)


def _build_selected_scale_var_data(
    data: pd.DataFrame,
    target: str,
    selected_levels: list[str],
    drivers: list[str],
    vmd_k: int = 4,
) -> pd.DataFrame:
    """Build selected-scale target and driver series for VAR FEVD."""
    required = ["Date", target] + drivers
    aligned = data[required].dropna().sort_values("Date").reset_index(drop=True)
    if len(aligned) < 40:
        raise ValueError("Too few aligned rows for selected-scale VAR contribution decomposition.")

    result = aligned[["Date"]].copy()
    for variable in [target] + drivers:
        result[variable] = _level_sum_from_imfs(aligned, variable, selected_levels, vmd_k=vmd_k)
    return result


def _contribution_decomposition(
    data: pd.DataFrame,
    target: str,
    effect: dict[str, Any],
    selected_scale_drivers: list[str] | None = None,
    candidate_variables: list[str] | None = None,
    vmd_k: int = 4,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Estimate selected-scale VAR FEVD and contribution tables."""
    selected_levels = str(effect["SelectedScale"]).split("+")
    drivers = [driver for driver in (selected_scale_drivers or []) if driver in data.columns]
    driver_selection_rule = "Selected by selected-scale MRGC/BIC Granger test at p < 0.10."
    if not drivers:
        fallback_pool = FALLBACK_DRIVER_MAP.get(target, candidate_variables or [])
        drivers = [
            driver
            for driver in fallback_pool
            if driver in data.columns and driver != target
        ]
        driver_selection_rule = "Fallback to the selected candidate pool because selected-scale MRGC retained no drivers."
        warnings.warn("No selected-scale Granger drivers were retained; falling back to default driver map.")
    if not drivers:
        drivers = [
            candidate
            for candidate in _numeric_variable_columns(data)
            if candidate != target
        ][:3]
        driver_selection_rule = "Fallback to the first available numeric candidate variables because MRGC and selected candidate pool were empty."
        warnings.warn("No paper driver map variables were available; using available default drivers.")

    var_data = _build_selected_scale_var_data(data, target, selected_levels, drivers, vmd_k=vmd_k)
    columns = [target] + drivers
    values = var_data[columns].to_numpy(dtype=float)
    finite_values = values[np.isfinite(values).all(axis=1)]
    lag, _, _, _ = _select_var_lag(finite_values, max_lag=5)
    lag_selection_rule = "Selected by BIC within lags 1 to 5 for the current sample."

    h = int(effect["FEVD_h"])
    event_start = pd.to_datetime(effect["EventStartDate"])
    maximum_date = pd.to_datetime(effect["MaximumDate"])
    fevd_dates, fevd_shares = _rolling_var_fevd(
        dates=var_data["Date"],
        values=values,
        lag=lag,
        rolling_window=PAPER_ROLLING_WINDOW,
        horizon=h,
        event_start=event_start,
        event_end=maximum_date,
    )

    daily_external_rows = []
    for date_value, shares in zip(fevd_dates, fevd_shares):
        external_shares = shares[1:]
        external_total = float(np.nansum(external_shares))
        if np.isfinite(external_total) and external_total > 0:
            external_relative = external_shares / external_total * 100
        else:
            external_relative = np.repeat(np.nan, len(drivers))
        for variable, weight in zip(drivers, external_relative):
            daily_external_rows.append(
                {
                    "Date": date_value,
                    "ExternalVariable": variable,
                    "ExternalRelativeWeightPercent": float(weight),
                }
            )
    daily_external = pd.DataFrame(daily_external_rows)
    minimum_date = pd.to_datetime(effect["MinimumDate"])
    one_day = daily_external.loc[pd.to_datetime(daily_external["Date"]) == maximum_date].copy()
    if one_day.empty:
        raise ValueError(
            f"No one-day contribution data found for {target} on {maximum_date:%Y-%m-%d}."
        )

    net_effect = float(effect["NetEffect"])
    rows = []
    for variable in drivers:
        variable_values = one_day.loc[
            one_day["ExternalVariable"] == variable,
            "ExternalRelativeWeightPercent",
        ]
        weight = float(variable_values.iloc[0]) if not variable_values.empty else np.nan
        rows.append(
            {
                "Target": target,
                "SelectedScale": effect["SelectedScale"],
                "Date": maximum_date,
                "ExternalVariable": variable,
                "ExternalRelativeWeight": weight,
                "ExternalRelativeWeightPercent": weight,
                "NetContribution": float(net_effect * weight / 100),
                "OneDayNetContribution": float(net_effect * weight / 100),
                "VARLag": lag,
                "LagOrder": lag,
                "LagCriterion": "BIC",
                "LagSelectionRule": lag_selection_rule,
                "VMDSource": _vmd_source_note(),
                "VMD_K": vmd_k,
                "FEVD_h": h,
                "RollingWindow": PAPER_ROLLING_WINDOW,
                "MinimumDate": minimum_date,
                "MaximumDate": maximum_date,
                "DriverSelectionRule": driver_selection_rule,
                "Note": "External weights are taken from the selected-scale maximum date only, not averaged over the interval.",
            }
        )
    contribution = pd.DataFrame(rows)

    gprd_weight = contribution.loc[contribution["ExternalVariable"] == "GPRD", "ExternalRelativeWeight"].sum()
    broad_weight = contribution.loc[
        contribution["ExternalVariable"].isin(WAR_RELATED_VARIABLES), "ExternalRelativeWeight"
    ].sum()
    net_impacts = pd.DataFrame(
        [
            {
                "Target": target,
                "SelectedScale": effect["SelectedScale"],
                "IncludedDrivers": ", ".join(drivers),
                "DriverSelectionRule": driver_selection_rule,
                "OneDayDate": maximum_date,
                "NEI": net_effect,
                "GPRDWeight": gprd_weight,
                "GPRDWeightPercent": gprd_weight,
                "NarrowImpact": net_effect * gprd_weight / 100,
                "GPRDGoldOVXWeight": broad_weight,
                "GPRD_Gold_OVX_WeightPercent": broad_weight,
                "BroadImpact": net_effect * broad_weight / 100,
                "LagOrder": lag,
                "LagSelectionRule": lag_selection_rule,
                "VMDSource": _vmd_source_note(),
                "VMD_K": vmd_k,
                "FEVD_h": h,
            }
        ]
    )
    settings = pd.DataFrame(
        [
            {
                "Target": target,
                "SelectedScale": effect["SelectedScale"],
                "IncludedDrivers": ", ".join(drivers),
                "VARLag": lag,
                "LagOrder": lag,
                "LagCriterion": "BIC",
                "LagSelectionRule": lag_selection_rule,
                "VMDSource": _vmd_source_note(),
                "VMD_K": vmd_k,
                "FEVD_h": h,
                "RollingWindow": PAPER_ROLLING_WINDOW,
                "MinDate": effect["MinimumDate"],
                "MaxDate": effect["MaximumDate"],
                "DriverSelectionRule": driver_selection_rule,
                "MethodNote": "FEVD horizon h follows the selected-scale min-to-max trading-day interval; contribution weights use the selected-scale maximum date only.",
            }
        ]
    )
    return settings, contribution, net_impacts, var_data


def _structural_break_test(scale_df: pd.DataFrame, target: str, effect: dict[str, Any]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Run fixed event-start trend-break test on selected scale."""
    column = f"{target}_SelectedScale"
    data = scale_df[["Date", column]].dropna().sort_values("Date").reset_index(drop=True)
    break_date = pd.to_datetime(effect.get("EventStartDate", effect["MinimumDate"]))
    data["t"] = np.arange(1, len(data) + 1, dtype=float)
    break_matches = np.where(pd.to_datetime(data["Date"]) >= break_date)[0]
    if len(break_matches) == 0:
        raise ValueError("Break date is outside the available date range.")
    break_index = int(break_matches[0]) + 1
    data["D"] = (data["t"] >= break_index).astype(float)
    data["PostT"] = data["D"] * (data["t"] - break_index + 1)
    y = data[column].to_numpy(dtype=float)
    x_restricted = np.column_stack([np.ones(len(data)), data["t"].to_numpy(dtype=float)])
    x_break = np.column_stack(
        [
            np.ones(len(data)),
            data["t"].to_numpy(dtype=float),
            data["D"].to_numpy(dtype=float),
            data["PostT"].to_numpy(dtype=float),
        ]
    )
    beta_r, *_ = np.linalg.lstsq(x_restricted, y, rcond=None)
    beta_b, *_ = np.linalg.lstsq(x_break, y, rcond=None)
    fit_r = x_restricted @ beta_r
    fit_b = x_break @ beta_b
    rss_r = float(np.sum((y - fit_r) ** 2))
    rss_b = float(np.sum((y - fit_b) ** 2))
    df_num = x_break.shape[1] - x_restricted.shape[1]
    df_den = len(data) - x_break.shape[1]
    f_stat = ((rss_r - rss_b) / df_num) / max(rss_b / max(df_den, 1), 1e-12)
    try:
        from scipy.stats import f as f_dist

        p_value = float(f_dist.sf(f_stat, df_num, df_den))
    except Exception:  # noqa: BLE001
        p_value = np.nan
    slope_pre = float(beta_b[1])
    slope_post = float(beta_b[1] + beta_b[3])
    summary = pd.DataFrame(
        [
            {
                "Target": target,
                "SelectedScale": effect["SelectedScale"],
                "BreakDate": break_date,
                "RestrictedRSS": rss_r,
                "BreakModelRSS": rss_b,
                "FStatistic": f_stat,
                "PValue": p_value,
                "FStatisticWithStars": f"{f_stat:.3f}{significance_stars(p_value)}",
                "PreBreakSlope": slope_pre,
                "PostBreakSlope": slope_post,
                "SlopeChange": slope_post - slope_pre,
                "LevelShift": float(beta_b[2]),
                "Significance": "Significant at 10% level" if p_value < 0.10 else "Not significant at 10% level",
            }
        ]
    )
    fit = data[["Date", column]].copy()
    fit["RestrictedFit"] = fit_r
    fit["BreakModelFit"] = fit_b
    return summary, fit


def _round_numeric(df: pd.DataFrame) -> pd.DataFrame:
    """Round numeric columns to three decimals."""
    result = df.copy()
    numeric_cols = result.select_dtypes(include=[np.number]).columns
    result[numeric_cols] = result[numeric_cols].round(3)
    return result


def _numeric_variable_columns(data: pd.DataFrame) -> list[str]:
    """Return non-Date columns that contain at least one numeric observation."""
    variables: list[str] = []
    for column in data.columns:
        if column == "Date":
            continue
        numeric = pd.to_numeric(data[column], errors="coerce")
        if numeric.notna().any() and numeric.nunique(dropna=True) > 1:
            variables.append(str(column))
    return variables


def _normalise_requested_variables(
    requested: list[str] | tuple[str, ...] | None,
    available: list[str],
    label: str,
    max_count: int | None = None,
) -> list[str]:
    """Validate requested variable names against available numeric columns."""
    if requested is None:
        return []
    seen: set[str] = set()
    output: list[str] = []
    available_set = set(available)
    missing: list[str] = []
    for variable in requested:
        name = str(variable).strip()
        if not name or name in seen:
            continue
        if name not in available_set:
            missing.append(name)
            continue
        seen.add(name)
        output.append(name)
    if missing:
        warnings.warn(f"{label} variables are unavailable and were skipped: {', '.join(missing)}")
    if max_count is not None and len(output) > max_count:
        raise ValueError(f"{label} supports at most {max_count} variables per run.")
    return output


def _resolve_analysis_variables(
    data: pd.DataFrame,
    target_variables: list[str] | tuple[str, ...] | None,
    candidate_variables: list[str] | tuple[str, ...] | None,
) -> tuple[list[str], list[str]]:
    """Resolve requested target and explanatory variables against available data."""
    available_variables = _numeric_variable_columns(data)
    if target_variables is None:
        targets = [target for target in ["WTI", "Brent"] if target in available_variables]
        if not targets:
            targets = available_variables[:1]
    else:
        targets = _normalise_requested_variables(
            target_variables,
            available_variables,
            label="Target",
            max_count=2,
        )
    if not targets:
        raise ValueError("No valid target variable is available. Select one or two numeric target variables.")

    if candidate_variables is None:
        default_pool = [
            candidate
            for candidate in DEFAULT_CANDIDATES
            if candidate in available_variables
        ]
        candidate_pool = default_pool or [
            variable for variable in available_variables if variable not in targets
        ]
    else:
        candidate_pool = _normalise_requested_variables(
            candidate_variables,
            available_variables,
            label="Candidate",
        )
    if not candidate_pool:
        raise ValueError("No valid explanatory variable is available for paper-method replication.")
    return targets, candidate_pool


def _setup_plot() -> None:
    """Apply paper-style matplotlib settings."""
    apply_publication_plot_style(
        **{
            "font.size": 11,
            "axes.titlesize": 14,
            "axes.labelsize": 12,
            "xtick.labelsize": 10,
            "ytick.labelsize": 10,
            "legend.fontsize": 10,
            "axes.edgecolor": "#111827",
            "axes.linewidth": 0.9,
            "grid.color": "#D9D9D9",
            "grid.linewidth": 0.5,
            "grid.alpha": 0.85,
        }
    )


def _save_fig(fig: plt.Figure, png: Path, pdf: Path) -> None:
    """Save PNG and PDF figures."""
    png.parent.mkdir(parents=True, exist_ok=True)
    for ax in fig.axes:
        ax.tick_params(axis="both", colors="#111827", width=0.8)
        for spine in ax.spines.values():
            spine.set_color("#111827")
            spine.set_linewidth(0.9)
    fig.align_labels()
    fig.tight_layout(pad=1.0)
    save_figure_pair(fig, png, pdf)


def _safe_file_token(value: Any) -> str:
    """Return a filesystem-friendly token for generated figure variants."""
    token = re.sub(r"[^A-Za-z0-9]+", "_", str(value)).strip("_").lower()
    return token or "variable"


def _figure_variant_paths(stem: str) -> tuple[Path, Path]:
    """Return PNG/PDF paths for a dynamic paper figure."""
    return FIGURES_DIR / f"{stem}.png", FIGURES_DIR / f"{stem}.pdf"


def _normalise_series(series: pd.Series) -> pd.Series:
    """Return a z-score normalized series with stable zero-variance handling."""
    values = pd.to_numeric(series, errors="coerce")
    std = values.std()
    return (values - values.mean()) / (std if std and np.isfinite(std) else 1)


def _instantaneous_frequency(values: pd.Series | np.ndarray) -> np.ndarray:
    """Return positive instantaneous frequency from a Hilbert transform."""
    array = np.asarray(values, dtype=float)
    if len(array) < 3 or np.nanstd(array) <= 1e-12:
        return np.array([], dtype=float)
    try:
        from scipy.signal import hilbert

        analytic = hilbert(array)
    except Exception:  # noqa: BLE001 - deterministic FFT fallback mirrors _average_period.
        spectrum = np.fft.fft(array)
        n_obs = len(array)
        multiplier = np.zeros(n_obs)
        if n_obs % 2 == 0:
            multiplier[0] = 1
            multiplier[n_obs // 2] = 1
            multiplier[1 : n_obs // 2] = 2
        else:
            multiplier[0] = 1
            multiplier[1 : (n_obs + 1) // 2] = 2
        analytic = np.fft.ifft(spectrum * multiplier)
    phase = np.unwrap(np.angle(analytic))
    freq = np.abs(np.diff(phase)) / (2 * np.pi)
    freq[~np.isfinite(freq)] = np.nan
    return freq


def _normalise_plot_date(value: Any) -> pd.Timestamp | None:
    """Return one timezone-free date for plotting annotations."""
    timestamp = pd.to_datetime(value, errors="coerce")
    if pd.isna(timestamp):
        return None
    timestamp = pd.Timestamp(timestamp)
    if timestamp.tzinfo is not None:
        timestamp = timestamp.tz_localize(None)
    return timestamp.normalize()


def _format_axis_date(timestamp: pd.Timestamp | None) -> str:
    """Format an axis date label."""
    return "" if timestamp is None else timestamp.strftime("%Y-%m-%d")


def _even_date_ticks(
    start: pd.Timestamp,
    end: pd.Timestamp,
    max_ticks: int,
) -> list[pd.Timestamp]:
    """Return evenly spaced date ticks that always include start and end."""
    start = start.normalize()
    end = end.normalize()
    if end <= start:
        return [start]
    span_days = max(1, (end - start).days)
    tick_count = max(2, min(max_ticks, span_days + 1))
    offsets = [round(index * span_days / (tick_count - 1)) for index in range(tick_count)]
    ticks = [start + pd.Timedelta(days=int(offset)) for offset in offsets]
    ticks[0] = start
    ticks[-1] = end
    unique_ticks: list[pd.Timestamp] = []
    for tick in ticks:
        if not unique_ticks or tick != unique_ticks[-1]:
            unique_ticks.append(tick)
    return unique_ticks


def _mark_start_end_dates(
    ax: plt.Axes,
    dates: pd.Series,
    start_date: Any | None = None,
    end_date: Any | None = None,
) -> None:
    """Mark start/end dates and avoid nearby tick-label collisions."""
    parsed_dates = pd.to_datetime(dates, errors="coerce").dropna()
    if parsed_dates.empty:
        return
    data_start = _normalise_plot_date(parsed_dates.min())
    data_end = _normalise_plot_date(parsed_dates.max())
    label_start = _normalise_plot_date(start_date) or data_start
    label_end = _normalise_plot_date(end_date) or data_end
    if data_start is None or data_end is None or label_start is None or label_end is None:
        return
    label_start = max(data_start, min(label_start, data_end))
    label_end = max(data_start, min(label_end, data_end))
    if label_end < label_start:
        label_start, label_end = label_end, label_start

    figure_width = ax.figure.get_size_inches()[0] if ax.figure is not None else 8
    max_ticks = max(2, min(6, int(figure_width // 1.8)))
    ticks = _even_date_ticks(label_start, label_end, max_ticks=max_ticks)
    labels = []
    for tick in ticks:
        if tick == label_start:
            labels.append(f"Start\n{_format_axis_date(tick)}")
        elif tick == label_end:
            labels.append(f"End\n{_format_axis_date(tick)}")
        else:
            labels.append(tick.strftime("%Y-%m-%d"))

    ax.set_xlim(label_start, label_end)
    ax.set_xticks(ticks)
    ax.set_xticklabels(labels, rotation=30, ha="right")
    ax.tick_params(axis="x", labelsize=10, colors="#111827")
    ax.axvline(label_start, color="#111827", linestyle=":", linewidth=1.1)
    ax.axvline(label_end, color="#111827", linestyle=":", linewidth=1.1)
    ax.annotate(
        "Start",
        xy=(label_start, 1.0),
        xycoords=("data", "axes fraction"),
        xytext=(3, -8),
        textcoords="offset points",
        ha="left",
        va="top",
        fontsize=8,
        color="#111827",
    )
    ax.annotate(
        "End",
        xy=(label_end, 1.0),
        xycoords=("data", "axes fraction"),
        xytext=(-3, -8),
        textcoords="offset points",
        ha="right",
        va="top",
        fontsize=8,
        color="#111827",
    )


def _plot_selected_scale(scale_df: pd.DataFrame, target: str, effect: dict[str, Any]) -> None:
    """Plot normalized actual target and selected scale."""
    _setup_plot()
    column = f"{target}_SelectedScale"
    plot_df = scale_df[["Date", target, column]].dropna().copy()
    for col in [target, column]:
        plot_df[f"{col}_Normalized"] = _normalise_series(plot_df[col])
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(plot_df["Date"], plot_df[f"{target}_Normalized"], label=f"Actual {target}", linewidth=1.4)
    ax.plot(plot_df["Date"], plot_df[f"{column}_Normalized"], label=f"{target} {effect['SelectedScale']}", linewidth=1.8)
    ax.axvline(pd.to_datetime(effect["MinimumDate"]), color="#DC2626", linestyle="--", linewidth=1)
    ax.axvline(pd.to_datetime(effect["MaximumDate"]), color="#334155", linestyle="--", linewidth=1)
    ax.set_xlabel("Date")
    ax.set_ylabel("Normalized value")
    _mark_start_end_dates(
        ax,
        plot_df["Date"],
        start_date=effect.get("EventStartDate", plot_df["Date"].min()),
        end_date=plot_df["Date"].max(),
    )
    ax.legend(frameon=False)
    ax.grid(True, color="#D9D9D9", linewidth=0.5, alpha=0.85)
    _save_fig(fig, OUTPUT_PATHS["scale_figure"], OUTPUT_PATHS["scale_figure_pdf"])


def _plot_price_event(data: pd.DataFrame, targets: list[str], event_start_date: Any | None) -> None:
    """Plot selected crude-oil prices and the event start."""
    _setup_plot()
    plot_targets = [target for target in targets if target in data.columns]
    if not plot_targets:
        return
    plot_df = data[["Date", *plot_targets]].dropna(subset=plot_targets, how="all").copy()
    if plot_df.empty:
        return
    fig, ax = plt.subplots(figsize=(10, 5))
    for target in plot_targets:
        ax.plot(plot_df["Date"], plot_df[target], label=target, linewidth=1.5)
    event_date = _normalise_plot_date(event_start_date)
    if event_date is not None:
        ax.axvline(event_date, color="#DC2626", linestyle="--", linewidth=1.2, label="Event start")
    ax.set_xlabel("Date")
    ax.set_ylabel("Price")
    _mark_start_end_dates(ax, plot_df["Date"], start_date=event_start_date or plot_df["Date"].min(), end_date=plot_df["Date"].max())
    ax.legend(frameon=False)
    ax.grid(True, color="#D9D9D9", linewidth=0.5, alpha=0.85)
    _save_fig(fig, OUTPUT_PATHS["price_event_figure"], OUTPUT_PATHS["price_event_figure_pdf"])


def _plot_vmd_decomposition_figures(
    data: pd.DataFrame,
    variables: list[str],
    vmd_k: int,
    start_date: Any | None = None,
    end_date: Any | None = None,
) -> None:
    """Save VMD decomposition figures for selected paper variables."""
    _setup_plot()
    for variable in list(dict.fromkeys(variables)):
        if variable not in data.columns:
            continue
        series_df = data[["Date", variable]].copy()
        series_df[variable] = pd.to_numeric(series_df[variable], errors="coerce")
        series_df = series_df.dropna(subset=["Date", variable]).reset_index(drop=True)
        if len(series_df) <= vmd_k + 5 or series_df[variable].std() <= 1e-12:
            continue
        try:
            imfs = _vmd_frame(series_df[variable], variable, vmd_k=vmd_k)
        except Exception as exc:  # noqa: BLE001 - skip only this figure.
            warnings.warn(f"Could not plot VMD decomposition for {variable}: {exc}")
            continue
        plot_df = pd.concat([series_df[["Date", variable]], imfs], axis=1)
        fig = _create_vmd_decomposition_figure(plot_df, variable, vmd_k)
        date_axis = fig.axes[1] if vmd_k > 12 else fig.axes[-1]
        _mark_start_end_dates(
            date_axis,
            plot_df["Date"],
            start_date=start_date or plot_df["Date"].min(),
            end_date=end_date or plot_df["Date"].max(),
        )
        date_axis.set_xlabel("Date")
        png, pdf = _figure_variant_paths(f"paper_vmd_decomposition_{_safe_file_token(variable)}")
        _save_fig(fig, png, pdf)


def _create_vmd_decomposition_figure(
    plot_df: pd.DataFrame,
    variable: str,
    vmd_k: int,
) -> plt.Figure:
    """Create a readable VMD figure with bounded complexity for high K."""
    if vmd_k <= 12:
        rows = vmd_k + 1
        fig, axes = plt.subplots(
            rows,
            1,
            figsize=(10, max(5.2, 1.35 * rows)),
            sharex=True,
        )
        axes = np.atleast_1d(axes)
        axes[0].plot(plot_df["Date"], plot_df[variable], color="#111827", linewidth=1.2)
        axes[0].set_ylabel(variable)
        axes[0].set_title(f"VMD decomposition of {variable}")
        for mode_index in range(1, vmd_k + 1):
            column = f"{variable}_IMF{mode_index}"
            axes[mode_index].plot(
                plot_df["Date"],
                plot_df[column],
                color="#64748B",
                linewidth=1.0,
            )
            axes[mode_index].set_ylabel(f"IMF{mode_index}")
        for axis in axes:
            axis.grid(True, color="#D9D9D9", linewidth=0.5, alpha=0.85)
        return fig

    fig, (source_axis, heatmap_axis) = plt.subplots(
        2,
        1,
        figsize=(10, 7.5),
        gridspec_kw={"height_ratios": [1, 3]},
        sharex=True,
    )
    source_axis.plot(plot_df["Date"], plot_df[variable], color="#111827", linewidth=1.2)
    source_axis.set_ylabel(variable)
    source_axis.set_title(f"VMD decomposition of {variable}")
    source_axis.grid(True, color="#D9D9D9", linewidth=0.5, alpha=0.85)

    mode_columns = [f"{variable}_IMF{mode_index}" for mode_index in range(1, vmd_k + 1)]
    mode_matrix = plot_df[mode_columns].to_numpy(dtype=float).T
    row_means = np.nanmean(mode_matrix, axis=1, keepdims=True)
    row_scales = np.nanstd(mode_matrix, axis=1, keepdims=True)
    row_scales[~np.isfinite(row_scales) | (row_scales <= 1e-12)] = 1.0
    normalized_modes = np.clip((mode_matrix - row_means) / row_scales, -3, 3)
    date_values = mdates.date2num(pd.to_datetime(plot_df["Date"]).to_numpy())
    image = heatmap_axis.imshow(
        normalized_modes,
        aspect="auto",
        interpolation="nearest",
        cmap="RdBu_r",
        vmin=-3,
        vmax=3,
        extent=[date_values[0], date_values[-1], vmd_k + 0.5, 0.5],
    )
    tick_modes = np.unique(np.linspace(1, vmd_k, min(8, vmd_k), dtype=int))
    heatmap_axis.set_yticks(tick_modes)
    heatmap_axis.set_yticklabels([f"IMF{mode_index}" for mode_index in tick_modes])
    heatmap_axis.set_ylabel("Normalized IMF")
    heatmap_axis.xaxis_date()
    colorbar = fig.colorbar(image, ax=heatmap_axis, pad=0.02)
    colorbar.set_label("Standard deviations")
    return fig


def _plot_hht_imf1_frequency(
    data: pd.DataFrame,
    targets: list[str],
    vmd_k: int,
    event_start_date: Any | None,
    end_date: Any | None = None,
) -> None:
    """Plot normalized HHT instantaneous frequency for target IMF1 components."""
    _setup_plot()
    rows = []
    for target in targets:
        if target not in data.columns:
            continue
        series_df = data[["Date", target]].copy()
        series_df[target] = pd.to_numeric(series_df[target], errors="coerce")
        series_df = series_df.dropna(subset=["Date", target]).reset_index(drop=True)
        if len(series_df) <= vmd_k + 5:
            continue
        try:
            imfs = _vmd_frame(series_df[target], target, vmd_k=vmd_k)
        except Exception as exc:  # noqa: BLE001
            warnings.warn(f"Could not compute HHT frequency for {target}: {exc}")
            continue
        freq = _instantaneous_frequency(imfs[f"{target}_IMF1"])
        if len(freq) == 0:
            continue
        freq_series = pd.Series(freq, dtype=float)
        rows.append(
            pd.DataFrame(
                {
                    "Date": series_df["Date"].iloc[1 : len(freq) + 1].to_numpy(),
                    "Target": target,
                    "NormalizedFrequency": _normalise_series(freq_series).to_numpy(),
                }
            )
        )
    if not rows:
        return
    plot_df = pd.concat(rows, ignore_index=True)
    fig, ax = plt.subplots(figsize=(10, 5))
    for target, target_df in plot_df.groupby("Target"):
        ax.plot(target_df["Date"], target_df["NormalizedFrequency"], label=f"{target} IMF1", linewidth=1.2)
    event_date = _normalise_plot_date(event_start_date)
    if event_date is not None:
        ax.axvline(event_date, color="#DC2626", linestyle="--", linewidth=1.0, label="Event start")
    ax.set_xlabel("Date")
    ax.set_ylabel("Normalized instantaneous frequency")
    _mark_start_end_dates(
        ax,
        plot_df["Date"],
        start_date=event_start_date or plot_df["Date"].min(),
        end_date=end_date or plot_df["Date"].max(),
    )
    ax.legend(frameon=False)
    ax.grid(True, color="#D9D9D9", linewidth=0.5, alpha=0.85)
    _save_fig(fig, OUTPUT_PATHS["hht_imf1_figure"], OUTPUT_PATHS["hht_imf1_figure_pdf"])


def _plot_selected_scale_panel(items: list[tuple[str, pd.DataFrame, dict[str, Any]]]) -> None:
    """Plot normalized actual prices and selected scales for all targets."""
    _setup_plot()
    items = [item for item in items if not item[1].empty]
    if not items:
        return
    fig, axes = plt.subplots(len(items), 1, figsize=(10, max(5, 4.2 * len(items))), sharex=False)
    axes = np.atleast_1d(axes)
    for ax, (target, scale_df, effect) in zip(axes, items):
        column = f"{target}_SelectedScale"
        plot_df = scale_df[["Date", target, column]].dropna().copy()
        if plot_df.empty:
            continue
        ax.plot(plot_df["Date"], _normalise_series(plot_df[target]), label=f"Actual {target}", linewidth=1.3)
        ax.plot(
            plot_df["Date"],
            _normalise_series(plot_df[column]),
            label=f"{target} {effect['SelectedScale']}",
            linewidth=1.6,
        )
        ax.axvline(pd.to_datetime(effect["MinimumDate"]), color="#DC2626", linestyle="--", linewidth=1)
        ax.axvline(pd.to_datetime(effect["MaximumDate"]), color="#334155", linestyle="--", linewidth=1)
        ax.set_title(f"{target}: selected scale {effect['SelectedScale']}")
        ax.set_ylabel("Normalized value")
        _mark_start_end_dates(
            ax,
            plot_df["Date"],
            start_date=effect.get("EventStartDate", plot_df["Date"].min()),
            end_date=plot_df["Date"].max(),
        )
        ax.legend(frameon=False)
        ax.grid(True, color="#D9D9D9", linewidth=0.5, alpha=0.85)
    axes[-1].set_xlabel("Date")
    _save_fig(fig, OUTPUT_PATHS["scale_figure"], OUTPUT_PATHS["scale_figure_pdf"])


def _plot_scale_statistics(stats: pd.DataFrame) -> None:
    """Plot variance contribution and correlation by IMF."""
    _setup_plot()
    if stats.empty:
        return
    groups = list(stats.groupby("Target")) if "Target" in stats.columns else [("Target", stats)]
    fig, axes = plt.subplots(len(groups), 1, figsize=(9, max(5, 4.2 * len(groups))), sharex=False)
    axes = np.atleast_1d(axes)
    for ax1, (target, group) in zip(axes, groups):
        labels = group["IMF"].astype(str).tolist()
        x = np.arange(len(labels))
        ax1.bar(x - 0.18, group["VarianceContributionPercent"], width=0.36, label="Variance contribution (%)", color="#94A3B8")
        ax2 = ax1.twinx()
        ax2.bar(x + 0.18, group["CorrelationWithOriginal"], width=0.36, label="Correlation", color="#DC2626", alpha=0.75)
        ax1.set_xticks(x)
        ax1.set_xticklabels(labels)
        ax1.set_xlabel("IMF")
        ax1.set_ylabel("Variance contribution (%)")
        ax2.set_ylabel("Correlation")
        ax1.set_title(str(target))
        ax1.grid(True, axis="y", color="#D9D9D9", linewidth=0.5, alpha=0.85)
        lines1, labels1 = ax1.get_legend_handles_labels()
        lines2, labels2 = ax2.get_legend_handles_labels()
        ax1.legend(lines1 + lines2, labels1 + labels2, frameon=False, loc="upper left")
    _save_fig(fig, OUTPUT_PATHS["stats_figure"], OUTPUT_PATHS["stats_figure_pdf"])


def _plot_mrgc_heatmap(screening: pd.DataFrame) -> None:
    """Plot MRGC retained/dropped heatmap for candidate variables and levels."""
    _setup_plot()
    if screening.empty:
        return
    index_columns = ["Target", "CandidateVariable"] if "Target" in screening.columns else ["CandidateVariable"]
    pivot = screening.pivot_table(
        index=index_columns,
        columns="Level",
        values="Retained",
        aggfunc=lambda values: float(pd.Series(values).fillna(False).any()),
        fill_value=0,
    )
    imf_levels = sorted(
        [
            level
            for level in pivot.columns.astype(str).tolist()
            if re.match(r"^IMF\d+$", level)
        ],
        key=lambda value: int(value.replace("IMF", "")),
    )
    pivot = pivot.reindex(columns=["Original", *imf_levels], fill_value=0)
    fig, ax = plt.subplots(figsize=(9, max(4, 0.45 * len(pivot) + 1.5)))
    image = ax.imshow(pivot.to_numpy(dtype=float), cmap="Reds", vmin=0, vmax=1, aspect="auto")
    ax.set_xticks(np.arange(len(pivot.columns)))
    ax.set_xticklabels(pivot.columns)
    ax.set_yticks(np.arange(len(pivot.index)))
    if isinstance(pivot.index, pd.MultiIndex):
        ax.set_yticklabels([f"{target} | {variable}" for target, variable in pivot.index])
    else:
        ax.set_yticklabels(pivot.index)
    ax.set_xlabel("Resolution level")
    ax.set_ylabel("Candidate variable")
    for i in range(len(pivot.index)):
        for j in range(len(pivot.columns)):
            ax.text(j, i, "Yes" if pivot.iloc[i, j] else "No", ha="center", va="center", color="#111827", fontsize=8)
    fig.colorbar(image, ax=ax, fraction=0.03, pad=0.02, label="Retained")
    _save_fig(fig, OUTPUT_PATHS["mrgc_figure"], OUTPUT_PATHS["mrgc_figure_pdf"])


def _plot_contributions(contribution: pd.DataFrame) -> None:
    """Plot external relative contribution weights."""
    _setup_plot()
    if contribution.empty:
        return
    groups = list(contribution.groupby("Target")) if "Target" in contribution.columns else [("Target", contribution)]
    for target, group in groups:
        selected_scale = (
            str(group["SelectedScale"].dropna().iloc[0])
            if "SelectedScale" in group.columns and group["SelectedScale"].notna().any()
            else "SelectedScale"
        )
        plot_df = group.sort_values("ExternalRelativeWeight", ascending=False).copy()
        fig_width = max(9.5, 0.72 * len(plot_df) + 3.0)
        fig, ax = plt.subplots(figsize=(fig_width, 5.2))
        x = np.arange(len(plot_df))
        ax.bar(
            x,
            pd.to_numeric(plot_df["ExternalRelativeWeight"], errors="coerce"),
            color="#64748B",
            width=0.68,
        )
        ax.set_xticks(x)
        ax.set_xticklabels(plot_df["ExternalVariable"].astype(str), rotation=35, ha="right")
        ax.set_xlabel("External variable")
        ax.set_ylabel("External relative weight (%)")
        ax.set_title(f"{target} {selected_scale} external relative contribution")
        ax.grid(True, axis="y", color="#D9D9D9", linewidth=0.5, alpha=0.85)
        png, pdf = _figure_variant_paths(
            f"paper_external_contribution_{_safe_file_token(target)}_{_safe_file_token(selected_scale)}"
        )
        _save_fig(fig, png, pdf)

    fig, axes = plt.subplots(len(groups), 1, figsize=(9.5, max(5, 3.4 * len(groups))), sharex=False)
    axes = np.atleast_1d(axes)
    for ax, (target, group) in zip(axes, groups):
        plot_df = group.sort_values("ExternalRelativeWeight", ascending=True)
        ax.barh(plot_df["ExternalVariable"], plot_df["ExternalRelativeWeight"], color="#64748B")
        ax.set_xlabel("External relative weight (%)")
        ax.set_ylabel("External variable")
        ax.set_title(str(target))
        ax.grid(True, axis="x", color="#D9D9D9", linewidth=0.5, alpha=0.85)
    _save_fig(fig, OUTPUT_PATHS["contribution_figure"], OUTPUT_PATHS["contribution_figure_pdf"])


def _plot_net_impacts(net_impacts: pd.DataFrame) -> None:
    """Plot narrow and broad net impacts."""
    _setup_plot()
    if net_impacts.empty:
        return
    labels = ["NarrowImpact", "BroadImpact", "NEI"]
    target_labels = net_impacts.get(
        "Target",
        pd.Series([f"Target {idx + 1}" for idx in range(len(net_impacts))]),
    ).astype(str).tolist()
    x = np.arange(len(target_labels))
    width = 0.24
    fig, ax = plt.subplots(figsize=(8.5, 4.8))
    for offset, label, color in zip([-width, 0, width], labels, ["#DC2626", "#64748B", "#CBD5E1"]):
        ax.bar(x + offset, pd.to_numeric(net_impacts[label], errors="coerce"), width=width, label=label, color=color)
    ax.set_xticks(x)
    ax.set_xticklabels(target_labels)
    ax.set_ylabel("Net impact")
    ax.legend(frameon=False)
    ax.grid(True, axis="y", color="#D9D9D9", linewidth=0.5, alpha=0.85)
    _save_fig(fig, OUTPUT_PATHS["net_impact_figure"], OUTPUT_PATHS["net_impact_figure_pdf"])


def _plot_break_fit(fit_df: pd.DataFrame, break_summary: pd.DataFrame, target: str) -> None:
    """Plot fixed-break trend fit."""
    _setup_plot()
    if fit_df.empty:
        return
    value_col = [column for column in fit_df.columns if column.endswith("_SelectedScale")][0]
    break_date = pd.to_datetime(break_summary["BreakDate"].iloc[0])
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(fit_df["Date"], fit_df[value_col], label=f"{target} selected scale", linewidth=1.3)
    ax.plot(fit_df["Date"], fit_df["BreakModelFit"], label="Break-model fit", linewidth=1.5)
    ax.axvline(break_date, color="#DC2626", linestyle="--", linewidth=1)
    ax.set_xlabel("Date")
    ax.set_ylabel("Selected-scale value")
    _mark_start_end_dates(ax, fit_df["Date"], start_date=break_date, end_date=fit_df["Date"].max())
    ax.legend(frameon=False)
    ax.grid(True, color="#D9D9D9", linewidth=0.5, alpha=0.85)
    _save_fig(fig, OUTPUT_PATHS["break_figure"], OUTPUT_PATHS["break_figure_pdf"])


def _plot_break_fit_panel(items: list[tuple[str, pd.DataFrame, pd.DataFrame]]) -> None:
    """Plot fixed-break trend fits for all selected targets."""
    _setup_plot()
    items = [item for item in items if not item[1].empty and not item[2].empty]
    if not items:
        return
    fig, axes = plt.subplots(len(items), 1, figsize=(10, max(5, 4.2 * len(items))), sharex=False)
    axes = np.atleast_1d(axes)
    for ax, (target, fit_df, break_summary) in zip(axes, items):
        value_col = [column for column in fit_df.columns if column.endswith("_SelectedScale")][0]
        break_date = pd.to_datetime(break_summary["BreakDate"].iloc[0])
        ax.plot(fit_df["Date"], fit_df[value_col], label=f"{target} selected scale", linewidth=1.3)
        ax.plot(fit_df["Date"], fit_df["BreakModelFit"], label="Break-model fit", linewidth=1.5)
        ax.axvline(break_date, color="#DC2626", linestyle="--", linewidth=1)
        ax.set_title(f"{target}: event-start trend-break fit")
        ax.set_ylabel("Selected-scale value")
        _mark_start_end_dates(ax, fit_df["Date"], start_date=break_date, end_date=fit_df["Date"].max())
        ax.legend(frameon=False)
        ax.grid(True, color="#D9D9D9", linewidth=0.5, alpha=0.85)
    axes[-1].set_xlabel("Date")
    _save_fig(fig, OUTPUT_PATHS["break_figure"], OUTPUT_PATHS["break_figure_pdf"])


def _break_model_rss(y: np.ndarray, t: np.ndarray, break_index: int) -> float:
    """Return piecewise trend RSS for a one-based candidate break index."""
    d = (t >= break_index).astype(float)
    post_t = d * (t - break_index + 1)
    x_break = np.column_stack([np.ones(len(y)), t, d, post_t])
    beta, *_ = np.linalg.lstsq(x_break, y, rcond=None)
    fit = x_break @ beta
    return float(np.sum((y - fit) ** 2))


def _optimal_break_rss_profile(scale_df: pd.DataFrame, target: str, effect: dict[str, Any]) -> pd.DataFrame:
    """Compute RSS profile across candidate structural-break dates."""
    column = f"{target}_SelectedScale"
    data = scale_df[["Date", column]].dropna().sort_values("Date").reset_index(drop=True)
    if len(data) < 30:
        return pd.DataFrame()
    y = data[column].to_numpy(dtype=float)
    t = np.arange(1, len(data) + 1, dtype=float)
    lower = max(5, int(len(data) * 0.10))
    upper = min(len(data) - 5, int(len(data) * 0.90))
    rows = []
    for break_index in range(lower, upper + 1):
        rows.append(
            {
                "Target": target,
                "SelectedScale": effect["SelectedScale"],
                "CandidateBreakDate": data.loc[break_index - 1, "Date"],
                "CandidateBreakIndex": break_index,
                "BreakModelRSS": _break_model_rss(y, t, break_index),
                "EventStartDate": effect.get("EventStartDate"),
            }
        )
    profile = pd.DataFrame(rows)
    if profile.empty:
        return profile
    best_idx = pd.to_numeric(profile["BreakModelRSS"], errors="coerce").idxmin()
    best_date = profile.loc[best_idx, "CandidateBreakDate"]
    profile["OptimalBreakDate"] = best_date
    profile["IsOptimalBreak"] = pd.to_datetime(profile["CandidateBreakDate"]).eq(pd.to_datetime(best_date))
    return profile


def _plot_optimal_break_rss_profiles(profile_df: pd.DataFrame) -> None:
    """Plot optimal-break RSS profiles for selected targets."""
    _setup_plot()
    if profile_df.empty:
        return
    groups = list(profile_df.groupby("Target"))
    fig, axes = plt.subplots(len(groups), 1, figsize=(10, max(5, 4.0 * len(groups))), sharex=False)
    axes = np.atleast_1d(axes)
    for ax, (target, group) in zip(axes, groups):
        group = group.sort_values("CandidateBreakDate")
        ax.plot(group["CandidateBreakDate"], group["BreakModelRSS"], color="#64748B", linewidth=1.4, label="Break-model RSS")
        event_date = _normalise_plot_date(group["EventStartDate"].dropna().iloc[0] if group["EventStartDate"].notna().any() else None)
        optimal_date = _normalise_plot_date(group["OptimalBreakDate"].dropna().iloc[0] if group["OptimalBreakDate"].notna().any() else None)
        if event_date is not None:
            ax.axvline(event_date, color="#DC2626", linestyle="--", linewidth=1.0, label="Event start")
        if optimal_date is not None:
            ax.axvline(optimal_date, color="#111827", linestyle=":", linewidth=1.0, label="Optimal break")
        ax.set_title(f"{target}: optimal-break RSS profile")
        ax.set_ylabel("RSS")
        _mark_start_end_dates(
            ax,
            group["CandidateBreakDate"],
            start_date=group["CandidateBreakDate"].min(),
            end_date=group["CandidateBreakDate"].max(),
        )
        ax.legend(frameon=False)
        ax.grid(True, color="#D9D9D9", linewidth=0.5, alpha=0.85)
    axes[-1].set_xlabel("Candidate break date")
    _save_fig(fig, OUTPUT_PATHS["optimal_break_rss_figure"], OUTPUT_PATHS["optimal_break_rss_figure_pdf"])


def _save_dashboard(
    summary: pd.DataFrame,
    mrgc: pd.DataFrame,
    scale_stats: pd.DataFrame,
    effect: pd.DataFrame,
    selected_scale_granger: pd.DataFrame,
    settings: pd.DataFrame,
    contribution: pd.DataFrame,
    net_impacts: pd.DataFrame,
    break_test: pd.DataFrame,
) -> None:
    """Save a multi-sheet paper replication dashboard workbook."""
    with pd.ExcelWriter(OUTPUT_PATHS["dashboard"]) as writer:
        _round_numeric(summary).to_excel(writer, sheet_name="Summary", index=False)
        _round_numeric(mrgc).to_excel(writer, sheet_name="MRGC", index=False)
        _round_numeric(scale_stats).to_excel(writer, sheet_name="ScaleStatistics", index=False)
        _round_numeric(effect).to_excel(writer, sheet_name="SelectedScaleEffect", index=False)
        _round_numeric(selected_scale_granger).to_excel(
            writer,
            sheet_name="SelectedScaleGranger",
            index=False,
        )
        _round_numeric(settings).to_excel(writer, sheet_name="TVPVARSettings", index=False)
        _round_numeric(contribution).to_excel(writer, sheet_name="ExternalContributions", index=False)
        _round_numeric(net_impacts).to_excel(writer, sheet_name="NetImpacts", index=False)
        _round_numeric(break_test).to_excel(writer, sheet_name="BreakTest", index=False)


def run_paper_replication_h_review(
    start_date: str | None = None,
    end_date: str | None = None,
    event_start_date: str | None = None,
    input_path: str | Path = MODEL_READY_PATH,
    allow_thesis_source: bool = True,
    use_thesis_vmd_cache: bool = False,
    target_variables: list[str] | None = None,
    candidate_variables: list[str] | None = None,
    vmd_k: int = 4,
) -> dict[str, pd.DataFrame]:
    """Run paper-method workflow through FEVD horizon h selection, then stop."""
    global _THESIS_VMD_ACTIVE
    _ensure_dirs()
    vmd_k = max(1, int(vmd_k))
    data = load_paper_replication_data(
        input_path=input_path,
        start_date=start_date,
        end_date=end_date,
        allow_thesis_source=allow_thesis_source,
    )
    if use_thesis_vmd_cache and vmd_k == 4:
        _maybe_enable_thesis_vmd(data)
    else:
        _THESIS_VMD_ACTIVE = False

    targets, candidate_pool = _resolve_analysis_variables(data, target_variables, candidate_variables)
    paper_variables = list(dict.fromkeys([*targets, *candidate_pool]))
    _plot_price_event(data, targets, event_start_date or start_date)
    _plot_vmd_decomposition_figures(data, paper_variables, vmd_k, start_date=event_start_date or start_date, end_date=end_date)
    _plot_hht_imf1_frequency(data, targets, vmd_k, event_start_date or start_date, end_date=end_date)
    all_mrgc = []
    all_stats = []
    all_effects = []
    all_selected_scale_granger = []
    selected_series_frames = []
    selected_scale_plot_items = []
    h_review_rows = []

    for target in targets:
        target_data = data.dropna(subset=[target]).reset_index(drop=True)
        if len(target_data) < 40:
            warnings.warn(f"Target {target} has too few non-missing observations and was skipped.")
            continue
        candidates = [
            candidate
            for candidate in candidate_pool
            if candidate in target_data.columns
            and candidate != target
            and pd.to_numeric(target_data[candidate], errors="coerce").notna().any()
        ]
        if not candidates:
            warnings.warn(f"No explanatory variables remain after excluding target {target}; target is skipped.")
            continue
        if candidate_variables is None and "GPRD" not in candidates and "GPRD" in data.columns and target != "GPRD":
            candidates.insert(0, "GPRD")

        mrgc, _ = _run_mrgc_for_target(target_data, target, candidates, vmd_k=vmd_k)
        stats, scale_df = _target_scale_statistics(
            target_data,
            target,
            mrgc,
            event_start_date=event_start_date or start_date,
            vmd_k=vmd_k,
        )
        selected_levels = str(scale_df["SelectedScale"].iloc[0]).split("+")
        selected_granger, _ = _selected_scale_granger(
            data=target_data,
            target=target,
            selected_levels=selected_levels,
            candidate_variables=candidates,
            vmd_k=vmd_k,
        )
        effect = _selected_scale_extreme_effect(
            scale_df,
            target,
            event_start_date=event_start_date or start_date,
        )

        all_mrgc.append(mrgc)
        all_stats.append(stats)
        all_effects.append(pd.DataFrame([effect]))
        all_selected_scale_granger.append(selected_granger)
        selected_series_frames.append(scale_df)
        selected_scale_plot_items.append((target, scale_df, effect))
        h_review_rows.append(
            {
                "Target": effect["Target"],
                "SelectedScale": effect["SelectedScale"],
                "EventStartDate": effect["EventStartDate"],
                "SelectedScaleMinimumDate": effect["MinimumDate"],
                "SelectedScaleMinimumValue": effect["MinimumValue"],
                "SelectedScaleMaximumDate": effect["MaximumDate"],
                "SelectedScaleMaximumValue": effect["MaximumValue"],
                "TradingDayInterval": effect["TradingDayInterval"],
                "CalendarDayInterval": effect["CalendarDayInterval"],
                "FEVD_h": effect["FEVD_h"],
                "OriginalMinDate": effect["OriginalMinDate"],
                "OriginalMaxDate": effect["OriginalMaxDate"],
                "Status": "Ready",
                "NextStep": "Pending manual confirmation before TVP/VAR FEVD",
                "Note": effect["Note"],
            }
        )

    if not all_mrgc:
        raise ValueError("FEVD h review produced no target results. Check target and explanatory variable selections.")

    mrgc_df = pd.concat(all_mrgc, ignore_index=True)
    stats_df = pd.concat(all_stats, ignore_index=True)
    effect_df = pd.concat(all_effects, ignore_index=True)
    selected_granger_df = pd.concat(all_selected_scale_granger, ignore_index=True)
    selected_series = pd.concat(selected_series_frames, ignore_index=True)
    h_review_df = pd.DataFrame(h_review_rows)

    _plot_selected_scale_panel(selected_scale_plot_items)
    _plot_scale_statistics(stats_df)
    _plot_mrgc_heatmap(mrgc_df)

    _round_numeric(h_review_df).to_excel(OUTPUT_PATHS["h_review"], index=False)
    _round_numeric(mrgc_df).to_excel(OUTPUT_PATHS["mrgc"], index=False)
    _round_numeric(stats_df).to_excel(OUTPUT_PATHS["scale_statistics"], index=False)
    _round_numeric(effect_df).to_excel(OUTPUT_PATHS["selected_scale_effect"], index=False)
    _round_numeric(selected_granger_df).to_excel(OUTPUT_PATHS["selected_scale_granger"], index=False)
    _round_numeric(selected_series).to_excel(OUTPUT_PATHS["selected_scale_series"], index=False)

    return {
        "h_review": h_review_df,
        "mrgc": mrgc_df,
        "scale_statistics": stats_df,
        "selected_scale_effect": effect_df,
        "selected_scale_granger": selected_granger_df,
        "selected_scale_series": selected_series,
    }


def run_paper_replication_pipeline(
    start_date: str | None = None,
    end_date: str | None = None,
    event_start_date: str | None = None,
    input_path: str | Path = MODEL_READY_PATH,
    allow_thesis_source: bool = False,
    use_thesis_vmd_cache: bool = False,
    target_variables: list[str] | None = None,
    candidate_variables: list[str] | None = None,
    vmd_k: int = 4,
) -> dict[str, pd.DataFrame]:
    """Run the paper-method replication workflow and save tables/figures."""
    global _THESIS_VMD_ACTIVE
    _ensure_dirs()
    vmd_k = max(1, int(vmd_k))
    data = load_paper_replication_data(
        input_path=input_path,
        start_date=start_date,
        end_date=end_date,
        allow_thesis_source=allow_thesis_source,
    )
    if use_thesis_vmd_cache and vmd_k == 4:
        _maybe_enable_thesis_vmd(data)
    else:
        _THESIS_VMD_ACTIVE = False
    targets, candidate_pool = _resolve_analysis_variables(data, target_variables, candidate_variables)
    paper_variables = list(dict.fromkeys([*targets, *candidate_pool]))
    _plot_price_event(data, targets, event_start_date or start_date)
    _plot_vmd_decomposition_figures(data, paper_variables, vmd_k, start_date=event_start_date or start_date, end_date=end_date)
    _plot_hht_imf1_frequency(data, targets, vmd_k, event_start_date or start_date, end_date=end_date)

    all_mrgc = []
    all_stats = []
    all_effects = []
    all_selected_scale_granger = []
    all_settings = []
    all_contributions = []
    all_net_impacts = []
    all_breaks = []
    all_optimal_break_profiles = []
    selected_series_frames = []
    selected_scale_plot_items = []
    break_fit_items = []

    for target in targets:
        target_data = data.dropna(subset=[target]).reset_index(drop=True)
        if len(target_data) < 40:
            warnings.warn(f"Target {target} has too few non-missing observations and was skipped.")
            continue
        candidates = [
            candidate
            for candidate in candidate_pool
            if candidate in target_data.columns and candidate != target and pd.to_numeric(target_data[candidate], errors="coerce").notna().any()
        ]
        if not candidates:
            warnings.warn(f"No explanatory variables remain after excluding target {target}; target is skipped.")
            continue
        if candidate_variables is None and "GPRD" not in candidates and "GPRD" in data.columns and target != "GPRD":
            candidates.insert(0, "GPRD")
        mrgc, _ = _run_mrgc_for_target(target_data, target, candidates, vmd_k=vmd_k)
        stats, scale_df = _target_scale_statistics(
            target_data,
            target,
            mrgc,
            event_start_date=event_start_date or start_date,
            vmd_k=vmd_k,
        )
        selected_levels = str(scale_df["SelectedScale"].iloc[0]).split("+")
        selected_granger, selected_drivers = _selected_scale_granger(
            data=target_data,
            target=target,
            selected_levels=selected_levels,
            candidate_variables=candidates,
            vmd_k=vmd_k,
        )
        effect = _selected_scale_extreme_effect(
            scale_df,
            target,
            event_start_date=event_start_date or start_date,
        )
        settings, contribution, net_impacts, var_data = _contribution_decomposition(
            data=target_data,
            target=target,
            effect=effect,
            selected_scale_drivers=selected_drivers,
            candidate_variables=candidates,
            vmd_k=vmd_k,
        )
        break_summary, break_fit = _structural_break_test(scale_df, target, effect)
        optimal_profile = _optimal_break_rss_profile(scale_df, target, effect)

        all_mrgc.append(mrgc)
        all_stats.append(stats)
        all_effects.append(pd.DataFrame([effect]))
        all_selected_scale_granger.append(selected_granger)
        all_settings.append(settings)
        all_contributions.append(contribution)
        all_net_impacts.append(net_impacts)
        all_breaks.append(break_summary)
        if not optimal_profile.empty:
            all_optimal_break_profiles.append(optimal_profile)
        selected_series_frames.append(scale_df)
        selected_scale_plot_items.append((target, scale_df, effect))
        break_fit_items.append((target, break_fit, break_summary))

    if not all_mrgc:
        raise ValueError("Paper-method replication produced no target results. Check target and explanatory variable selections.")

    mrgc_df = pd.concat(all_mrgc, ignore_index=True)
    stats_df = pd.concat(all_stats, ignore_index=True)
    effect_df = pd.concat(all_effects, ignore_index=True)
    selected_granger_df = pd.concat(all_selected_scale_granger, ignore_index=True)
    settings_df = pd.concat(all_settings, ignore_index=True)
    contribution_df = pd.concat(all_contributions, ignore_index=True)
    net_impacts_df = pd.concat(all_net_impacts, ignore_index=True)
    break_df = pd.concat(all_breaks, ignore_index=True)
    optimal_break_df = (
        pd.concat(all_optimal_break_profiles, ignore_index=True)
        if all_optimal_break_profiles
        else pd.DataFrame()
    )
    selected_series = pd.concat(selected_series_frames, ignore_index=True)
    h_review_df = pd.DataFrame(
        [
            {
                "Target": row.get("Target"),
                "SelectedScale": row.get("SelectedScale"),
                "EventStartDate": row.get("EventStartDate"),
                "SelectedScaleMinimumDate": row.get("MinimumDate"),
                "SelectedScaleMinimumValue": row.get("MinimumValue"),
                "SelectedScaleMaximumDate": row.get("MaximumDate"),
                "SelectedScaleMaximumValue": row.get("MaximumValue"),
                "TradingDayInterval": row.get("TradingDayInterval"),
                "CalendarDayInterval": row.get("CalendarDayInterval"),
                "FEVD_h": row.get("FEVD_h"),
                "OriginalMinDate": row.get("OriginalMinDate"),
                "OriginalMaxDate": row.get("OriginalMaxDate"),
                "Status": "Confirmed",
                "NextStep": "TVP/VAR FEVD completed",
                "Note": row.get("Note"),
            }
            for _, row in effect_df.iterrows()
        ]
    )

    _plot_selected_scale_panel(selected_scale_plot_items)
    _plot_scale_statistics(stats_df)
    _plot_mrgc_heatmap(mrgc_df)
    _plot_contributions(contribution_df)
    _plot_net_impacts(net_impacts_df)
    _plot_break_fit_panel(break_fit_items)
    _plot_optimal_break_rss_profiles(optimal_break_df)

    summary = pd.DataFrame(
        [
            {
                "Item": "Method",
                "Value": "EMTV-NEI paper replication: VMD + MRGC + core scale + rolling VAR FEVD",
            },
            {"Item": "DataStartDate", "Value": _format_date(data["Date"].min())},
            {"Item": "DataEndDate", "Value": _format_date(data["Date"].max())},
            {"Item": "Targets", "Value": ", ".join(targets)},
            {"Item": "CandidateVariables", "Value": ", ".join(candidate_pool)},
            {"Item": "EventStartDate", "Value": _format_date(event_start_date or start_date)},
            {"Item": "VMD K", "Value": vmd_k},
            {"Item": "VMD penalty factor", "Value": 1000},
            {"Item": "VMD source", "Value": _vmd_source_note()},
            {"Item": "MRGC lag selection", "Value": "BIC"},
            {"Item": "MRGC max lag", "Value": 5},
            {"Item": "Main scale rule", "Value": _scale_rule_text(vmd_k)},
            {"Item": "FEVD h rule", "Value": "Trading-day interval between event-window selected-scale minimum and maximum dates"},
            {
                "Item": "VAR lag rule",
                "Value": "Selected by BIC within lags 1 to 5 for the current sample",
            },
            {"Item": "Rolling window", "Value": 120},
        ]
    )

    _round_numeric(summary).to_excel(OUTPUT_PATHS["summary"], index=False)
    _round_numeric(mrgc_df).to_excel(OUTPUT_PATHS["mrgc"], index=False)
    _round_numeric(stats_df).to_excel(OUTPUT_PATHS["scale_statistics"], index=False)
    _round_numeric(effect_df).to_excel(OUTPUT_PATHS["selected_scale_effect"], index=False)
    _round_numeric(h_review_df).to_excel(OUTPUT_PATHS["h_review"], index=False)
    _round_numeric(selected_granger_df).to_excel(OUTPUT_PATHS["selected_scale_granger"], index=False)
    _round_numeric(settings_df).to_excel(OUTPUT_PATHS["tvp_settings"], index=False)
    _round_numeric(contribution_df).to_excel(OUTPUT_PATHS["contribution_weights"], index=False)
    _round_numeric(net_impacts_df).to_excel(OUTPUT_PATHS["net_impacts"], index=False)
    _round_numeric(break_df).to_excel(OUTPUT_PATHS["break_test"], index=False)
    _round_numeric(optimal_break_df).to_excel(OUTPUT_PATHS["optimal_break_rss"], index=False)
    _round_numeric(selected_series).to_excel(OUTPUT_PATHS["selected_scale_series"], index=False)
    _save_dashboard(
        summary,
        mrgc_df,
        stats_df,
        effect_df,
        selected_granger_df,
        settings_df,
        contribution_df,
        net_impacts_df,
        break_df,
    )

    return {
        "summary": summary,
        "mrgc": mrgc_df,
        "scale_statistics": stats_df,
        "selected_scale_effect": effect_df,
        "h_review": h_review_df,
        "selected_scale_granger": selected_granger_df,
        "tvp_settings": settings_df,
        "contribution_weights": contribution_df,
        "net_impacts": net_impacts_df,
        "break_test": break_df,
        "optimal_break_rss": optimal_break_df,
        "selected_scale_series": selected_series,
    }
