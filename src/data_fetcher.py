'Market data download and preparation helper.'

from __future__ import annotations

import json
import os
import re
import time
import warnings
import uuid
from functools import reduce
from io import StringIO
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlencode, urljoin, urlparse
from urllib.request import Request, urlopen

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_DATA_DIR = PROJECT_ROOT / "data" / "raw"
PROCESSED_DATA_DIR = PROJECT_ROOT / "data" / "processed"
OUTPUT_TABLES_DIR = PROJECT_ROOT / "outputs" / "tables"
PROCESSED_MARKET_DATA_PATH = PROCESSED_DATA_DIR / "clean_market_data.xlsx"
PROCESSED_GPRD_PATH = PROCESSED_DATA_DIR / "gprd_clean.xlsx"
DATA_SOURCE_LOG_PATH = OUTPUT_TABLES_DIR / "data_source_log.xlsx"

EIA_API_URL = "https://api.eia.gov/v2/petroleum/pri/fut/data/"
EIA_EXCEL_URLS = {
    "RCLC1": "https://www.eia.gov/dnav/pet/hist_xls/RCLC1d.xls",
}

GPRD_OFFICIAL_PAGE_URL = "https://www.matteoiacoviello.com/gpr.htm"
GPRD_DAILY_RECENT_URL = (
    "https://www.matteoiacoviello.com/gpr_files/data_gpr_daily_recent.xls"
)
POLICY_UNCERTAINTY_DAILY_URL = "https://www.policyuncertainty.com/media/All_Daily_Policy_Data.csv"
POLICY_UNCERTAINTY_DAILY_SOURCES = {
    "US": {
        "url": POLICY_UNCERTAINTY_DAILY_URL,
        "value_column": "daily_policy_index",
        "actual_source": "policy_uncertainty_daily:US",
    },
    "EPU": {
        "url": POLICY_UNCERTAINTY_DAILY_URL,
        "value_column": "daily_policy_index",
        "actual_source": "policy_uncertainty_daily:US",
    },
    "TPU": {
        "url": "https://www.policyuncertainty.com/media/All_Daily_TPU_Data.csv",
        "value_column": "daily_tpu_index",
        "actual_source": "policy_uncertainty_daily:TPU",
    },
    "EMV": {
        "url": "https://www.policyuncertainty.com/media/All_Infectious_EMV_Data.csv",
        "value_column": "daily_infect_emv_index",
        "actual_source": "policy_uncertainty_daily:EMV",
    },
}
NYFED_EFFR_API_URL = "https://markets.newyorkfed.org/api/rates/unsecured/effr/search.json"
TREASURY_YIELD_CURVE_URL = (
    "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/TextView"
)
RAW_CACHE_FILES = {
    "WTI": RAW_DATA_DIR / "WTI_EIA_RCLC1.csv",
    "Brent": RAW_DATA_DIR / "Brent_BZ_F.csv",
    "Gold": RAW_DATA_DIR / "Gold_GC_F.csv",
    "OVX": RAW_DATA_DIR / "OVX_FRED_OVXCLS.csv",
    "DollarIndex": RAW_DATA_DIR / "DollarIndex_DTWEXBGS.csv",
    "TNote10Y": RAW_DATA_DIR / "TNote10Y_DGS10.csv",
}

SERIES_SOURCES = {
    "WTI": [
        {"type": "eia", "id": "RCLC1"},
        {"type": "yfinance", "id": "CL=F"},
        {"type": "stooq", "id": "CL.F"},
        {"type": "fred_csv", "id": "DCOILWTICO"},
    ],
    "Brent": [
        {"type": "fred", "id": "DCOILBRENTEU"},
        {"type": "yfinance", "id": "BZ=F"},
        {"type": "stooq", "id": "CB.F"},
        {"type": "stooq", "id": "SC.F"},
    ],
    "Gold": [
        {"type": "yfinance", "id": "GC=F"},
        {"type": "stooq", "id": "GC.F"},
    ],
    "OVX": [
        {"type": "fred", "id": "OVXCLS"},
        {"type": "yfinance", "id": "^OVX"},
    ],
    "DollarIndex": [
        {"type": "fred", "id": "DTWEXBGS"},
        {"type": "yfinance", "id": "DX-Y.NYB"},
    ],
    "TNote10Y": [
        {"type": "fred", "id": "DGS10"},
        {"type": "treasury_yield_curve", "id": "10 Yr"},
        {"type": "yfinance", "id": "^TNX"},
    ],
}

YFINANCE_SERIES = {
    "WTI": "CL=F",
    "Brent": "BZ=F",
    "Gold": "GC=F",
}

MARKET_COLUMNS = [
    "Date",
    "WTI",
    "Brent",
    "Gold",
    "OVX",
    "DollarIndex",
    "TNote10Y",
    "GPRD",
]

REQUESTED_TYPES = {
    "WTI": "WTI crude oil futures price; target variable",
    "Brent": "Brent crude oil futures price; paper-replication oil benchmark",
    "Gold": "Gold futures price",
    "OVX": "CBOE crude oil volatility index",
    "DollarIndex": "U.S. Dollar Index",
    "TNote10Y": "10-year Treasury yield",
    "GPRD": "Traditional Caldara-Iacoviello GPR daily index",
}

LAST_SOURCE_USED: dict[str, str] = {}
LAST_SOURCE_NOTES: dict[str, str] = {}


def _env_int(name: str, default: int) -> int:
    """Read a positive integer environment option with a safe default."""
    try:
        value = int(str(os.getenv(name, "")).strip())
    except (TypeError, ValueError):
        return default
    return value if value > 0 else default


def _fred_timeout_seconds() -> int:
    """Timeout for FRED downloads; public FRED can be slow on some networks."""
    return _env_int("FRED_HTTP_TIMEOUT", 25)


def _fred_retries() -> int:
    """Retry count for FRED downloads."""
    return _env_int("FRED_HTTP_RETRIES", 2)


def _ensure_data_directories() -> None:
    'Market data download and preparation helper.'
    RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)
    PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_TABLES_DIR.mkdir(parents=True, exist_ok=True)


def _validate_date_range(
    start_date: str | pd.Timestamp,
    end_date: str | pd.Timestamp,
) -> tuple[pd.Timestamp, pd.Timestamp]:
    'Market data download and preparation helper.'
    start_timestamp = pd.to_datetime(start_date)
    end_timestamp = pd.to_datetime(end_date)

    if pd.isna(start_timestamp) or pd.isna(end_timestamp):
        raise ValueError('start_date and end_date must be valid dates, for example 2020-01-01.')
    if start_timestamp > end_timestamp:
        raise ValueError('start_date cannot be after end_date.')

    return start_timestamp.normalize(), end_timestamp.normalize()


def _normalise_date_column(data: pd.DataFrame, date_column: str = "Date") -> pd.DataFrame:
    'Market data download and preparation helper.'
    normalised = data.copy()
    normalised[date_column] = pd.to_datetime(
        normalised[date_column],
        errors="coerce",
        utc=True,
    )
    normalised[date_column] = normalised[date_column].dt.tz_convert(None).dt.normalize()
    return normalised


def _prepare_two_column_series(data: pd.DataFrame, value_column: str) -> pd.DataFrame:
    'Input data must contain Date and a numeric value column.'
    prepared = data[["Date", value_column]].copy()
    prepared = _normalise_date_column(prepared)
    prepared[value_column] = pd.to_numeric(prepared[value_column], errors="coerce")
    prepared = prepared.dropna(subset=["Date"])
    prepared = prepared.drop_duplicates(subset=["Date"], keep="last")
    prepared = prepared.sort_values("Date").reset_index(drop=True)
    return prepared


def _empty_market_frame(
    name: str,
    start_date: str | pd.Timestamp,
    end_date: str | pd.Timestamp,
) -> pd.DataFrame:
    'Market data download and preparation helper.'
    start_timestamp, end_timestamp = _validate_date_range(start_date, end_date)
    dates = pd.date_range(start_timestamp, end_timestamp, freq="D")
    return pd.DataFrame({"Date": dates, name: pd.NA})


