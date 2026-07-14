"""MRGC and Granger-causality screening for WTI candidate variables.

MRGC here follows the paper-facing screening idea used by the dashboard:
candidate variables are checked against WTI at the original scale and at
VMD-derived IMF scales. Lag order is selected by BIC within lags 1 to 5.
The functions are intentionally defensive because expanded variables are
optional and should never break the main WTI freshness protection.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
import warnings

import numpy as np
import pandas as pd

from src.vmd_module import run_vmd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TABLES_DIR = PROJECT_ROOT / "outputs" / "tables"

MRGC_LATEST_PATH = TABLES_DIR / "mrgc_feature_screening_latest.xlsx"
MRGC_ROLLING_PATH = TABLES_DIR / "mrgc_feature_screening_by_rolling_window.xlsx"
MRGC_SUMMARY_PATH = TABLES_DIR / "mrgc_selected_variables_summary.xlsx"

MRGC_LEVELS = ["Original", "IMF1", "IMF2", "IMF3", "IMF4"]
_VMD_DECOMPOSITION_CACHE: dict[tuple[int, int, int], np.ndarray] = {}


def mrgc_levels(K: int) -> list[str]:
    """Return original plus K IMF levels."""
    K = max(1, int(K))
    return ["Original", *[f"IMF{idx}" for idx in range(1, K + 1)]]


def _series_cache_key(series: pd.Series, K: int) -> tuple[int, int, int]:
    """Build a compact cache key for repeated VMD decompositions."""
    numeric = pd.to_numeric(series, errors="coerce").reset_index(drop=True).round(8)
    value_hash = int(pd.util.hash_pandas_object(numeric, index=False).sum())
    return int(K), len(numeric), value_hash


def _p_value_from_f_stat(f_statistic: float, df_num: int, df_den: int) -> float:
    """Return the right-tail p-value for an F statistic when SciPy is available."""
    if not np.isfinite(f_statistic) or df_num <= 0 or df_den <= 0:
        return np.nan
    try:
        from scipy.stats import f as f_dist  # type: ignore

        return float(f_dist.sf(f_statistic, df_num, df_den))
    except Exception:  # noqa: BLE001 - p-values are diagnostic, not pipeline critical.
        warnings.warn("SciPy is unavailable; MRGC p-values are reported as NaN.")
        return np.nan


def significance_stars(p_value: float) -> str:
    """Return paper-style significance stars for a p-value."""
    if not np.isfinite(p_value):
        return ""
    if p_value < 0.01:
        return "***"
    if p_value < 0.05:
        return "**"
    if p_value < 0.10:
        return "*"
    return ""


def _ols_rss(y: np.ndarray, x: np.ndarray) -> float:
    """Compute OLS residual sum of squares using least squares."""
    beta, *_ = np.linalg.lstsq(x, y, rcond=None)
    residuals = y - x @ beta
    return float(np.sum(residuals**2))


def _lagged_design(y: pd.Series, x: pd.Series, lag: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Build restricted and unrestricted Granger designs for one lag order."""
    frame = pd.DataFrame({"y": y, "x": x}).apply(pd.to_numeric, errors="coerce")
    for idx in range(1, lag + 1):
        frame[f"y_lag{idx}"] = frame["y"].shift(idx)
        frame[f"x_lag{idx}"] = frame["x"].shift(idx)
    frame = frame.dropna()
    if len(frame) <= 2 * lag + 2:
        raise ValueError("Too few complete rows for Granger regression.")

    y_array = frame["y"].to_numpy(dtype=float)
    restricted_columns = [f"y_lag{idx}" for idx in range(1, lag + 1)]
    unrestricted_columns = restricted_columns + [f"x_lag{idx}" for idx in range(1, lag + 1)]
    restricted_x = np.column_stack(
        [np.ones(len(frame)), frame[restricted_columns].to_numpy(dtype=float)]
    )
    unrestricted_x = np.column_stack(
        [np.ones(len(frame)), frame[unrestricted_columns].to_numpy(dtype=float)]
    )
    return y_array, restricted_x, unrestricted_x


