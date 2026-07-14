"""WTI net-impact analysis data-cleaning utilities.

This module turns ``data/processed/clean_market_data.xlsx`` into a modeling
table for the multiscale net-impact analysis system.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT_PATH = PROJECT_ROOT / "data" / "processed" / "clean_market_data.xlsx"
DEFAULT_OUTPUT_PATH = PROJECT_ROOT / "data" / "processed" / "model_ready_data.xlsx"
MISSING_REPORT_PATH = PROJECT_ROOT / "outputs" / "tables" / "missing_report.xlsx"
CLEANING_REPORT_PATH = PROJECT_ROOT / "outputs" / "tables" / "cleaning_report.xlsx"

DEFAULT_TARGET_COL = "WTI"
DEFAULT_CANDIDATE_FEATURES = ["GPRD", "OVX", "DollarIndex", "TNote10Y", "Gold"]
DEFAULT_PRESERVED_PRICE_COLUMNS = ["Brent"]


def _resolve_project_path(path: str | Path) -> Path:
    """Resolve a relative path against the project root."""
    path = Path(path)
    if path.is_absolute():
        return path
    return PROJECT_ROOT / path


def _ensure_output_directories() -> None:
    """Create processed-data and report directories if needed."""
    DEFAULT_OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    MISSING_REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)


def load_raw_data(file_path: str | Path) -> pd.DataFrame:
    """Load a raw CSV or Excel file.

    Args:
        file_path: Path to a raw CSV, XLSX, or XLS file.

    Returns:
        Loaded raw data.
    """
    path = _resolve_project_path(file_path)
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return pd.read_csv(path)
    if suffix in {".xlsx", ".xls"}:
        return pd.read_excel(path)
    raise ValueError("Only .csv, .xlsx, and .xls files are supported.")


def clean_price_data(
    data: pd.DataFrame,
    date_column: str = "Date",
    price_column: str = DEFAULT_TARGET_COL,
) -> pd.DataFrame:
    """Clean a single WTI price time series without filling the target.

    Args:
        data: Input price dataset.
        date_column: Name of the date column.
        price_column: Name of the WTI price column.

    Returns:
        Cleaned WTI price dataset.
    """
    cleaned = data.copy()
    cleaned[date_column] = pd.to_datetime(cleaned[date_column], errors="coerce")
    cleaned = cleaned.dropna(subset=[date_column])
    cleaned = cleaned.drop_duplicates(subset=[date_column], keep="last")
    cleaned = cleaned.dropna(subset=[price_column])
    cleaned = cleaned.sort_values(date_column).reset_index(drop=True)
    return cleaned


def merge_datasets(
    base_data: pd.DataFrame,
    extra_data: list[pd.DataFrame],
    date_column: str = "Date",
) -> pd.DataFrame:
    """Merge datasets by date.

    Args:
        base_data: Main DataFrame.
        extra_data: Additional DataFrames to merge by date.
        date_column: Shared date column name.

    Returns:
        Merged DataFrame.
    """
    merged = base_data.copy()
    for dataset in extra_data:
        merged = merged.merge(dataset, on=date_column, how="left")
    return merged


def save_processed_data(data: pd.DataFrame, output_path: str | Path) -> None:
    """Save processed data as CSV or Excel based on the file extension.

    Args:
        data: Processed dataset to save.
        output_path: Destination file path.
    """
    path = _resolve_project_path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix.lower() in {".xlsx", ".xls"}:
        data.to_excel(path, index=False)
    else:
        data.to_csv(path, index=False)


def _initialise_missing_report_rows(
    data: pd.DataFrame,
    variables: list[str],
) -> dict[str, dict[str, Any]]:
    """Create missing-report rows with before-cleaning statistics."""
    total_rows = len(data)
    report_rows: dict[str, dict[str, Any]] = {}
    for variable in variables:
        missing_before = int(data[variable].isna().sum()) if variable in data else total_rows
        report_rows[variable] = {
            "Variable": variable,
            "MissingBefore": missing_before,
            "MissingAfter": None,
            "NonMissingRatioBefore": (
                1 - missing_before / total_rows if total_rows else 0.0
            ),
            "NonMissingRatioAfter": None,
            "Action": "",
        }
    return report_rows


def _finalise_missing_report_rows(
    report_rows: dict[str, dict[str, Any]],
    cleaned_data: pd.DataFrame,
) -> pd.DataFrame:
    """Add after-cleaning statistics to missing-report rows."""
    output_rows = len(cleaned_data)
    for variable, row in report_rows.items():
        if variable in cleaned_data:
            missing_after = int(cleaned_data[variable].isna().sum())
            ratio_after = 1 - missing_after / output_rows if output_rows else 0.0
        else:
            missing_after = output_rows
            ratio_after = 0.0
        row["MissingAfter"] = missing_after
        row["NonMissingRatioAfter"] = ratio_after
    return pd.DataFrame(report_rows.values())


def _write_cleaning_report(
    input_rows: int,
    output_data: pd.DataFrame,
    target_col: str,
    kept_features: list[str],
    dropped_features: list[str],
    dropped_reasons: dict[str, str],
    preserved_price_columns: list[str],
    max_ffill_days: int,
    min_non_missing_ratio: float,
    latest_wti_date_in_clean_data: pd.Timestamp | None,
) -> pd.DataFrame:
    """Write the high-level cleaning report."""
    latest_ready_date = output_data["Date"].max() if not output_data.empty else pd.NaT
    latest_preserved = (
        bool(pd.notna(latest_wti_date_in_clean_data) and latest_ready_date == latest_wti_date_in_clean_data)
        if pd.notna(latest_ready_date)
        else False
    )
    report = pd.DataFrame(
        [
            {"Item": "Input rows", "Value": input_rows},
            {"Item": "Output rows", "Value": len(output_data)},
            {
                "Item": "Start date",
                "Value": output_data["Date"].min() if not output_data.empty else pd.NaT,
            },
            {
                "Item": "End date",
                "Value": output_data["Date"].max() if not output_data.empty else pd.NaT,
            },
            {"Item": "Target variable", "Value": target_col},
            {"Item": "Kept features", "Value": ", ".join(kept_features)},
            {"Item": "Dropped features", "Value": ", ".join(dropped_features)},
            {
                "Item": "Preserved target-like columns",
                "Value": ", ".join(preserved_price_columns),
            },
            {
                "Item": "Dropped feature reasons",
                "Value": " | ".join(
                    f"{feature}: {reason}"
                    for feature, reason in dropped_reasons.items()
                ),
            },
            {
                "Item": "Missing-value policy",
                "Value": "Strict complete-case deletion: any row with any missing retained column is dropped.",
            },
            {"Item": "max_ffill_days", "Value": f"{max_ffill_days} (disabled)"},
            {"Item": "min_non_missing_ratio", "Value": min_non_missing_ratio},
            {
                "Item": "Latest WTI date in clean data",
                "Value": latest_wti_date_in_clean_data,
            },
            {
                "Item": "Latest date in model_ready_data",
                "Value": latest_ready_date,
            },
            {
                "Item": "Whether latest WTI date is preserved",
                "Value": latest_preserved,
            },
        ]
    )
    report.to_excel(CLEANING_REPORT_PATH, index=False)
    return report


def prepare_model_data(
    input_path: str | Path = DEFAULT_INPUT_PATH,
    output_path: str | Path = DEFAULT_OUTPUT_PATH,
    target_col: str = DEFAULT_TARGET_COL,
    candidate_features: list[str] | None = None,
    max_ffill_days: int = 0,
    min_non_missing_ratio: float = 0.6,
) -> pd.DataFrame:
    """Prepare model-ready WTI net-impact analysis data.

    Cleaning rules:
    - Convert Date to pandas datetime, sort, and remove duplicate dates.
    - Do not forward-fill or interpolate any variable.
    - Drop rows where any retained modeling column is missing.
    - Drop explanatory variables with low coverage.

    Args:
        input_path: Source market-data workbook.
        output_path: Destination model-ready workbook.
        target_col: Analysis target, default ``WTI``.
        candidate_features: Candidate explanatory variables.
        max_ffill_days: Retained for compatibility; strict cleaning does not fill missing values.
        min_non_missing_ratio: Minimum coverage required to keep a feature.

    Returns:
        Cleaned model-ready DataFrame.
    """
    _ensure_output_directories()
    candidate_features = candidate_features or DEFAULT_CANDIDATE_FEATURES
    input_path = _resolve_project_path(input_path)
    output_path = _resolve_project_path(output_path)

    if not input_path.exists():
        raise FileNotFoundError(f"Input market data not found: {input_path}")

    data = pd.read_excel(input_path)
    required_columns = ["Date", target_col]
    missing_required = [column for column in required_columns if column not in data]
    if missing_required:
        raise ValueError(f"Input data is missing required columns: {missing_required}")

    preserved_price_columns = [
        column
        for column in DEFAULT_PRESERVED_PRICE_COLUMNS
        if column in data.columns and column != target_col
    ]
    candidate_features = [
        feature
        for feature in candidate_features
        if feature not in preserved_price_columns and feature != target_col
    ]
    available_features = [feature for feature in candidate_features if feature in data.columns]
    missing_candidates = [feature for feature in candidate_features if feature not in data.columns]

    data = data.copy()
    data["Date"] = pd.to_datetime(data["Date"], errors="coerce")
    data = data.dropna(subset=["Date"])
    data = data.drop_duplicates(subset=["Date"], keep="last")
    data = data.sort_values("Date").reset_index(drop=True)

    variables_for_report = [target_col] + preserved_price_columns + available_features + missing_candidates
    report_rows = _initialise_missing_report_rows(data, variables_for_report)
    report_rows[target_col]["Action"] = "Target_drop_missing_rows"
    for column in preserved_price_columns:
        report_rows[column]["Action"] = "Preserved_target_like_no_fill"

    input_rows = len(data)

    # WTI is the target and is never filled. This target-valid subset is used
    # to judge feature coverage so weekends/non-trading days do not dominate.
    target_valid_data = data.dropna(subset=[target_col]).copy()
    latest_wti_date_in_clean_data = (
        target_valid_data["Date"].max() if not target_valid_data.empty else pd.NaT
    )

    kept_features: list[str] = []
    dropped_features = missing_candidates.copy()
    dropped_reasons: dict[str, str] = {}
    for feature in missing_candidates:
        report_rows[feature]["Action"] = "Dropped_low_coverage"
        dropped_reasons[feature] = "column_missing"

    for feature in available_features:
        non_missing_ratio = (
            float(target_valid_data[feature].notna().mean())
            if len(target_valid_data)
            else 0.0
        )
        if non_missing_ratio < min_non_missing_ratio:
            dropped_features.append(feature)
            report_rows[feature]["Action"] = "Dropped_low_coverage"
            dropped_reasons[feature] = (
                f"non_missing_ratio_on_wti_days={non_missing_ratio:.3f} "
                f"< {min_non_missing_ratio:.3f}"
            )
            continue

        kept_features.append(feature)
        report_rows[feature]["Action"] = "Strict_complete_case_required"

    if "GPRD" not in kept_features:
        reason = dropped_reasons.get("GPRD", "not available")
        raise ValueError(
            "GPRD is required for model-ready data, but it did not pass data preparation. "
            f"Reason: {reason}."
        )

    output_columns = ["Date", target_col] + preserved_price_columns + kept_features
    cleaned = data[output_columns].copy()
    cleaned = cleaned.dropna(subset=output_columns).reset_index(drop=True)

    save_processed_data(cleaned, output_path)

    missing_report = _finalise_missing_report_rows(report_rows, cleaned)
    missing_report.to_excel(MISSING_REPORT_PATH, index=False)

    _write_cleaning_report(
        input_rows=input_rows,
        output_data=cleaned,
        target_col=target_col,
        kept_features=kept_features,
        dropped_features=dropped_features,
        dropped_reasons=dropped_reasons,
        preserved_price_columns=preserved_price_columns,
        max_ffill_days=max_ffill_days,
        min_non_missing_ratio=min_non_missing_ratio,
        latest_wti_date_in_clean_data=latest_wti_date_in_clean_data,
    )

    return cleaned