def _has_valid_values(data: pd.DataFrame, value_column: str) -> bool:
    'Market data download and preparation helper.'
    return value_column in data.columns and data[value_column].notna().any()


def _is_fresh_enough(
    data: pd.DataFrame,
    value_column: str,
    end_date: str | pd.Timestamp,
    max_lag_days: int = 7,
) -> tuple[bool, str]:
    'Input data must contain Date and a numeric value column.'
    if not _has_valid_values(data, value_column):
        return False, f"{value_column} has no valid values."

    valid_dates = pd.to_datetime(
        data.loc[data[value_column].notna(), "Date"],
        errors="coerce",
    ).dropna()
    if valid_dates.empty:
        return False, f"{value_column} has no valid dates."

    latest_date = valid_dates.max()
    requested_end = pd.to_datetime(end_date)
    lag_days = int((requested_end - latest_date).days)
    if lag_days > max_lag_days:
        return (
            False,
            f"{value_column} data ends at {latest_date:%Y-%m-%d}, "
            f"which is {lag_days} days before requested end date {requested_end:%Y-%m-%d}.",
        )

    return True, f"{value_column} data ends at {latest_date:%Y-%m-%d}."


def _freshness_lag_days_for_variable(name: str) -> int:
    """Return source freshness tolerance in calendar days."""
    if name == "WTI":
        return 7
    if name in {"Brent", "Gold"}:
        return 10
    return 14


def _filter_by_date_range(
    data: pd.DataFrame,
    start_date: str | pd.Timestamp,
    end_date: str | pd.Timestamp,
) -> pd.DataFrame:
    'Input data must contain Date and a numeric value column.'
    start_timestamp, end_timestamp = _validate_date_range(start_date, end_date)
    filtered = _normalise_date_column(data)
    filtered = filtered.dropna(subset=["Date"])
    filtered = filtered[
        (filtered["Date"] >= start_timestamp) & (filtered["Date"] <= end_timestamp)
    ]
    return filtered.sort_values("Date").reset_index(drop=True)


def _source_label(source_type: str, source_id: str) -> str:
    'Market data download and preparation helper.'
    return f"{source_type}:{source_id}"


def _safe_exception_text(exc: BaseException) -> str:
    """Return an ASCII-only exception summary for UI and logs."""
    message = str(exc).encode("ascii", errors="ignore").decode("ascii").strip()
    message = re.sub(r"\s+", " ", message)
    if message:
        return f"{type(exc).__name__}: {message}"
    return type(exc).__name__


def _load_environment_files() -> None:
    'Market data download and preparation helper.'
    try:
        from dotenv import load_dotenv
    except ImportError as exc:
        raise ImportError(
            'Missing python-dotenv. Please run: pip install -r requirements.txt'
        ) from exc

    env_path = PROJECT_ROOT / ".env"
    api_env_path = PROJECT_ROOT / "API.env"

    if env_path.exists():
        load_dotenv(env_path, override=True)
    if api_env_path.exists():
        load_dotenv(api_env_path, override=False)


def _read_env_file_value(path: Path, key: str) -> str:
    'Market data download and preparation helper.'
    if not path.exists():
        return ""
    try:
        for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            name, value = stripped.split("=", 1)
            if name.strip() == key:
                return value.strip().strip('"').strip("'")
    except OSError:
        return ""
    return ""


def _looks_like_fred_api_key(api_key: str) -> bool:
    """FRED API keys are 32 lower-case alphanumeric characters."""
    return len(api_key) == 32 and api_key.isalnum() and api_key.lower() == api_key


def _get_fred_api_key() -> str:
    """Read FRED_API_KEY from .env, API.env, or the process environment."""
    _load_environment_files()
    env_path = PROJECT_ROOT / ".env"
    api_env_path = PROJECT_ROOT / "API.env"
    candidates = [
        _read_env_file_value(env_path, "FRED_API_KEY"),
        _read_env_file_value(api_env_path, "FRED_API_KEY"),
        os.getenv("FRED_API_KEY", "").strip(),
    ]
    for api_key in candidates:
        api_key = str(api_key).strip()
        if _looks_like_fred_api_key(api_key):
            return api_key
    if not any(str(candidate).strip() for candidate in candidates):
        raise RuntimeError(
            "FRED_API_KEY was not found. Public FRED CSV fallback will be used when possible. "
            "Create API.env with FRED_API_KEY=your_fred_api_key for the official FRED API."
        )
    raise RuntimeError(
        "FRED_API_KEY has an invalid format. A FRED key should be 32 lower-case "
        "alphanumeric characters. Public FRED CSV fallback will be used when possible."
    )


def _get_eia_api_key() -> str:
    'EIA source returned no usable data.'
    _load_environment_files()
    return os.getenv("EIA_API_KEY", "DEMO_KEY").strip() or "DEMO_KEY"


def _has_configured_fred_api_key() -> bool:
    """Return True when a usable FRED API key is configured."""
    _load_environment_files()
    env_path = PROJECT_ROOT / ".env"
    api_env_path = PROJECT_ROOT / "API.env"
    candidates = [
        _read_env_file_value(env_path, "FRED_API_KEY"),
        _read_env_file_value(api_env_path, "FRED_API_KEY"),
        os.getenv("FRED_API_KEY", "").strip(),
    ]
    return any(_looks_like_fred_api_key(str(candidate).strip()) for candidate in candidates)


def _has_configured_eia_api_key() -> bool:
    """Return True when a non-demo EIA API key is configured."""
    _load_environment_files()
    env_path = PROJECT_ROOT / ".env"
    api_env_path = PROJECT_ROOT / "API.env"
    candidates = [
        _read_env_file_value(env_path, "EIA_API_KEY"),
        _read_env_file_value(api_env_path, "EIA_API_KEY"),
        os.getenv("EIA_API_KEY", "").strip(),
    ]
    for candidate in candidates:
        value = str(candidate or "").strip()
        if value and value.upper() != "DEMO_KEY" and "your_key_here" not in value.lower():
            return True
    return False


def _source_uses_configured_api(source: dict[str, str]) -> bool:
    """Return whether the source should be tried first because its API key exists."""
    source_type = str(source.get("type", "")).lower()
    if source_type == "fred":
        return _has_configured_fred_api_key()
    if source_type == "eia":
        return _has_configured_eia_api_key()
    return False


def _prioritise_api_sources(sources: list[dict[str, str]]) -> list[dict[str, str]]:
    """Move configured API sources ahead of non-API sources while preserving order."""
    return [
        source
        for _, source in sorted(
            enumerate(sources),
            key=lambda item: (0 if _source_uses_configured_api(item[1]) else 1, item[0]),
        )
    ]


def _get_fred_client() -> Any:
    'FRED returned no data for the requested series.'
    try:
        from fredapi import Fred
    except ImportError as exc:
        raise ImportError('Missing fredapi. Please run: pip install -r requirements.txt') from exc

    return Fred(api_key=_get_fred_api_key())


def _safe_http_get(url: str, timeout: int = 30, retries: int = 3) -> bytes:
    """Download URL bytes with browser-like headers and short retries."""
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "text/csv,application/vnd.ms-excel,application/json,text/plain,*/*",
        "Connection": "close",
    }
    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        request = Request(url, headers=headers)
        try:
            with urlopen(request, timeout=timeout) as response:
                return response.read()
        except Exception as exc:  # noqa: BLE001 - transient public-source failures are common.
            last_error = exc
            if attempt < retries:
                time.sleep(min(2 * attempt, 5))
    if last_error is not None:
        raise last_error
    raise RuntimeError(f"Could not download URL: {url}")


