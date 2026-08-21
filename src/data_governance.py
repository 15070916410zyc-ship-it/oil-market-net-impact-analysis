"""Provider-neutral data discovery, source audit, and frequency conversion.

The application deliberately keeps provider metadata separate from the paper's
economic IMF interpretation.  This module answers three operational questions:

* Is the same provider series registered more than once?
* Which source should be attempted first without changing the variable meaning?
* How should an observed series be displayed at daily or monthly frequency?
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
import re
from typing import Any, Iterable, Mapping

import pandas as pd


SOURCE_POLICIES: dict[str, dict[str, Any]] = {
    "existing_model_ready_column": {"authority": 5.0, "label": "Verified local model data"},
    "exchange_futures_daily": {"authority": 5.0, "label": "Official futures exchange"},
    "eia": {"authority": 5.0, "label": "U.S. EIA"},
    "eia_v2": {"authority": 5.0, "label": "U.S. EIA API v2"},
    "eia_excel": {"authority": 5.0, "label": "U.S. EIA historical file"},
    "treasury_yield_curve": {"authority": 5.0, "label": "U.S. Treasury"},
    "nyfed_rate": {"authority": 5.0, "label": "Federal Reserve Bank of New York"},
    "policy_uncertainty_daily": {"authority": 4.8, "label": "Policy Uncertainty database"},
    "fred": {"authority": 4.8, "label": "FRED"},
    "fred_csv": {"authority": 4.7, "label": "FRED public CSV"},
    "yfinance": {"authority": 3.4, "label": "Yahoo Finance"},
    "stooq": {"authority": 3.0, "label": "Stooq"},
    "sina_main_futures": {"authority": 2.8, "label": "Sina Finance"},
    "local_upload": {"authority": 2.5, "label": "User upload"},
}

PRICE_HINTS = (
    "price",
    "close",
    "settlement",
    "yield",
    "rate",
    "index",
    "wti",
    "brent",
    "gold",
    "gasoline",
    "heatingoil",
    "copper",
    "silver",
    "cnyusd",
)
FLOW_HINTS = ("production", "consumption", "supply", "demand", "imports", "exports", "volume")


@dataclass(frozen=True)
class SourceAuditSummary:
    """Registry audit result used by tests, downloads, and the data-center UI."""

    table: pd.DataFrame
    exact_duplicate_count: int
    proxy_fallback_count: int
    variable_count: int


def source_key(source: Mapping[str, Any]) -> tuple[str, str]:
    """Return the exact provider-series identity for duplicate detection."""
    return (
        str(source.get("type", "")).strip().lower(),
        str(source.get("id", "")).strip().upper(),
    )


def source_authority(source_type: str) -> float:
    """Return a transparent authority score, not a data-quality guarantee."""
    return float(SOURCE_POLICIES.get(str(source_type).lower(), {}).get("authority", 2.0))


def source_label(source_type: str) -> str:
    return str(SOURCE_POLICIES.get(str(source_type).lower(), {}).get("label", source_type))


def _looks_like_proxy(entry: Mapping[str, Any], source: Mapping[str, Any]) -> bool:
    note = " ".join(
        str(value or "")
        for value in (entry.get("description"), entry.get("note"), entry.get("is_proxy"))
    ).lower()
    source_type = str(source.get("type", "")).lower()
    source_id = str(source.get("id", "")).upper()
    if "proxy" in note or bool(entry.get("is_proxy")):
        return True
    # These known fallbacks change the economic instrument, even if highly correlated.
    name = str(entry.get("name", ""))
    return (
        (name == "Brent" and source_id == "DCOILBRENTEU")
        or (name == "NaturalGas" and source_type == "yfinance")
        or (name == "DollarIndex" and source_id == "DX=F")
    )


def audit_registry_sources(registry: Iterable[Mapping[str, Any]]) -> SourceAuditSummary:
    """Audit exact duplicates and source roles without deleting useful fallbacks."""
    entries = [dict(entry) for entry in registry]
    occurrences: dict[tuple[str, str], list[str]] = defaultdict(list)
    for entry in entries:
        for source in entry.get("sources", []):
            occurrences[source_key(source)].append(str(entry.get("name", "")))

    rows: list[dict[str, Any]] = []
    proxy_count = 0
    duplicate_keys = {key for key, names in occurrences.items() if len(names) > 1}
    for entry in entries:
        sources = list(entry.get("sources", []))
        for index, source in enumerate(sources):
            key = source_key(source)
            is_proxy = _looks_like_proxy(entry, source)
            proxy_count += int(is_proxy)
            rows.append(
                {
                    "Variable": str(entry.get("name", "")),
                    "SourceType": key[0],
                    "Source": source_label(key[0]),
                    "SeriesID": str(source.get("id", "")),
                    "Role": "Primary" if index == 0 else ("Proxy fallback" if is_proxy else "Fallback"),
                    "AuthorityScore": source_authority(key[0]),
                    "ExactDuplicate": key in duplicate_keys,
                    "DefinitionWarning": is_proxy,
                    "AutoDownload": bool(entry.get("auto_download", False)),
                    "Frequency": str(entry.get("frequency", "")),
                }
            )
    table = pd.DataFrame(rows)
    if not table.empty:
        table = table.sort_values(
            ["Variable", "Role", "AuthorityScore"],
            ascending=[True, True, False],
        ).reset_index(drop=True)
    return SourceAuditSummary(
        table=table,
        exact_duplicate_count=len(duplicate_keys),
        proxy_fallback_count=proxy_count,
        variable_count=len(entries),
    )


def deduplicate_catalog_results(items: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Remove exact catalog duplicates while keeping different definitions visible."""
    best: dict[tuple[str, str], dict[str, Any]] = {}
    for raw in items:
        item = dict(raw)
        key = (str(item.get("source", "")).upper(), str(item.get("series_id", "")).upper())
        if not key[0] or not key[1]:
            continue
        previous = best.get(key)
        if previous is None or len(str(item.get("description", ""))) > len(str(previous.get("description", ""))):
            best[key] = item
    return list(best.values())


