"""Automatic candidate-variable screening and feature selection utilities.

The dashboard now enables automatic feature selection by default. Legacy
callers can still pass ``enable_feature_selection=False`` in training or
backtest functions when debugging old baselines.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
import warnings

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.linear_model import ElasticNetCV, LassoCV

from src.mrgc_selector import run_mrgc_screening, save_mrgc_outputs


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TABLES_DIR = PROJECT_ROOT / "outputs" / "tables"
FIGURES_DIR = PROJECT_ROOT / "outputs" / "figures"
UPLOAD_DIR = PROJECT_ROOT / "data" / "raw" / "uploads"
MODEL_READY_PATH = PROJECT_ROOT / "data" / "processed" / "model_ready_data.xlsx"

CANDIDATE_VARIABLE_POOL = [
    "GPRD",
    "OVX",
    "DollarIndex",
    "TNote10Y",
    "Gold",
    "Brent",
    "VIX",
    "SP500",
    "Nasdaq",
    "NaturalGas",
    "Gasoline",
    "HeatingOil",
    "Copper",
    "Silver",
    "US2Y",
    "FedFunds",
    "CNYUSD",
    "ShanghaiSC",
    "ShanghaiFU",
    "EPU",
]

OUTPUT_PATHS = {
    "selected_latest": TABLES_DIR / "selected_features_latest.xlsx",
    "selected_by_imf": TABLES_DIR / "selected_features_by_imf.xlsx",
    "selected_by_window": TABLES_DIR / "selected_features_by_rolling_window.xlsx",
    "summary": TABLES_DIR / "feature_selection_summary.xlsx",
    "importance": TABLES_DIR / "feature_importance_summary.xlsx",
    "mrgc_latest": TABLES_DIR / "mrgc_feature_screening_latest.xlsx",
    "mrgc_by_window": TABLES_DIR / "mrgc_feature_screening_by_rolling_window.xlsx",
    "mrgc_summary": TABLES_DIR / "mrgc_selected_variables_summary.xlsx",
    "frequency_png": FIGURES_DIR / "feature_selection_frequency.png",
    "importance_png": FIGURES_DIR / "top_feature_importance.png",
}

_MRGC_RESULT_CACHE: dict[tuple[Any, ...], tuple[pd.DataFrame, list[str]]] = {}
_MRGC_SCREENING_OUTPUT_BUFFER: list[pd.DataFrame] = []


def _resolve_project_path(path: str | Path) -> Path:
    """Resolve a relative path against the project root."""
    path = Path(path)
    if path.is_absolute():
        return path
    return PROJECT_ROOT / path


def ensure_output_dirs() -> None:
    """Create feature-selection output directories."""
    TABLES_DIR.mkdir(parents=True, exist_ok=True)
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def canonical_variable_name(name: str) -> str:
    """Normalize a variable name into a stable column identifier."""
    normalized = str(name).strip().replace(" ", "_").replace("-", "_")
    aliases = {
        "S&P500": "SP500",
        "S_and_P_500": "SP500",
        "S_P_500": "SP500",
        "US_2Y": "US2Y",
        "Fed_Funds": "FedFunds",
    }
    return aliases.get(normalized, normalized)


def detect_date_column(columns: list[str]) -> str | None:
    """Detect a Date/date/date-like column, including Chinese date labels."""
    lowered = {str(column).strip().lower(): column for column in columns}
    for key in ["date", "datetime", "time", "timestamp"]:
        if key in lowered:
            return str(lowered[key])
    for column in columns:
        text = str(column).strip().lower()
        if "date" in text or "time" in text or "\u65e5\u671f" in text:
            return str(column)
    return None


def load_local_variable_file(file_path: str | Path) -> pd.DataFrame:
    """Load one uploaded CSV/XLSX variable file and standardize Date + variables.

    The file can contain one or more variable columns. Date/date/time-style
    columns are recognized automatically. Non-date columns are treated as
    candidate explanatory variables.
    """
    path = _resolve_project_path(file_path)
    suffix = path.suffix.lower()
    if suffix == ".csv":
        data = pd.read_csv(path)
    elif suffix in {".xlsx", ".xls"}:
        data = pd.read_excel(path)
    else:
        raise ValueError(f"Unsupported upload file type: {path.suffix}")

    if data.empty:
        raise ValueError(f"Uploaded variable file is empty: {path}")

    date_col = detect_date_column(data.columns.astype(str).tolist())
    if date_col is None:
        raise ValueError(f"Could not identify a date column in {path.name}.")

    result = data.copy()
    result = result.rename(columns={date_col: "Date"})
    result["Date"] = pd.to_datetime(result["Date"], errors="coerce")
    result = result.dropna(subset=["Date"])
    result = result.drop_duplicates(subset=["Date"], keep="last")
    result = result.sort_values("Date").reset_index(drop=True)

    variable_columns = [column for column in result.columns if column != "Date"]
    rename_map = {column: canonical_variable_name(column) for column in variable_columns}
    result = result.rename(columns=rename_map)
    for column in result.columns:
        if column != "Date":
            result[column] = pd.to_numeric(result[column], errors="coerce")
    return result


def load_uploaded_variable_pool(upload_dir: str | Path = UPLOAD_DIR) -> pd.DataFrame:
    """Load and merge all uploaded local variable files."""
    upload_dir = _resolve_project_path(upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)
    files = [
        path
        for path in upload_dir.iterdir()
        if path.is_file() and path.suffix.lower() in {".csv", ".xlsx", ".xls"}
    ]
    merged: pd.DataFrame | None = None
    for path in files:
        try:
            data = load_local_variable_file(path)
        except Exception as exc:  # noqa: BLE001 - keep other uploads usable.
            warnings.warn(f"Skipping uploaded variable file {path.name}: {exc}")
            continue
        merged = data if merged is None else merged.merge(data, on="Date", how="outer")

    if merged is None:
        return pd.DataFrame(columns=["Date"])
    merged = merged.sort_values("Date").reset_index(drop=True)
    return merged


def merge_uploaded_variables_into_model_ready(
    model_ready_path: str | Path = MODEL_READY_PATH,
    upload_dir: str | Path = UPLOAD_DIR,
    output_path: str | Path | None = None,
    prefer_uploaded: bool = True,
) -> pd.DataFrame:
    """Merge uploaded explanatory variables into model_ready_data.xlsx.

    Uploaded values can override existing explanatory-variable values when
    ``prefer_uploaded`` is True. The merged output is strict complete-case:
    any date with a missing value in any retained data column is removed.
    """
    model_ready_path = _resolve_project_path(model_ready_path)
    if output_path is None:
        output_path = model_ready_path
    output_path = _resolve_project_path(output_path)
    if not model_ready_path.exists():
        raise FileNotFoundError(f"Model-ready data file not found: {model_ready_path}")

    base = pd.read_excel(model_ready_path)
    if "Date" not in base.columns or "WTI" not in base.columns:
        raise ValueError("model_ready_data.xlsx must contain Date and WTI.")
    base = base.copy()
    base["Date"] = pd.to_datetime(base["Date"], errors="coerce")
    base = base.dropna(subset=["Date"])

    uploads = load_uploaded_variable_pool(upload_dir)
    if uploads.empty or len(uploads.columns) <= 1:
        return base

    merged = base.merge(uploads, on="Date", how="left", suffixes=("", "_uploaded"))
    for column in uploads.columns:
        if column == "Date":
            continue
        uploaded_column = f"{column}_uploaded"
        if uploaded_column in merged.columns:
            if prefer_uploaded:
                merged[column] = merged[uploaded_column]
            else:
                merged[column] = merged.get(column).combine_first(merged[uploaded_column])
            merged = merged.drop(columns=[uploaded_column])
    merged = merged.sort_values("Date").reset_index(drop=True)
    strict_columns = [column for column in merged.columns if column != "Date"]
    if strict_columns:
        merged = merged.dropna(subset=strict_columns).reset_index(drop=True)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    merged.to_excel(output_path, index=False)
    return merged


def identify_candidate_variables(
    data: pd.DataFrame,
    target_col: str = "WTI",
    candidate_pool: list[str] | None = None,
) -> list[str]:
    """Identify usable candidate variables from a DataFrame."""
    candidate_pool = candidate_pool or CANDIDATE_VARIABLE_POOL
    excluded = {"Date", target_col, "Delta_WTI", "LogReturn_WTI"}
    pool_set = {canonical_variable_name(name) for name in candidate_pool}
    candidates = []
    for column in data.columns:
        canonical = canonical_variable_name(column)
        if column in excluded or canonical in excluded:
            continue
        if canonical in pool_set or column not in excluded:
            if data[column].notna().any():
                candidates.append(column)
    return candidates


def quality_filter_variables(
    data: pd.DataFrame,
    candidate_vars: list[str],
    end_date: str | pd.Timestamp | None = None,
    min_coverage: float = 0.6,
    max_missing_rate: float | None = None,
    max_stale_days: int = 14,
    min_variance: float = 1e-10,
) -> tuple[list[str], pd.DataFrame]:
    """Filter candidate variables by coverage, freshness, and variance."""
    if "Date" not in data.columns:
        raise ValueError("Data must contain Date for feature quality screening.")

    prepared = data.copy()
    prepared["Date"] = pd.to_datetime(prepared["Date"], errors="coerce")
    prepared = prepared.dropna(subset=["Date"])
    if max_missing_rate is None:
        max_missing_rate = 1 - min_coverage
    if end_date is None:
        end_timestamp = prepared["Date"].max()
    else:
        end_timestamp = pd.to_datetime(end_date)

    rows: list[dict[str, Any]] = []
    kept: list[str] = []
    for variable in candidate_vars:
        if variable not in prepared.columns:
            rows.append(
                {
                    "Variable": variable,
                    "Coverage": 0.0,
                    "MissingRate": 1.0,
                    "LatestDate": pd.NaT,
                    "Variance": np.nan,
                    "Action": "Dropped_missing_column",
                    "Reason": "Variable column is not available.",
                }
            )
            continue

        series = pd.to_numeric(prepared[variable], errors="coerce")
        coverage = float(series.notna().mean()) if len(series) else 0.0
        missing_rate = 1 - coverage
        non_missing_rows = prepared.loc[series.notna(), ["Date"]].copy()
        latest_date = non_missing_rows["Date"].max() if not non_missing_rows.empty else pd.NaT
        variance = float(series.dropna().var(ddof=0)) if series.notna().sum() else np.nan
        reasons: list[str] = []
        if coverage < min_coverage or missing_rate > max_missing_rate:
            reasons.append("low_coverage")
        if pd.isna(latest_date) or end_timestamp - latest_date > pd.Timedelta(days=max_stale_days):
            reasons.append("stale_latest_date")
        if pd.isna(variance) or variance <= min_variance:
            reasons.append("near_zero_variance")
        action = "Kept" if not reasons else "Dropped_quality_filter"
        if action == "Kept":
            kept.append(variable)
        rows.append(
            {
                "Variable": variable,
                "Coverage": coverage,
                "MissingRate": missing_rate,
                "LatestDate": latest_date,
                "Variance": variance,
                "Action": action,
                "Reason": "; ".join(reasons) if reasons else "Passed quality filter.",
            }
        )
    return kept, pd.DataFrame(rows)


def base_variable_from_lag(feature_name: str) -> str:
    """Return the base variable name for a lag feature."""
    marker = "_lag"
    if marker not in feature_name:
        return feature_name
    return feature_name.rsplit(marker, 1)[0]


def _mrgc_cache_key(
    context_df: pd.DataFrame,
    target_col: str,
    candidate_variables: list[str],
    max_lag: int,
    lag_selection: str,
    window_number: int | None,
    vmd_k: int,
) -> tuple[Any, ...]:
    """Build a stable per-window MRGC cache key."""
    columns = [
        column
        for column in ["Date", target_col, *candidate_variables]
        if column in context_df.columns
    ]
    signature = context_df[columns].copy()
    for column in columns:
        if column == "Date":
            signature[column] = pd.to_datetime(signature[column], errors="coerce").astype("int64")
        else:
            signature[column] = pd.to_numeric(signature[column], errors="coerce")
    fingerprint = int(pd.util.hash_pandas_object(signature, index=False).sum())
    return (
        target_col,
        tuple(sorted(candidate_variables)),
        int(vmd_k),
        int(max_lag),
        lag_selection.lower().strip(),
        window_number,
        len(context_df),
        fingerprint,
    )


def _infer_vmd_k(context_df: pd.DataFrame) -> int:
    """Infer VMD K from available WTI IMF columns, falling back to 4."""
    imf_indices = []
    for column in context_df.columns:
        text = str(column)
        if text.startswith("WTI_IMF") and text.replace("WTI_IMF", "", 1).isdigit():
            imf_indices.append(int(text.replace("WTI_IMF", "", 1)))
    return max(imf_indices) if imf_indices else 4


def _record_mrgc_screening_output(
    screening_df: pd.DataFrame,
    retained_variables: list[str],
    window_number: int | None,
) -> None:
    """Save latest MRGC immediately and buffer rolling MRGC rows until the end."""
    if screening_df.empty:
        return
    if window_number is None:
        save_mrgc_outputs(screening_df, retained_variables, window_number=window_number)
        return
    _MRGC_SCREENING_OUTPUT_BUFFER.append(screening_df.copy())


def flush_mrgc_screening_output_buffer() -> None:
    """Write buffered rolling-window MRGC rows with one Excel operation."""
    if not _MRGC_SCREENING_OUTPUT_BUFFER:
        return
    combined = pd.concat(_MRGC_SCREENING_OUTPUT_BUFFER, ignore_index=True)
    _MRGC_SCREENING_OUTPUT_BUFFER.clear()
    save_mrgc_outputs(combined, [], window_number=-1)


def _select_by_elasticnet(
    clean: pd.DataFrame,
    y: pd.Series,
    max_selected_features: int,
    random_state: int,
    method_label: str = "elasticnet",
) -> tuple[list[str], pd.DataFrame]:
    """Select lag features with ElasticNetCV, falling back to LassoCV."""
    cv_folds = min(5, max(2, len(clean) // 10))
    try:
        model = ElasticNetCV(
            l1_ratio=[0.2, 0.5, 0.8, 1.0],
            cv=cv_folds,
            random_state=random_state,
            max_iter=10000,
        )
        model.fit(clean, y)
        coef = np.asarray(model.coef_, dtype=float)
    except Exception as exc:  # noqa: BLE001 - Lasso fallback keeps selector usable.
        warnings.warn(f"ElasticNetCV failed ({exc}); falling back to LassoCV.")
        model = LassoCV(cv=cv_folds, random_state=random_state, max_iter=10000)
        model.fit(clean, y)
        coef = np.asarray(model.coef_, dtype=float)

    importance = pd.DataFrame(
        {
            "Feature": clean.columns,
            "BaseVariable": [base_variable_from_lag(column) for column in clean.columns],
            "Score": np.abs(coef),
            "Method": method_label,
        }
    ).sort_values("Score", ascending=False)
    selected = importance.loc[importance["Score"] > 0, "Feature"].head(max_selected_features).tolist()
    if not selected:
        selected = importance["Feature"].head(min(max_selected_features, len(importance))).tolist()
    importance["Selected"] = importance["Feature"].isin(selected)
    return selected, importance.reset_index(drop=True)


def _select_by_correlation(
    clean: pd.DataFrame,
    y: pd.Series,
    max_selected_features: int,
    method_label: str = "correlation",
) -> tuple[list[str], pd.DataFrame]:
    """Select lag features by absolute training-set correlation."""
    scores = []
    for column in clean.columns:
        corr = clean[column].corr(y)
        score = abs(float(corr)) if pd.notna(corr) else 0.0
        scores.append(
            {
                "Feature": column,
                "BaseVariable": base_variable_from_lag(column),
                "Score": score,
                "Method": method_label,
            }
        )
    importance = pd.DataFrame(scores).sort_values("Score", ascending=False)
    selected = importance.loc[importance["Score"] > 0, "Feature"].head(max_selected_features).tolist()
    if not selected:
        selected = importance["Feature"].head(min(max_selected_features, len(importance))).tolist()
    importance["Selected"] = importance["Feature"].isin(selected)
    return selected, importance.reset_index(drop=True)


def select_features_from_training_data(
    x_train: pd.DataFrame,
    y_train: pd.Series,
    method: str = "correlation",
    max_selected_features: int = 20,
    random_state: int = 42,
    context_df: pd.DataFrame | None = None,
    target_col: str = "WTI",
    candidate_variables: list[str] | None = None,
    imf_name: str | None = None,
    window_number: int | None = None,
    max_lag: int = 5,
    lag_selection: str = "bic",
) -> tuple[list[str], pd.DataFrame]:
    """Select features using only the training matrix and target.

    ``mrgc`` and ``mrgc_then_elasticnet`` use ``context_df`` when available.
    Rolling-window callers pass the current training window, so MRGC/Granger
    screening does not see future observations.
    """
    if x_train.empty:
        raise ValueError("x_train is empty; cannot run feature selection.")
    if max_selected_features < 1:
        raise ValueError("max_selected_features must be at least 1.")

    clean = x_train.copy()
    clean = clean.apply(pd.to_numeric, errors="coerce")
    y = pd.to_numeric(y_train, errors="coerce")
    valid = clean.notna().all(axis=1) & y.notna()
    clean = clean.loc[valid]
    y = y.loc[valid]
    if clean.empty:
        raise ValueError("No complete rows are available for feature selection.")

    method = method.lower().strip()
    if method == "correlation":
        selected, importance = _select_by_correlation(clean, y, max_selected_features)
    elif method == "elasticnet":
        selected, importance = _select_by_elasticnet(
            clean,
            y,
            max_selected_features=max_selected_features,
            random_state=random_state,
        )
    elif method in {"mrgc", "mrgc_then_elasticnet"}:
        base_variables = sorted(
            {
                base_variable_from_lag(column)
                for column in clean.columns
                if "_lag" in column
            }
        )
        imf_base_variables = {
            variable for variable in base_variables if variable.startswith(("WTI_IMF", "Delta_IMF"))
        }
        candidate_variables = candidate_variables or [
            variable for variable in base_variables if variable not in imf_base_variables
        ]

        retained_variables: list[str] = []
        mrgc_screening = pd.DataFrame()
        if context_df is not None and candidate_variables:
            try:
                actual_target_col = target_col if target_col in context_df.columns else "WTI"
                vmd_k = _infer_vmd_k(context_df)
                cache_key = _mrgc_cache_key(
                    context_df=context_df,
                    target_col=actual_target_col,
                    candidate_variables=candidate_variables,
                    max_lag=max_lag,
                    lag_selection=lag_selection,
                    window_number=window_number,
                    vmd_k=vmd_k,
                )
                if cache_key in _MRGC_RESULT_CACHE:
                    cached_screening, cached_retained = _MRGC_RESULT_CACHE[cache_key]
                    mrgc_screening = cached_screening.copy()
                    retained_variables = list(cached_retained)
                else:
                    mrgc_screening, retained_variables = run_mrgc_screening(
                        data=context_df,
                        target_col=actual_target_col,
                        candidate_variables=candidate_variables,
                        max_lag=max_lag,
                        lag_selection=lag_selection,
                        K=vmd_k,
                        target_label=actual_target_col,
                        window_number=window_number,
                        save_outputs=False,
                    )
                    _MRGC_RESULT_CACHE[cache_key] = (
                        mrgc_screening.copy(),
                        list(retained_variables),
                    )
                    _record_mrgc_screening_output(
                        mrgc_screening,
                        retained_variables,
                        window_number=window_number,
                    )
            except Exception as exc:  # noqa: BLE001 - fallback keeps the analysis runnable.
                warnings.warn(f"MRGC screening failed ({exc}); falling back to default variable pool.")

        if not retained_variables:
            retained_variables = list(candidate_variables)
            warnings.warn(
                "MRGC retained no variables; falling back to the default quality-filtered "
                "candidate pool for this training window."
            )

        allowed_base_variables = set(retained_variables).union(imf_base_variables)
        restricted_columns = [
            column for column in clean.columns if base_variable_from_lag(column) in allowed_base_variables
        ]
        if not restricted_columns:
            restricted_columns = clean.columns.tolist()
        restricted = clean[restricted_columns]

        if method == "mrgc_then_elasticnet":
            selected, importance = _select_by_elasticnet(
                restricted,
                y,
                max_selected_features=max_selected_features,
                random_state=random_state,
                method_label="mrgc_then_elasticnet",
            )
        else:
            selected, importance = _select_by_correlation(
                restricted,
                y,
                max_selected_features=max_selected_features,
                method_label="mrgc",
            )
        if not mrgc_screening.empty:
            min_p = (
                mrgc_screening.groupby("CandidateVariable")["PValue"]
                .min()
                .rename("MRGCMinPValue")
                .reset_index()
            )
            importance = importance.merge(
                min_p,
                left_on="BaseVariable",
                right_on="CandidateVariable",
                how="left",
            ).drop(columns=["CandidateVariable"], errors="ignore")
        importance["LagSelectionCriterion"] = "BIC"
        importance["MaxLag"] = max_lag
    else:
        raise ValueError(
            "Feature selection method must be correlation, elasticnet, mrgc, "
            "or mrgc_then_elasticnet."
        )

    return selected, importance.reset_index(drop=True)


def save_selection_artifacts(
    latest_rows: list[dict[str, Any]] | None = None,
    by_imf_rows: list[dict[str, Any]] | None = None,
    rolling_rows: list[dict[str, Any]] | None = None,
    quality_report: pd.DataFrame | None = None,
    importance_rows: list[pd.DataFrame] | None = None,
    settings: dict[str, Any] | None = None,
) -> dict[str, Path]:
    """Save feature-selection logs and summary outputs."""
    ensure_output_dirs()
    flush_mrgc_screening_output_buffer()
    latest_df = pd.DataFrame(latest_rows or [])
    by_imf_df = pd.DataFrame(by_imf_rows or latest_rows or [])
    rolling_df = pd.DataFrame(rolling_rows or [])
    importance_df = (
        pd.concat(importance_rows, ignore_index=True)
        if importance_rows
        else pd.DataFrame(columns=["Feature", "BaseVariable", "Score", "Method", "Selected"])
    )

    if latest_rows is not None:
        latest_df.to_excel(OUTPUT_PATHS["selected_latest"], index=False)
    elif OUTPUT_PATHS["selected_latest"].exists():
        latest_df = pd.read_excel(OUTPUT_PATHS["selected_latest"])

    if by_imf_rows is not None or latest_rows is not None:
        by_imf_df.to_excel(OUTPUT_PATHS["selected_by_imf"], index=False)
    elif OUTPUT_PATHS["selected_by_imf"].exists():
        by_imf_df = pd.read_excel(OUTPUT_PATHS["selected_by_imf"])

    if rolling_rows is not None:
        if OUTPUT_PATHS["selected_by_window"].exists() and not rolling_df.empty:
            existing = pd.read_excel(OUTPUT_PATHS["selected_by_window"])
            rolling_df = pd.concat([existing, rolling_df], ignore_index=True)
            rolling_df = rolling_df.drop_duplicates()
        rolling_df.to_excel(OUTPUT_PATHS["selected_by_window"], index=False)
    elif OUTPUT_PATHS["selected_by_window"].exists():
        rolling_df = pd.read_excel(OUTPUT_PATHS["selected_by_window"])

    if importance_rows is not None:
        if OUTPUT_PATHS["importance"].exists() and not importance_df.empty:
            existing = pd.read_excel(OUTPUT_PATHS["importance"])
            importance_df = pd.concat([existing, importance_df], ignore_index=True)
            importance_df = importance_df.drop_duplicates()
        importance_df.to_excel(OUTPUT_PATHS["importance"], index=False)
    elif OUTPUT_PATHS["importance"].exists():
        importance_df = pd.read_excel(OUTPUT_PATHS["importance"])

    candidate_count = int(len(quality_report)) if quality_report is not None else 0
    passed_count = (
        int((quality_report["Action"] == "Kept").sum())
        if quality_report is not None and "Action" in quality_report.columns
        else 0
    )
    selected_variables = []
    for frame in [latest_df, rolling_df]:
        if "BaseVariable" in frame.columns:
            selected_variables.extend(frame["BaseVariable"].dropna().astype(str).tolist())
    frequency = pd.Series(selected_variables).value_counts().reset_index()
    if not frequency.empty:
        frequency.columns = ["Variable", "SelectionCount"]
    else:
        frequency = pd.DataFrame(columns=["Variable", "SelectionCount"])

    top_variable = frequency.iloc[0]["Variable"] if not frequency.empty else "None"
    settings = settings or {}
    summary_rows = [
        {"Item": "Automatic feature selection enabled", "Value": settings.get("enabled", False)},
        {"Item": "Selection method", "Value": settings.get("method", "not_enabled")},
        {"Item": "Lag selection criterion", "Value": settings.get("lag_selection", "BIC")},
        {"Item": "Maximum lag considered", "Value": settings.get("max_lag", 5)},
        {"Item": "Candidate variable count", "Value": candidate_count},
        {"Item": "Variables passing quality filter", "Value": passed_count},
        {"Item": "Max selected features", "Value": settings.get("max_selected_features")},
        {"Item": "Minimum data coverage", "Value": settings.get("min_coverage")},
        {"Item": "Most frequently selected variable", "Value": top_variable},
    ]
    pd.DataFrame(summary_rows).to_excel(OUTPUT_PATHS["summary"], index=False)

    plot_feature_selection_frequency(frequency)
    plot_top_feature_importance(importance_df)
    return OUTPUT_PATHS


def plot_feature_selection_frequency(frequency_df: pd.DataFrame) -> None:
    """Plot top selected base variables by frequency."""
    OUTPUT_PATHS["frequency_png"].parent.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({"figure.facecolor": "white", "axes.facecolor": "white"})
    fig, ax = plt.subplots(figsize=(8, 4.5))
    if not frequency_df.empty:
        data = frequency_df.head(15).sort_values("SelectionCount")
        ax.barh(data["Variable"], data["SelectionCount"], color="#1f77b4")
    ax.set_xlabel("Selection count")
    ax.set_ylabel("Variable")
    ax.grid(True, axis="x", color="#d9d9d9", linewidth=0.5)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    fig.tight_layout()
    fig.savefig(OUTPUT_PATHS["frequency_png"], dpi=300, bbox_inches="tight")
    plt.close(fig)


def plot_top_feature_importance(importance_df: pd.DataFrame) -> None:
    """Plot top lag-feature importance scores."""
    OUTPUT_PATHS["importance_png"].parent.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({"figure.facecolor": "white", "axes.facecolor": "white"})
    fig, ax = plt.subplots(figsize=(8, 4.5))
    if not importance_df.empty and {"Feature", "Score"}.issubset(importance_df.columns):
        data = importance_df.sort_values("Score", ascending=False).head(15).sort_values("Score")
        ax.barh(data["Feature"].astype(str), data["Score"], color="#4b5563")
    ax.set_xlabel("Importance score")
    ax.set_ylabel("Feature")
    ax.grid(True, axis="x", color="#d9d9d9", linewidth=0.5)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    fig.tight_layout()
    fig.savefig(OUTPUT_PATHS["importance_png"], dpi=300, bbox_inches="tight")
    plt.close(fig)


def read_feature_selection_summary() -> pd.DataFrame | None:
    """Read feature_selection_summary.xlsx if available."""
    path = OUTPUT_PATHS["summary"]
    if not path.exists():
        return None
    return pd.read_excel(path)