def _download_file(url: str, output_path: Path, timeout: int = 30, retries: int = 3) -> Path:
    """Download a file to disk."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = _safe_http_get(url, timeout=timeout, retries=retries)
    temporary_path = output_path.with_name(f"{output_path.stem}.{uuid.uuid4().hex}.tmp")
    temporary_path.write_bytes(payload)
    temporary_path.replace(output_path)
    return output_path


def _read_table_file(file_path: str | Path) -> pd.DataFrame:
    'Market data download and preparation helper.'
    path = Path(file_path)
    suffix = path.suffix.lower()

    if suffix == ".csv":
        return pd.read_csv(path)
    if suffix in {".xlsx", ".xls"}:
        try:
            return pd.read_excel(path)
        except ImportError as exc:
            raise ImportError(
                'Reading Excel files requires openpyxl or xlrd. Please run: pip install -r requirements.txt'
            ) from exc

    raise ValueError(f"Unsupported table file type: {path.suffix}")


def _find_column_case_insensitive(
    columns: list[str],
    candidates: list[str],
) -> str | None:
    'Market data download and preparation helper.'
    column_lookup = {column.strip().lower(): column for column in columns}
    for candidate in candidates:
        matched = column_lookup.get(candidate.lower())
        if matched:
            return matched
    return None


def _find_market_value_column(
    data: pd.DataFrame,
    name: str,
    source_id: str | None = None,
) -> str | None:
    'Market data download and preparation helper.'
    candidates = [name, "Close", "Adj Close", "Price", "value", "Value"]
    if source_id:
        candidates.extend(
            [
                f"{name}_{source_id}",
                f"Close_{source_id}",
                f"Adj Close_{source_id}",
                f"Price_{source_id}",
            ]
        )

    matched = _find_column_case_insensitive(data.columns.tolist(), candidates)
    if matched:
        return matched

    for column in data.columns:
        cleaned = str(column).strip().lower()
        if cleaned == name.lower():
            return column
        if cleaned.startswith(("close", "adj close", "price", "value")):
            return column

    return None


def _standardise_market_data(
    raw_data: pd.DataFrame,
    name: str,
    source_id: str | None = None,
) -> pd.DataFrame:
    'Input data must contain Date and a numeric value column.'
    data = raw_data.copy()
    data.columns = [str(column).strip() for column in data.columns]

    date_column = _find_column_case_insensitive(
        data.columns.tolist(),
        ["Date", "Datetime", "date", "datetime", "period"],
    )
    value_column = _find_market_value_column(data, name, source_id)

    if not date_column or not value_column:
        raise ValueError(
            f"{name} data must contain Date and one of Close, Adj Close, Price, value, or {name}."
        )

    standardised = data[[date_column, value_column]].copy()
    standardised.columns = ["Date", name]
    return _prepare_two_column_series(standardised, name)


def _load_cache_file(
    cache_file: str | Path,
    name: str,
    start_date: str | pd.Timestamp,
    end_date: str | pd.Timestamp,
    source_id: str | None = None,
) -> pd.DataFrame:
    'Market data download and preparation helper.'
    cache_path = Path(cache_file)
    if not cache_path.exists():
        warnings.warn(f"{name} has no cache file available: {cache_path}")
        return _empty_market_frame(name, start_date, end_date)

    try:
        cached_data = _read_table_file(cache_path)
        data = _standardise_market_data(cached_data, name, source_id)
        data = _filter_by_date_range(data, start_date, end_date)
        if data.empty:
            warnings.warn(f"{name} cache exists but has no data in the requested date range.")
            return _empty_market_frame(name, start_date, end_date)

        warnings.warn(f"{name} loaded from cache file: {cache_path}")
        return data
    except Exception as exc:  # noqa: BLE001 - continue fallback handling.
        warnings.warn(
            f"{name} cache file could not be read; keeping an empty series. "
            f"Reason: {_safe_exception_text(exc)}"
        )
        return _empty_market_frame(name, start_date, end_date)


def fetch_eia_series(
    series_id: str,
    name: str,
    start_date: str,
    end_date: str,
    cache_file: str | Path | None = None,
) -> pd.DataFrame:
    'EIA API returned no data.'
    _ensure_data_directories()
    try:
        data = _fetch_eia_api_series(series_id, name, start_date, end_date)
    except Exception as api_exc:  # noqa: BLE001 - continue fallback handling.
        warnings.warn(
            f"{name} / EIA {series_id} API failed; trying EIA Excel. "
            f"Reason: {_safe_exception_text(api_exc)}"
        )
        data = _fetch_eia_excel_series(series_id, name, start_date, end_date)

    if not _has_valid_values(data, name):
        raise ValueError(f"EIA {series_id} returned no usable data.")

    if cache_file:
        save_raw_data(data, cache_file)
    return data


def _fetch_eia_api_series(
    series_id: str,
    name: str,
    start_date: str,
    end_date: str,
) -> pd.DataFrame:
    'EIA API returned no data.'
    start_timestamp, end_timestamp = _validate_date_range(start_date, end_date)
    rows: list[dict[str, Any]] = []
    offset = 0
    length = 5000

    while True:
        params = [
            ("api_key", _get_eia_api_key()),
            ("frequency", "daily"),
            ("data[0]", "value"),
            ("facets[series][]", series_id),
            ("start", start_timestamp.strftime("%Y-%m-%d")),
            ("end", end_timestamp.strftime("%Y-%m-%d")),
            ("sort[0][column]", "period"),
            ("sort[0][direction]", "asc"),
            ("offset", str(offset)),
            ("length", str(length)),
        ]
        url = f"{EIA_API_URL}?{urlencode(params)}"
        payload = json.loads(_safe_http_get(url).decode("utf-8"))
        response = payload.get("response", {})
        data = response.get("data", [])
        rows.extend(data)

        total = int(response.get("total", len(rows)) or len(rows))
        if not data or len(rows) >= total:
            break
        offset += length

    if not rows:
        raise ValueError('EIA API returned no data.')

    raw_data = pd.DataFrame(rows)
    standardised = raw_data[["period", "value"]].copy()
    standardised.columns = ["Date", name]
    return _prepare_two_column_series(standardised, name)


def _fetch_eia_excel_series(
    series_id: str,
    name: str,
    start_date: str,
    end_date: str,
) -> pd.DataFrame:
    'EIA source returned no usable data.'
    url = EIA_EXCEL_URLS.get(series_id)
    if not url:
        raise ValueError(f"No EIA Excel download URL is configured for {series_id}.")

    raw_path = RAW_DATA_DIR / f"{series_id}_eia_download.xls"
    _download_file(url, raw_path)
    raw_data = pd.read_excel(raw_path, sheet_name="Data 1", header=None)

    # NOTE: fallback behavior is intentional.
    data = raw_data.iloc[3:, [0, 1]].copy()
    data.columns = ["Date", name]
    data = _prepare_two_column_series(data, name)
    return _filter_by_date_range(data, start_date, end_date)


def fetch_fred_series(
    series_id: str,
    name: str,
    start_date: str,
    end_date: str,
    cache_file: str | Path | None = None,
    allow_public_csv: bool = True,
) -> pd.DataFrame:
    """Download one FRED series with API, fredapi, and public CSV fallbacks."""
    _ensure_data_directories()
    start_timestamp, end_timestamp = _validate_date_range(start_date, end_date)
    errors: list[str] = []

    try:
        api_key = _get_fred_api_key()
    except Exception as exc:  # noqa: BLE001 - public CSV fallback does not need a key.
        api_key = ""
        errors.append(f"api key unavailable: {_safe_exception_text(exc)}")
        warnings.warn(
            f"FRED API key is not usable for {series_id}; trying public CSV fallback. "
            f"Reason: {_safe_exception_text(exc)}"
        )

    if api_key:
        try:
            return fetch_fred_api_http_series(
                series_id,
                name,
                start_date,
                end_date,
                cache_file,
                api_key=api_key,
            )
        except Exception as exc:  # noqa: BLE001 - keep trying the package and public CSV.
            error_text = _safe_exception_text(exc)
            errors.append(f"official API failed: {error_text}")
            warnings.warn(
                f"FRED HTTP API unavailable for {series_id}; trying fredapi package. "
                f"Reason: {error_text}"
            )

        try:
            from fredapi import Fred
        except ImportError as exc:
            errors.append(f"fredapi package unavailable: {_safe_exception_text(exc)}")
        else:
            try:
                fred = Fred(api_key=api_key)
                series = fred.get_series(
                    series_id,
                    observation_start=start_timestamp,
                    observation_end=end_timestamp,
                )
                if not series.empty:
                    data = series.rename(name).reset_index()
                    data.columns = ["Date", name]
                    data = _prepare_two_column_series(data, name)
                    if _has_valid_values(data, name):
                        save_raw_data(data, cache_file or RAW_DATA_DIR / f"{name}_{series_id}.csv")
                        data.attrs["actual_source"] = f"fredapi:{series_id}"
                        return data
                errors.append("fredapi returned no usable data")
            except Exception as exc:  # noqa: BLE001 - public CSV is the final fallback.
                error_text = _safe_exception_text(exc)
                errors.append(f"fredapi failed: {error_text}")
                next_step = "public CSV" if allow_public_csv else "the next configured source"
                warnings.warn(
                    f"FRED fredapi package unavailable for {series_id}; trying {next_step}. "
                    f"Reason: {error_text}"
                )

    if not allow_public_csv:
        detail = " | ".join(errors)
        raise RuntimeError(
            f"FRED API/fredapi failed for {series_id}; public CSV was skipped because "
            f"another configured source will be tried. {detail}"
        )

    try:
        return fetch_fred_csv_series(series_id, name, start_date, end_date, cache_file)
    except Exception as exc:  # noqa: BLE001 - preserve all FRED diagnostics for the UI.
        error_text = _safe_exception_text(exc)
        errors.append(f"public CSV failed: {error_text}")
        detail = " | ".join(errors)
        raise RuntimeError(f"FRED download failed for {series_id}. {detail}") from exc


def fetch_fred_api_http_series(
    series_id: str,
    name: str,
    start_date: str,
    end_date: str,
    cache_file: str | Path | None = None,
    api_key: str | None = None,
) -> pd.DataFrame:
    """Download one FRED series through the official observations API."""
    _ensure_data_directories()
    start_timestamp, end_timestamp = _validate_date_range(start_date, end_date)
    fred_key = (api_key or _get_fred_api_key()).strip()
    params = {
        "series_id": series_id,
        "api_key": fred_key,
        "file_type": "json",
        "observation_start": start_timestamp.strftime("%Y-%m-%d"),
        "observation_end": end_timestamp.strftime("%Y-%m-%d"),
    }
    url = "https://api.stlouisfed.org/fred/series/observations?" + urlencode(params)
    payload = json.loads(
        _safe_http_get(
            url,
            timeout=_fred_timeout_seconds(),
            retries=_fred_retries(),
        ).decode("utf-8", errors="ignore")
    )
    if "error_code" in payload:
        raise ValueError(payload.get("error_message", f"FRED error {payload['error_code']}"))

    observations = payload.get("observations", [])
    if not observations:
        raise ValueError(f"FRED API returned no observations for {series_id}.")

    raw = pd.DataFrame(observations)
    if "date" not in raw.columns or "value" not in raw.columns:
        raise ValueError(f"FRED API response for {series_id} is missing date/value fields.")

    data = pd.DataFrame(
        {
            "Date": pd.to_datetime(raw["date"], errors="coerce"),
            name: pd.to_numeric(raw["value"].replace(".", pd.NA), errors="coerce"),
        }
    )
    data = data.dropna(subset=["Date"])
    data = data.drop_duplicates(subset=["Date"], keep="last")
    data = data.sort_values("Date").reset_index(drop=True)
    data = _filter_by_date_range(data, start_date, end_date)
    if not _has_valid_values(data, name):
        raise ValueError(f"FRED API returned no usable values for {series_id}.")

    save_raw_data(data, cache_file or RAW_DATA_DIR / f"{name}_{series_id}.csv")
    data.attrs["actual_source"] = f"fred_api:{series_id}"
    return data


def fetch_fred_csv_series(
    series_id: str,
    name: str,
    start_date: str,
    end_date: str,
    cache_file: str | Path | None = None,
) -> pd.DataFrame:
    """Download a FRED graph CSV series without requiring a FRED API key."""
    _ensure_data_directories()
    start_timestamp, end_timestamp = _validate_date_range(start_date, end_date)
    params = urlencode(
        {
            "id": series_id,
            "cosd": start_timestamp.strftime("%Y-%m-%d"),
            "coed": end_timestamp.strftime("%Y-%m-%d"),
        }
    )
    url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?{params}"
    raw_text: str | None = None
    timeout = _fred_timeout_seconds()
    retries = _fred_retries()
    try:
        import requests
    except ImportError:
        raw_text = _safe_http_get(url, timeout=timeout, retries=retries).decode("utf-8", errors="ignore")
    else:
        last_error: Exception | None = None

        headers = {
            "User-Agent": "Mozilla/5.0",
            "Accept": "text/csv,*/*",
            "Connection": "close",
        }
        for attempt in range(1, retries + 1):
            try:
                response = requests.get(url, headers=headers, timeout=timeout)
                response.raise_for_status()
                raw_text = response.text
                break
            except Exception as exc:  # noqa: BLE001 - retry transient public CSV failures.
                last_error = exc
                if attempt < retries:
                    time.sleep(min(2 * attempt, 5))
        if raw_text is None and last_error is not None:
            raise last_error
    raw = pd.read_csv(StringIO(raw_text))
    if raw.empty or raw.shape[1] < 2:
        raise ValueError(f"FRED public CSV returned no data for {series_id}.")
    date_column = raw.columns[0]
    value_column = raw.columns[1]
    data = raw[[date_column, value_column]].copy()
    data.columns = ["Date", name]
    data[name] = pd.to_numeric(data[name].replace(".", pd.NA), errors="coerce")
    data = _prepare_two_column_series(data, name)
    data = _filter_by_date_range(data, start_date, end_date)
    if not _has_valid_values(data, name):
        raise ValueError(f"FRED public CSV returned no usable values for {series_id}.")
    if cache_file:
        save_raw_data(data, cache_file)
    else:
        save_raw_data(data, RAW_DATA_DIR / f"{name}_{series_id}.csv")
    data.attrs["actual_source"] = f"fred_csv:{series_id}"
    return data


def _treasury_yield_column(source_id: str) -> str:
    """Map a Treasury yield source id to the official table column."""
    cleaned = str(source_id).strip().lower().replace("_", " ").replace("-", " ")
    aliases = {
        "2": "2 Yr",
        "2 yr": "2 Yr",
        "2y": "2 Yr",
        "dgs2": "2 Yr",
        "10": "10 Yr",
        "10 yr": "10 Yr",
        "10y": "10 Yr",
        "dgs10": "10 Yr",
    }
    if cleaned in aliases:
        return aliases[cleaned]
    if source_id in {"2 Yr", "10 Yr"}:
        return source_id
    raise ValueError(f"Unsupported Treasury yield tenor: {source_id}")


def fetch_treasury_yield_curve_series(
    source_id: str,
    name: str,
    start_date: str,
    end_date: str,
    cache_file: str | Path | None = None,
) -> pd.DataFrame:
    """Download daily Treasury yield curve data from the U.S. Treasury website."""
    _ensure_data_directories()
    start_timestamp, end_timestamp = _validate_date_range(start_date, end_date)
    column = _treasury_yield_column(source_id)
    frames: list[pd.DataFrame] = []
    errors: list[str] = []
    headers = {"User-Agent": "Mozilla/5.0"}

    for year in range(start_timestamp.year, end_timestamp.year + 1):
        params = urlencode(
            {
                "type": "daily_treasury_yield_curve",
                "field_tdr_date_value": str(year),
            }
        )
        url = f"{TREASURY_YIELD_CURVE_URL}?{params}"
        try:
            tables = pd.read_html(url, storage_options=headers)
            if not tables:
                raise ValueError("Treasury page returned no tables.")
            raw = tables[0]
            if "Date" not in raw.columns or column not in raw.columns:
                raise ValueError(f"Treasury yield table did not contain Date/{column}.")
            frame = raw[["Date", column]].copy()
            frame.columns = ["Date", name]
            frames.append(frame)
        except Exception as exc:  # noqa: BLE001 - try other years and report all failures.
            errors.append(f"{year}: {_safe_exception_text(exc)}")

    if not frames:
        raise ValueError("Treasury yield curve download failed. " + " | ".join(errors))

    data = pd.concat(frames, ignore_index=True)
    data = _prepare_two_column_series(data, name)
    data = _filter_by_date_range(data, start_date, end_date)
    if not _has_valid_values(data, name):
        raise ValueError(f"Treasury yield curve returned no usable values for {source_id}.")

    save_raw_data(data, cache_file or RAW_DATA_DIR / f"{name}_Treasury_{column.replace(' ', '')}.csv")
    data.attrs["actual_source"] = f"treasury_yield_curve:{column}"
    return data


def fetch_nyfed_rate_series(
    source_id: str,
    name: str,
    start_date: str,
    end_date: str,
    cache_file: str | Path | None = None,
) -> pd.DataFrame:
    """Download NY Fed reference rates such as EFFR."""
    _ensure_data_directories()
    rate_type = str(source_id or "EFFR").strip().upper()
    start_timestamp, end_timestamp = _validate_date_range(start_date, end_date)
    params = urlencode(
        {
            "startDate": start_timestamp.strftime("%Y-%m-%d"),
            "endDate": end_timestamp.strftime("%Y-%m-%d"),
        }
    )
    url = f"{NYFED_EFFR_API_URL}?{params}"
    payload = json.loads(
        _safe_http_get(url, timeout=25, retries=2).decode("utf-8", errors="ignore")
    )
    rows = [
        row
        for row in payload.get("refRates", [])
        if str(row.get("type", "")).upper() == rate_type
    ]
    if not rows:
        raise ValueError(f"NY Fed returned no {rate_type} observations.")

    raw = pd.DataFrame(rows)
    data = pd.DataFrame(
        {
            "Date": pd.to_datetime(raw.get("effectiveDate"), errors="coerce"),
            name: pd.to_numeric(raw.get("percentRate"), errors="coerce"),
        }
    )
    data = _prepare_two_column_series(data, name)
    data = _filter_by_date_range(data, start_date, end_date)
    if not _has_valid_values(data, name):
        raise ValueError(f"NY Fed returned no usable {rate_type} values.")

    save_raw_data(data, cache_file or RAW_DATA_DIR / f"{name}_NYFed_{rate_type}.csv")
    data.attrs["actual_source"] = f"nyfed_rate:{rate_type}"
    return data


def fetch_policy_uncertainty_daily_series(
    source_id: str,
    name: str,
    start_date: str,
    end_date: str,
    cache_file: str | Path | None = None,
) -> pd.DataFrame:
    """Download a daily policyuncertainty.com index such as EPU, TPU, or EMV."""
    _ensure_data_directories()
    source_key = str(source_id or "US").strip().upper()
    source_config = POLICY_UNCERTAINTY_DAILY_SOURCES.get(source_key)
    if source_config is None:
        raise ValueError(f"Unsupported policyuncertainty.com daily source: {source_id}")
    url = source_config["url"]
    value_column = source_config["value_column"]
    try:
        import requests
    except ImportError:
        raw_text = _safe_http_get(url, timeout=25, retries=2).decode(
            "utf-8",
            errors="ignore",
        )
    else:
        response = requests.get(
            url,
            headers={"User-Agent": "Mozilla/5.0", "Accept": "text/csv,*/*"},
            timeout=25,
        )
        response.raise_for_status()
        raw_text = response.text

    raw = pd.read_csv(StringIO(raw_text))
    required = {"day", "month", "year", value_column}
    if not required.issubset(set(raw.columns)):
        raise ValueError("Policy uncertainty daily CSV has an unexpected schema.")

    data = pd.DataFrame(
        {
            "Date": pd.to_datetime(
                {
                    "year": pd.to_numeric(raw["year"], errors="coerce"),
                    "month": pd.to_numeric(raw["month"], errors="coerce"),
                    "day": pd.to_numeric(raw["day"], errors="coerce"),
                },
                errors="coerce",
            ),
            name: pd.to_numeric(raw[value_column], errors="coerce"),
        }
    )
    data = _prepare_two_column_series(data, name)
    data = _filter_by_date_range(data, start_date, end_date)
    if not _has_valid_values(data, name):
        raise ValueError(f"Policy uncertainty daily CSV returned no usable values for {source_key}.")

    save_raw_data(data, cache_file or RAW_DATA_DIR / f"{name}_PolicyUncertaintyDaily.csv")
    data.attrs["actual_source"] = source_config["actual_source"]
    return data


def _extract_yfinance_close(data: pd.DataFrame, ticker: str) -> pd.Series:
    'Yahoo Finance returned no usable daily data.'
    if isinstance(data.columns, pd.MultiIndex):
        for level in range(data.columns.nlevels):
            if "Close" not in data.columns.get_level_values(level):
                continue
            close_data = data.xs("Close", axis=1, level=level)
            if isinstance(close_data, pd.DataFrame):
                if ticker in close_data.columns:
                    return close_data[ticker]
                return close_data.iloc[:, 0]
            return close_data
        raise ValueError(f"yfinance data has no Close column for {ticker}.")

    if "Close" in data.columns:
        return data["Close"]
    if "Adj Close" in data.columns:
        return data["Adj Close"]

    raise ValueError(f"yfinance data has no Close or Adj Close column for {ticker}.")


def _download_yfinance_series(
    ticker: str,
    name: str,
    start_date: str,
    end_date: str,
    retries: int = 1,
    retry_wait_seconds: int = 2,
) -> pd.DataFrame:
    'Yahoo Finance returned no usable daily data.'
    try:
        import yfinance as yf
    except ImportError as exc:
        raise ImportError('Missing yfinance. Please run: pip install -r requirements.txt') from exc

    start_timestamp, end_timestamp = _validate_date_range(start_date, end_date)
    errors: list[str] = []
    end_exclusive = end_timestamp + pd.Timedelta(days=1)

    for attempt in range(1, retries + 1):
        try:
            raw_data = yf.download(
                ticker,
                start=start_timestamp.strftime("%Y-%m-%d"),
                end=end_exclusive.strftime("%Y-%m-%d"),
                progress=False,
                auto_adjust=False,
                threads=False,
            )
            if raw_data.empty:
                raise ValueError('Yahoo Finance returned no usable daily data.')

            close_series = _extract_yfinance_close(raw_data, ticker)
            close_series.name = name
            data = close_series.reset_index()
            data.columns = ["Date", name]
            prepared = _prepare_two_column_series(data, name)
            prepared.attrs["actual_source"] = f"yfinance:{ticker}"
            return prepared
        except Exception as exc:  # noqa: BLE001 - continue fallback handling.
            errors.append(f"attempt {attempt} failed: {_safe_exception_text(exc)}")
            if attempt < retries:
                warnings.warn(
                    f"{name} / {ticker} download failed; retrying in {retry_wait_seconds} seconds. "
                    f"Reason: {_safe_exception_text(exc)}"
                )
                time.sleep(retry_wait_seconds)

    warnings.warn(
        f"{name} / {ticker} yfinance package retries failed. "
        "Trying Yahoo Finance chart endpoint as an automatic Yahoo fallback."
    )
    try:
        return _download_yahoo_chart_series(ticker, name, start_date, end_date)
    except Exception as chart_exc:  # noqa: BLE001 - caller will continue fallback sources.
        errors.append(f"Yahoo chart fallback failed: {_safe_exception_text(chart_exc)}")
        raise RuntimeError(" | ".join(errors)) from chart_exc


def _download_yahoo_chart_series(
    ticker: str,
    name: str,
    start_date: str,
    end_date: str,
) -> pd.DataFrame:
    """Download daily close values from Yahoo Finance's chart endpoint."""
    start_timestamp, end_timestamp = _validate_date_range(start_date, end_date)
    period1 = int(start_timestamp.tz_localize("UTC").timestamp())
    period2 = int((end_timestamp + pd.Timedelta(days=1)).tz_localize("UTC").timestamp())
    params = urlencode(
        {
            "period1": period1,
            "period2": period2,
            "interval": "1d",
            "events": "history",
            "includeAdjustedClose": "true",
        }
    )
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{quote(ticker, safe='')}?{params}"
    payload = json.loads(_safe_http_get(url).decode("utf-8"))

    chart = payload.get("chart", {})
    error = chart.get("error")
    if error:
        raise ValueError(error)

    results = chart.get("result") or []
    if not results:
        raise ValueError("Yahoo chart endpoint returned no result.")

    result = results[0]
    timestamps = result.get("timestamp") or []
    quote_rows = result.get("indicators", {}).get("quote") or []
    if not timestamps or not quote_rows:
        raise ValueError("Yahoo chart endpoint returned no timestamp or quote data.")

    close_values = quote_rows[0].get("close")
    if close_values is None:
        raise ValueError("Yahoo chart endpoint returned no close values.")

    data = pd.DataFrame(
        {
            "Date": pd.to_datetime(timestamps, unit="s", utc=True)
            .tz_convert(None)
            .normalize(),
            name: close_values,
        }
    )
    data = _prepare_two_column_series(data, name)
    data = _filter_by_date_range(data, start_date, end_date)
    if not _has_valid_values(data, name):
        raise ValueError("Yahoo chart endpoint returned no valid close values.")

    data.attrs["actual_source"] = f"yahoo_chart:{ticker}"
    return data