def _system_var_bic(y: pd.Series, x: pd.Series, lag: int) -> tuple[float, int, float]:
    """Return MATLAB-paper-style bivariate system VAR BIC for lag selection."""
    frame = pd.DataFrame({"y": y, "x": x}).apply(pd.to_numeric, errors="coerce").dropna()
    if len(frame) <= lag + 3:
        raise ValueError("Too few complete rows for system VAR BIC.")

    y_values = frame["y"].to_numpy(dtype=float)
    x_values = frame["x"].to_numpy(dtype=float)
    y_system = np.column_stack([y_values[lag:], x_values[lag:]])
    n_obs = len(y_system)

    x_system_parts = [np.ones(n_obs)]
    for step in range(1, lag + 1):
        x_system_parts.append(y_values[lag - step : len(y_values) - step])
        x_system_parts.append(x_values[lag - step : len(x_values) - step])
    x_system = np.column_stack(x_system_parts)

    beta, *_ = np.linalg.lstsq(x_system, y_system, rcond=None)
    residuals = y_system - x_system @ beta
    sigma = residuals.T @ residuals / n_obs
    det_sigma = float(np.linalg.det(sigma))
    if det_sigma <= 0 or not np.isfinite(det_sigma):
        log_det_sigma = float(np.log(np.finfo(float).tiny))
    else:
        log_det_sigma = float(np.log(det_sigma))
    variable_count = 2
    total_params = variable_count * (variable_count * lag + 1)
    bic = log_det_sigma + np.log(n_obs) * total_params / n_obs
    return float(bic), int(n_obs), log_det_sigma


def granger_test_bic(
    target: pd.Series,
    candidate: pd.Series,
    max_lag: int = 5,
) -> dict[str, Any]:
    """Run bivariate Granger testing with MATLAB-paper-style BIC lag selection."""
    best_lag: int | None = None
    best_bic = np.inf
    best_bic_obs = 0
    max_lag = max(1, int(max_lag))
    for lag in range(1, max_lag + 1):
        try:
            bic, n_obs, _ = _system_var_bic(target, candidate, lag)
            if bic < best_bic:
                best_bic = bic
                best_lag = lag
                best_bic_obs = n_obs
        except Exception:
            continue

    if best_lag is None:
        return {
            "SelectedLagByBIC": np.nan,
            "FStatistic": np.nan,
            "PValue": np.nan,
            "BIC": np.nan,
            "Observations": 0,
        }

    try:
        y_array, restricted_x, unrestricted_x = _lagged_design(target, candidate, best_lag)
        rss_restricted = _ols_rss(y_array, restricted_x)
        rss_unrestricted = _ols_rss(y_array, unrestricted_x)
        n_obs = len(y_array)
        k_unrestricted = unrestricted_x.shape[1]
        df_num = best_lag
        df_den = n_obs - k_unrestricted
        if df_den <= 0 or rss_unrestricted <= 0:
            raise ValueError("Invalid degrees of freedom for Granger test.")
        f_statistic = ((rss_restricted - rss_unrestricted) / df_num) / (
            rss_unrestricted / df_den
        )
        f_statistic = max(float(f_statistic), 0.0)
        p_value = _p_value_from_f_stat(f_statistic, df_num, df_den)
    except Exception:
        f_statistic = np.nan
        p_value = np.nan

    return {
        "SelectedLagByBIC": best_lag,
        "FStatistic": f_statistic,
        "PValue": p_value,
        "BIC": float(best_bic),
        "Observations": int(best_bic_obs),
    }