def infer_monthly_method(variable: str, metadata: Mapping[str, Any] | None = None) -> str:
    """Choose a defensible monthly display aggregation from variable semantics."""
    metadata = metadata or {}
    text = " ".join(
        [str(variable), str(metadata.get("description", "")), str(metadata.get("units", ""))]
    ).lower()
    if any(hint in text for hint in FLOW_HINTS):
        return "sum"
    if "stock" in text or "inventory" in text:
        return "last"
    if any(hint in text for hint in PRICE_HINTS):
        return "last"
    return "mean"


def aggregate_time_series(
    data: pd.DataFrame,
    frequency: str,
    *,
    methods: Mapping[str, str] | None = None,
    metadata: Mapping[str, Mapping[str, Any]] | None = None,
) -> pd.DataFrame:
    """Return daily observations or semantically aggregated month-end values."""
    if "Date" not in data.columns:
        raise ValueError("Data must contain a Date column.")
    output = data.copy()
    output["Date"] = pd.to_datetime(output["Date"], errors="coerce")
    output = output.dropna(subset=["Date"]).sort_values("Date")
    normalized_frequency = str(frequency).strip().lower()
    if normalized_frequency in {"daily", "d", "日度"}:
        return output.reset_index(drop=True)
    if normalized_frequency not in {"monthly", "m", "月度"}:
        raise ValueError("Frequency must be daily or monthly.")

    method_map: dict[str, str] = {}
    for column in output.columns:
        if column == "Date":
            continue
        requested = (methods or {}).get(column)
        method_map[column] = requested or infer_monthly_method(column, (metadata or {}).get(column))
    numeric = output.set_index("Date")
    for column in numeric.columns:
        numeric[column] = pd.to_numeric(numeric[column], errors="coerce")
    monthly = numeric.resample("ME").agg(method_map).dropna(how="all").reset_index()
    return monthly


def normalize_search_text(value: str) -> str:
    """Normalize bilingual catalog text for simple local filtering."""
    return re.sub(r"[^a-z0-9\u4e00-\u9fff]+", " ", str(value).lower()).strip()