def fetch_yfinance_series(
    ticker: str,
    name: str,
    start_date: str,
    end_date: str,
    retries: int = 3,
    retry_wait_seconds: int = 10,
) -> pd.DataFrame:
    'Yahoo Finance returned no usable daily data.'
    _ensure_data_directories()
    try:
        data = _download_yfinance_series(
            ticker,
            name,
            start_date,
            end_date,
            retries=retries,
            retry_wait_seconds=retry_wait_seconds,
        )
        save_raw_data(data, RAW_CACHE_FILES.get(name, RAW_DATA_DIR / f"{name}.csv"))
        return data
    except Exception as exc:  # noqa: BLE001 - continue fallback handling.
        warnings.warn(
            f"{name} / {ticker} yfinance failed; trying the cache file. "
            f"Reason: {_safe_exception_text(exc)}"
        )
        return _load_cache_file(
            RAW_CACHE_FILES.get(name, RAW_DATA_DIR / f"{name}.csv"),
            name,
            start_date,
            end_date,
            ticker,
        )


def fetch_stooq_series(
    symbol: str,
    name: str,
    start_date: str,
    end_date: str,
    cache_file: str | Path | None = None,
) -> pd.DataFrame:
    'Stooq returned no usable daily data.'
    _ensure_data_directories()
    start_timestamp, end_timestamp = _validate_date_range(start_date, end_date)
    d1 = start_timestamp.strftime("%Y%m%d")
    d2 = end_timestamp.strftime("%Y%m%d")
    url = f"https://stooq.com/q/d/l/?s={symbol.lower()}&d1={d1}&d2={d2}&i=d"

    try:
        content = _safe_http_get(url).decode("utf-8", errors="ignore").strip()
        if not content:
            raise ValueError('Stooq returned no usable daily data.')
        if "Get your apikey" in content:
            raise ValueError('Stooq returned no usable daily data.')

        raw_data = pd.read_csv(StringIO(content))
        if raw_data.empty:
            raise ValueError('Stooq returned no usable daily data.')

        data = _standardise_market_data(raw_data, name, symbol)
        data = _filter_by_date_range(data, start_date, end_date)
        if not _has_valid_values(data, name):
            raise ValueError('Stooq returned no usable daily data.')

        if cache_file:
            save_raw_data(data, cache_file)
        return data
    except Exception as exc:  # noqa: BLE001 - continue fallback handling.
        warnings.warn(f"{name} / {symbol} Stooq download failed. Reason: {_safe_exception_text(exc)}")
        return _empty_market_frame(name, start_date, end_date)