def _decompose_or_nan(series: pd.Series, K: int = 4) -> pd.DataFrame:
    """Return VMD IMFs for a complete numeric series, preserving VMD output order."""
    values = pd.to_numeric(series, errors="coerce").to_numpy(dtype=float)
    if np.isnan(values).any() or len(values) <= K + 5 or np.nanstd(values) <= 1e-12:
        return pd.DataFrame(index=series.index)
    cache_key = _series_cache_key(series, K)
    if cache_key in _VMD_DECOMPOSITION_CACHE:
        imfs = _VMD_DECOMPOSITION_CACHE[cache_key]
    else:
        # Keep MRGC labels compatible with the thesis MATLAB vmd output:
        # MATLAB IMF1 is high-frequency and higher IMF numbers are lower-frequency. vmdpy with
        # init=0 returns the comparable components in the opposite column order.
        imfs = run_vmd(values, K=K, alpha=1000, tau=0, DC=0, init=0, tol=1e-7)[:, ::-1]
        if len(_VMD_DECOMPOSITION_CACHE) > 512:
            _VMD_DECOMPOSITION_CACHE.pop(next(iter(_VMD_DECOMPOSITION_CACHE)))
        _VMD_DECOMPOSITION_CACHE[cache_key] = imfs
    return pd.DataFrame(
        imfs,
        index=series.index,
        columns=[f"IMF{idx}" for idx in range(1, K + 1)],
    )


def run_mrgc_screening(
    data: pd.DataFrame,
    target_col: str = "WTI",
    candidate_variables: list[str] | None = None,
    max_lag: int = 5,
    lag_selection: str = "bic",
    K: int = 4,
    p_threshold: float = 0.10,
    target_label: str = "WTI",
    window_number: int | None = None,
    save_outputs: bool = False,
) -> tuple[pd.DataFrame, list[str]]:
    """Screen candidate variables with MRGC and return retained variables.

    Only rows in ``data`` are used. In rolling backtests this function must be
    called with the current training window, so no future information enters
    the screening decision.
    """
    if lag_selection.lower() != "bic":
        warnings.warn("MRGC currently uses BIC lag selection; overriding requested criterion.")
    if target_col not in data.columns:
        raise ValueError(f"MRGC target column is missing: {target_col}")

    prepared = data.copy()
    prepared["Date"] = pd.to_datetime(prepared["Date"], errors="coerce") if "Date" in prepared else pd.NaT
    candidate_variables = candidate_variables or [
        column for column in prepared.columns if column not in {"Date", target_col}
    ]
    candidate_variables = [
        column
        for column in candidate_variables
        if column in prepared.columns and pd.to_numeric(prepared[column], errors="coerce").notna().any()
    ]

    rows: list[dict[str, Any]] = []
    retained: set[str] = set()

    for candidate in candidate_variables:
        pair = prepared[["Date", target_col, candidate]].copy()
        pair[target_col] = pd.to_numeric(pair[target_col], errors="coerce")
        pair[candidate] = pd.to_numeric(pair[candidate], errors="coerce")
        pair = pair.dropna(subset=[target_col, candidate]).reset_index(drop=True)
        if len(pair) <= max_lag + K + 8 or pair[candidate].std() <= 1e-12:
            rows.append(
                {
                    "WindowNumber": window_number,
                    "Target": target_label,
                    "CandidateVariable": candidate,
                    "Level": "Original",
                    "VMD_K": K,
                    "SelectedLagByBIC": np.nan,
                    "FStatistic": np.nan,
                    "FStatisticWithStars": "",
                    "PValue": np.nan,
                    "SignificanceStars": "",
                    "Retained": False,
                    "Action": "Dropped",
                    "Note": "Too few observations or near-zero variance.",
                    "LagSelectionCriterion": "BIC",
                    "MaxLag": max_lag,
                }
            )
            continue

        level_series: dict[str, tuple[pd.Series, pd.Series]] = {
            "Original": (pair[target_col], pair[candidate])
        }
        try:
            pair_target_imfs = _decompose_or_nan(pair[target_col], K=K)
            pair_candidate_imfs = _decompose_or_nan(pair[candidate], K=K)
            for idx in range(1, K + 1):
                level = f"IMF{idx}"
                if level in pair_target_imfs.columns and level in pair_candidate_imfs.columns:
                    level_series[level] = (pair_target_imfs[level], pair_candidate_imfs[level])
        except Exception as exc:  # noqa: BLE001 - original-level screening still remains valid.
            warnings.warn(f"VMD decomposition failed during MRGC for {candidate}: {exc}")

        candidate_retained = False
        for level in mrgc_levels(K):
            if level not in level_series:
                continue
            target_series, candidate_series = level_series[level]
            result = granger_test_bic(target_series, candidate_series, max_lag=max_lag)
            p_value = float(result["PValue"]) if pd.notna(result["PValue"]) else np.nan
            stars = significance_stars(p_value)
            is_retained = bool(np.isfinite(p_value) and p_value < p_threshold)
            candidate_retained = candidate_retained or is_retained
            rows.append(
                {
                    "WindowNumber": window_number,
                    "Target": target_label,
                    "CandidateVariable": candidate,
                    "Level": level,
                    "VMD_K": K,
                    "SelectedLagByBIC": result["SelectedLagByBIC"],
                    "FStatistic": result["FStatistic"],
                    "FStatisticWithStars": (
                        f"{result['FStatistic']:.3f}{stars}"
                        if pd.notna(result["FStatistic"])
                        else ""
                    ),
                    "PValue": p_value,
                    "SignificanceStars": stars,
                    "Retained": is_retained,
                    "Action": "Retained" if is_retained else "Dropped",
                    "Note": "BIC lag selected within 1 to 5; VMD IMF order is unchanged.",
                    "LagSelectionCriterion": "BIC",
                    "MaxLag": max_lag,
                    "Observations": result["Observations"],
                }
            )

        if candidate_retained:
            retained.add(candidate)

    screening = pd.DataFrame(rows)
    retained_variables = sorted(retained)
    if save_outputs:
        save_mrgc_outputs(screening, retained_variables, window_number=window_number)
    return screening, retained_variables