def fetch_series_with_fallback(
    name: str,
    sources: list[dict[str, str]],
    start_date: str,
    end_date: str,
    cache_file: str | Path,
    force_refresh: bool = False,
) -> pd.DataFrame:
    'Market data download and preparation helper.'
    _ensure_data_directories()
    errors: list[str] = []
    ordered_sources = _prioritise_api_sources(sources)

    for source_index, source in enumerate(ordered_sources):
        source_type = source["type"].lower()
        source_id = source["id"]
        source_label = _source_label(source_type, source_id)
        has_later_non_fred_source = any(
            str(later_source.get("type", "")).lower() not in {"fred", "fred_csv"}
            for later_source in ordered_sources[source_index + 1 :]
        )

        try:
            if source_type == "eia":
                data = fetch_eia_series(source_id, name, start_date, end_date, cache_file)
            elif source_type == "fred":
                data = fetch_fred_series(
                    source_id,
                    name,
                    start_date,
                    end_date,
                    cache_file,
                    allow_public_csv=not has_later_non_fred_source,
                )
            elif source_type == "fred_csv":
                data = fetch_fred_csv_series(source_id, name, start_date, end_date, cache_file)
            elif source_type == "yfinance":
                data = _download_yfinance_series(source_id, name, start_date, end_date)
            elif source_type == "stooq":
                data = fetch_stooq_series(source_id, name, start_date, end_date, cache_file)
            elif source_type == "treasury_yield_curve":
                data = fetch_treasury_yield_curve_series(source_id, name, start_date, end_date, cache_file)
            elif source_type == "nyfed_rate":
                data = fetch_nyfed_rate_series(source_id, name, start_date, end_date, cache_file)
            elif source_type == "policy_uncertainty_daily":
                data = fetch_policy_uncertainty_daily_series(source_id, name, start_date, end_date, cache_file)
            else:
                raise ValueError(f"Unknown data source type: {source_type}")

            if _has_valid_values(data, name):
                is_fresh, freshness_note = _is_fresh_enough(
                    data,
                    name,
                    end_date,
                    max_lag_days=_freshness_lag_days_for_variable(name),
                )
                if not is_fresh:
                    errors.append(f"{source_label} stale data: {freshness_note}")
                    warnings.warn(
                        f"{name} automatic source {source_label} returned stale data; trying the next source. "
                        f"Details: {freshness_note}"
                    )
                    continue

                save_raw_data(data, cache_file)
                actual_source = str(data.attrs.get("actual_source", source_label))
                LAST_SOURCE_USED[name] = actual_source
                if source_label == "fred_csv:DCOILWTICO":
                    LAST_SOURCE_NOTES[name] = (
                        "FRED DCOILWTICO daily WTI spot price is used as a no-key fallback "
                        "when futures sources are stale, unavailable, or rate-limited."
                    )
                elif name == "Brent" and (
                    source_label in {"fred:DCOILBRENTEU", "fred_csv:DCOILBRENTEU"}
                    or actual_source in {
                        "fred_api:DCOILBRENTEU",
                        "fredapi:DCOILBRENTEU",
                        "fred_csv:DCOILBRENTEU",
                    }
                ):
                    LAST_SOURCE_NOTES[name] = (
                        "FRED DCOILBRENTEU daily Brent spot price is used as an API-capable "
                        "fallback when futures sources are unavailable or rate-limited."
                    )
                elif name == "Gold" and source_label.startswith("fred:GOLD"):
                    LAST_SOURCE_NOTES[name] = f"FRED {source_id} is used as a proxy for gold futures."
                elif name == "WTI" and source_label == "eia:RCLC1":
                    LAST_SOURCE_NOTES[name] = "EIA RCLC1 used as WTI futures target; yfinance was not called."
                elif actual_source.startswith("yahoo_chart:"):
                    LAST_SOURCE_NOTES[name] = (
                        "Downloaded via Yahoo Finance chart endpoint after yfinance package retries failed."
                    )
                elif actual_source.startswith("treasury_yield_curve:"):
                    LAST_SOURCE_NOTES[name] = "Downloaded from the U.S. Treasury daily yield curve table."
                elif actual_source.startswith("nyfed_rate:"):
                    LAST_SOURCE_NOTES[name] = "Downloaded from the New York Fed reference-rate API."
                elif actual_source.startswith("policy_uncertainty_daily:"):
                    LAST_SOURCE_NOTES[name] = "Downloaded from an official policyuncertainty.com daily CSV."
                else:
                    LAST_SOURCE_NOTES[name] = ""
                return data

            errors.append(f"{source_label} returned empty or all-missing data")
        except Exception as exc:  # noqa: BLE001 - continue fallback handling.
            error_text = _safe_exception_text(exc)
            errors.append(f"{source_label} failed: {error_text}")
            warnings.warn(f"{name} automatic source {source_label} failed: {error_text}")

    error_detail = " | ".join(errors)
    warnings.warn(
        f"{name} all automatic sources failed; trying the cache file. Details: {error_detail}"
    )
    if force_refresh:
        warnings.warn(
            f"{name} force_refresh=True: online sources were retried before cache fallback."
        )
    cached_data = _load_cache_file(cache_file, name, start_date, end_date)
    if _has_valid_values(cached_data, name):
        is_fresh, freshness_note = _is_fresh_enough(
            cached_data,
            name,
            end_date,
            max_lag_days=_freshness_lag_days_for_variable(name),
        )
        if not is_fresh:
            warnings.warn(
                f"{name} cached data is stale; keeping an empty series or using a local fallback. Details: {freshness_note}"
            )
            LAST_SOURCE_USED[name] = "outdated"
            LAST_SOURCE_NOTES[name] = "Cached data was available but stale. " + freshness_note
            return _empty_market_frame(name, start_date, end_date)

        LAST_SOURCE_USED[name] = f"cache:{Path(cache_file).name}"
        LAST_SOURCE_NOTES[name] = (
            "Loaded from existing cache after automatic sources failed. "
            f"Failure details: {error_detail}"
        ).strip()
        return cached_data

    LAST_SOURCE_USED[name] = "empty"
    LAST_SOURCE_NOTES[name] = (
        "All automatic sources and cache failed. Details: " + error_detail
    )
    return cached_data


def _standardise_gprd_data(raw_data: pd.DataFrame) -> pd.DataFrame:
    'GPRD data was unavailable. Use a local GPRD file if the official download cannot be reached.'
    data = raw_data.copy()
    data.columns = [str(column).strip() for column in data.columns]

    date_column = _find_column_case_insensitive(data.columns.tolist(), ["Date", "date"])
    if not date_column:
        date_column = _find_column_case_insensitive(data.columns.tolist(), ["DAY", "day"])

    gprd_column = _find_column_case_insensitive(data.columns.tolist(), ["GPRD"])
    if not date_column or not gprd_column:
        raise ValueError('GPRD data was unavailable. Use a local GPRD file if the official download cannot be reached.')

    if date_column.lower() == "day":
        numeric_dates = pd.to_numeric(data[date_column], errors="coerce")
        date_values = pd.to_datetime(
            numeric_dates.astype("Int64").astype(str),
            format="%Y%m%d",
            errors="coerce",
        )
    else:
        date_values = pd.to_datetime(data[date_column], errors="coerce")

    gprd_data = pd.DataFrame(
        {
            "Date": date_values,
            "GPRD": pd.to_numeric(data[gprd_column], errors="coerce"),
        }
    )
    return _prepare_two_column_series(gprd_data, "GPRD")