def save_mrgc_outputs(
    screening_df: pd.DataFrame,
    retained_variables: list[str],
    window_number: int | None = None,
) -> None:
    """Save MRGC latest, rolling-window, and summary workbooks."""
    TABLES_DIR.mkdir(parents=True, exist_ok=True)
    if window_number is None:
        screening_df.to_excel(MRGC_LATEST_PATH, index=False)
    else:
        rolling = screening_df.copy()
        if MRGC_ROLLING_PATH.exists() and not rolling.empty:
            existing = pd.read_excel(MRGC_ROLLING_PATH)
            rolling = pd.concat([existing, rolling], ignore_index=True).drop_duplicates()
        rolling.to_excel(MRGC_ROLLING_PATH, index=False)

    summary_rows = []
    source = screening_df.copy()
    if not source.empty and "CandidateVariable" in source.columns:
        grouped = source.groupby("CandidateVariable", dropna=False)
        for variable, group in grouped:
            retained_series = (
                group["Retained"].fillna(False)
                if "Retained" in group.columns
                else pd.Series([False])
            )
            retained = bool(retained_series.any())
            best_p = pd.to_numeric(group.get("PValue"), errors="coerce").min()
            significant_levels = ", ".join(
                group.loc[retained_series.reindex(group.index, fill_value=False), "Level"]
                .astype(str)
                .unique()
            )
            summary_rows.append(
                {
                    "Variable": variable,
                    "RetainedByMRGC": retained,
                    "BestPValue": best_p,
                    "SignificantLevels": significant_levels or "None",
                    "SelectionRule": "BIC, max lag = 5",
                }
            )
    summary = pd.DataFrame(summary_rows)
    if not summary.empty:
        summary = summary.sort_values(["RetainedByMRGC", "BestPValue"], ascending=[False, True])
    summary.to_excel(MRGC_SUMMARY_PATH, index=False)