def _discover_gprd_download_urls() -> list[str]:
    """Return official daily GPRD download URLs.

    The fixed official daily file is used first to avoid slow page scraping on
    unstable networks. Page discovery is available only as an explicit debug
    fallback.
    """
    urls = [GPRD_DAILY_RECENT_URL]
    discover_links = str(os.getenv("DISCOVER_GPRD_LINKS", "")).strip().lower() in {
        "1",
        "true",
        "yes",
    }
    if not discover_links:
        return urls

    try:
        html = _safe_http_get(GPRD_OFFICIAL_PAGE_URL, timeout=8, retries=1).decode("utf-8", errors="ignore")
    except Exception as exc:  # noqa: BLE001 - continue fallback handling.
        warnings.warn(
            "GPR official page could not be read; trying the fixed download URL. "
            f"Reason: {_safe_exception_text(exc)}"
        )
        return urls

    hrefs = re.findall(r"href=[\"']([^\"']+)[\"']", html, flags=re.IGNORECASE)
    for href in hrefs:
        lower_href = href.lower()
        if "ai" in lower_href:
            continue
        if "data_gpr_daily_recent" not in lower_href:
            continue
        if not lower_href.endswith((".xls", ".xlsx", ".csv")):
            continue
        urls.insert(0, urljoin(GPRD_OFFICIAL_PAGE_URL, href))

    unique_urls: list[str] = []
    for url in urls:
        if url not in unique_urls:
            unique_urls.append(url)
    return unique_urls


def _gprd_raw_path_from_url(url: str) -> Path:
    'Market data download and preparation helper.'
    suffix = Path(urlparse(url).path).suffix.lower() or ".xls"
    return RAW_DATA_DIR / f"gprd_auto_download{suffix}"


def _empty_gprd_frame() -> pd.DataFrame:
    'GPRD data was unavailable. Use a local GPRD file if the official download cannot be reached.'
    return pd.DataFrame(
        {
            "Date": pd.Series(dtype="datetime64[ns]"),
            "GPRD": pd.Series(dtype="float64"),
        }
    )


def _load_gprd_cache(
    start_date: str | pd.Timestamp,
    end_date: str | pd.Timestamp,
) -> pd.DataFrame:
    'GPRD data was unavailable. Use a local GPRD file if the official download cannot be reached.'
    candidates = sorted(RAW_DATA_DIR.glob("gprd_auto_download.*"))
    for cache_path in candidates:
        try:
            raw_data = _read_table_file(cache_path)
            gprd_data = _standardise_gprd_data(raw_data)
            gprd_data = _filter_by_date_range(gprd_data, start_date, end_date)
            if _has_valid_values(gprd_data, "GPRD"):
                warnings.warn(f"GPRD loaded from cache file: {cache_path}")
                return gprd_data
        except Exception as exc:  # noqa: BLE001 - continue fallback handling.
            warnings.warn(
                f"GPRD cache file could not be read: {cache_path}; "
                f"reason: {_safe_exception_text(exc)}"
            )

    return _empty_gprd_frame()


def fetch_gprd_auto(start_date: str, end_date: str) -> pd.DataFrame:
    """Download the traditional official daily GPRD series."""
    _ensure_data_directories()
    start_timestamp, end_timestamp = _validate_date_range(start_date, end_date)

    errors: list[str] = []
    for url in _discover_gprd_download_urls():
        raw_path = _gprd_raw_path_from_url(url)
        try:
            _download_file(url, raw_path, timeout=12, retries=2)
            raw_data = _read_table_file(raw_path)
            gprd_data = _standardise_gprd_data(raw_data)
            gprd_data = gprd_data[
                (gprd_data["Date"] >= start_timestamp)
                & (gprd_data["Date"] <= end_timestamp)
            ].reset_index(drop=True)
            if not _has_valid_values(gprd_data, "GPRD"):
                raise ValueError("Official daily GPRD file contained no usable GPRD values in the requested range.")

            gprd_data.to_excel(PROCESSED_GPRD_PATH, index=False)
            gprd_data.attrs["actual_source"] = "official_gprd_daily"
            return gprd_data
        except Exception as exc:  # noqa: BLE001 - continue fallback handling.
            errors.append(f"{url}: {_safe_exception_text(exc)}")

    warnings.warn(
        "GPRD data was unavailable. Use a local GPRD file if the official download cannot be reached. "
        + " | ".join(errors)
    )
    return _empty_gprd_frame()


def load_gprd_file(file_path: str | Path) -> pd.DataFrame:
    'GPRD data was unavailable. Use a local GPRD file if the official download cannot be reached.'
    _ensure_data_directories()
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"GPRD file not found: {path}")

    raw_data = _read_table_file(path)
    gprd_data = _standardise_gprd_data(raw_data)
    save_raw_data(gprd_data, RAW_DATA_DIR / "GPRD_uploaded.csv")
    return gprd_data


def load_local_market_file(file_path: str | Path, name: str) -> pd.DataFrame:
    'Market data download and preparation helper.'
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"{name} local file not found: {path}")

    raw_data = _read_table_file(path)
    data = _standardise_market_data(raw_data, name, YFINANCE_SERIES.get(name))
    save_raw_data(data, RAW_DATA_DIR / f"{name}_local_uploaded.csv")
    return data


def fetch_wti_data(start_date: str, end_date: str) -> pd.DataFrame:
    'Market data download and preparation helper.'
    return fetch_series_with_fallback(
        "WTI",
        SERIES_SOURCES["WTI"],
        start_date,
        end_date,
        RAW_CACHE_FILES["WTI"],
    )


def _write_data_source_log(
    market_data: pd.DataFrame,
    start_date: str | pd.Timestamp,
    end_date: str | pd.Timestamp,
) -> pd.DataFrame:
    'Market data download and preparation helper.'
    rows = []
    for variable in MARKET_COLUMNS:
        if variable == "Date":
            continue

        actual_source = LAST_SOURCE_USED.get(variable, "empty")
        is_proxy = (
            (variable == "Gold" and actual_source == "fred:GOLDAMGBD228NLBM")
            or (variable == "WTI" and actual_source == "fred_csv:DCOILWTICO")
            or (
                variable == "Brent"
                and actual_source in {
                    "fred:DCOILBRENTEU",
                    "fred_api:DCOILBRENTEU",
                    "fredapi:DCOILBRENTEU",
                    "fred_csv:DCOILBRENTEU",
                }
            )
        )
        rows.append(
            {
                "Variable": variable,
                "RequestedType": REQUESTED_TYPES.get(variable, ""),
                "ActualSource": actual_source,
                "IsProxy": is_proxy,
                "StartDate": pd.to_datetime(start_date).normalize(),
                "EndDate": pd.to_datetime(end_date).normalize(),
                "MissingCount": int(market_data[variable].isna().sum()),
                "Note": LAST_SOURCE_NOTES.get(variable, ""),
            }
        )

    log_data = pd.DataFrame(rows)
    DATA_SOURCE_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    log_data.to_excel(DATA_SOURCE_LOG_PATH, index=False)
    return log_data


def build_market_dataset(
    start_date: str,
    end_date: str,
    gprd_file: str | Path | None = None,
    auto_gprd: bool = True,
    local_files: dict[str, str | Path] | None = None,
    force_refresh: bool = False,
    cache_first: bool = False,
    **kwargs: Any,
) -> pd.DataFrame:
    'Market data download and preparation helper.'
    _ensure_data_directories()
    start_timestamp, end_timestamp = _validate_date_range(start_date, end_date)
    local_files = local_files or {}

    LAST_SOURCE_USED.clear()
    LAST_SOURCE_NOTES.clear()

    datasets: list[pd.DataFrame] = []
    for name, sources in SERIES_SOURCES.items():
        data: pd.DataFrame | None = None
        if cache_first:
            cached_data = _load_cache_file(RAW_CACHE_FILES[name], name, start_date, end_date)
            if _has_valid_values(cached_data, name):
                is_fresh, freshness_note = _is_fresh_enough(
                    cached_data,
                    name,
                    end_date,
                    max_lag_days=_freshness_lag_days_for_variable(name),
                )
                if is_fresh:
                    data = cached_data
                    LAST_SOURCE_USED[name] = f"cache:{RAW_CACHE_FILES[name].name}"
                    LAST_SOURCE_NOTES[name] = (
                        "Loaded from local raw cache before online sources because cache_first=True."
                    )
                else:
                    warnings.warn(
                        f"{name} cache_first=True but cache is stale; online sources will be tried. "
                        f"Details: {freshness_note}"
                    )

        if data is None:
            data = fetch_series_with_fallback(
                name,
                sources,
                start_date,
                end_date,
                RAW_CACHE_FILES[name],
                force_refresh=force_refresh,
            )

        # NOTE: fallback behavior is intentional.
        if not _has_valid_values(data, name) and name in local_files:
            try:
                local_data = load_local_market_file(local_files[name], name)
                local_data = _filter_by_date_range(local_data, start_date, end_date)
                if _has_valid_values(local_data, name):
                    data = local_data
                    LAST_SOURCE_USED[name] = f"local:{local_files[name]}"
                    LAST_SOURCE_NOTES[name] = "Loaded from local_files fallback."
                else:
                    warnings.warn(f"{name} local fallback file has no valid data in the requested date range.")
            except Exception as exc:  # noqa: BLE001 - continue fallback handling.
                warnings.warn(
                    f"{name} local fallback file could not be read; keeping an empty series. "
                    f"Reason: {_safe_exception_text(exc)}"
                )

        datasets.append(data)

    market_data = reduce(
        lambda left, right: pd.merge(left, right, on="Date", how="outer"),
        datasets,
    )

    gprd_data = _empty_gprd_frame()
    if auto_gprd:
        gprd_data = fetch_gprd_auto(start_date, end_date)
        if _has_valid_values(gprd_data, "GPRD"):
            LAST_SOURCE_USED["GPRD"] = "official_gprd_daily"
            LAST_SOURCE_NOTES["GPRD"] = "Traditional Caldara-Iacoviello GPR daily index; AI-GPR is not used."

    if gprd_data.empty:
        gprd_data = _load_gprd_cache(start_date, end_date)
        if _has_valid_values(gprd_data, "GPRD"):
            LAST_SOURCE_USED["GPRD"] = "cache:gprd_auto_download"
            LAST_SOURCE_NOTES["GPRD"] = "Loaded from cached traditional GPRD file."

    if gprd_data.empty and gprd_file:
        try:
            gprd_data = load_gprd_file(gprd_file)
            gprd_data = _filter_by_date_range(gprd_data, start_date, end_date)
            if _has_valid_values(gprd_data, "GPRD"):
                LAST_SOURCE_USED["GPRD"] = f"local:{gprd_file}"
                LAST_SOURCE_NOTES["GPRD"] = "Loaded from local GPRD fallback file."
        except Exception as exc:  # noqa: BLE001 - continue fallback handling.
            warnings.warn(
                "GPRD local file could not be read; keeping an empty series. "
                f"Reason: {_safe_exception_text(exc)}"
            )
            gprd_data = _empty_gprd_frame()

    if gprd_data.empty:
        LAST_SOURCE_USED["GPRD"] = "empty"
        LAST_SOURCE_NOTES["GPRD"] = "Automatic download, cache, and local fallback did not provide GPRD."
        if auto_gprd:
            raise ValueError(
                "GPRD is required for this analysis, but the official daily GPRD download did not "
                "produce usable values. Check the internet connection or upload a local GPRD file."
            )
        market_data["GPRD"] = pd.NA
    else:
        market_data = market_data.merge(gprd_data, on="Date", how="outer")

    market_data = _normalise_date_column(market_data)
    market_data = market_data.dropna(subset=["Date"])
    market_data = market_data[
        (market_data["Date"] >= start_timestamp)
        & (market_data["Date"] <= end_timestamp)
    ]

    # NOTE: fallback behavior is intentional.
    market_data = market_data.drop_duplicates(subset=["Date"], keep="last")
    market_data = market_data.sort_values("Date").reset_index(drop=True)

    for column in MARKET_COLUMNS:
        if column not in market_data.columns:
            market_data[column] = pd.NA

    market_data = market_data[MARKET_COLUMNS]
    wti_fresh, wti_freshness_note = _is_fresh_enough(market_data, "WTI", end_date)
    if not wti_fresh:
        LAST_SOURCE_USED["WTI"] = "outdated"
        LAST_SOURCE_NOTES["WTI"] = (
            "WTI data is outdated or unavailable. " + wti_freshness_note
        )
    market_data.to_excel(PROCESSED_MARKET_DATA_PATH, index=False)
    _write_data_source_log(market_data, start_date, end_date)

    return market_data


def save_raw_data(data: pd.DataFrame, output_path: str | Path, **kwargs: Any) -> None:
    'Market data download and preparation helper.'
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data.to_csv(path, index=False, **kwargs)
