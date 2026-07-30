"""Search FRED/EIA catalog metadata and build request-local registry entries."""

from __future__ import annotations

from collections import OrderedDict
import re
from typing import Any

import pandas as pd
import requests

from src.data_fetcher import _get_eia_api_key, _get_fred_api_key
from src.quick_analysis import variable_economic_category


FRED_SEARCH_URL = "https://api.stlouisfed.org/fred/series/search"
EIA_API_ROOT = "https://api.eia.gov/v2"

# These are official leaf datasets with a ``series`` facet. Selecting a series
# facet produces one univariate time series without silently aggregating areas or
# products. Users can still enter another official leaf route in the UI.
EIA_DATASET_ROUTES: "OrderedDict[str, dict[str, str]]" = OrderedDict(
    [
        ("petroleum/pri/spt", {"label_en": "Petroleum spot prices", "label_zh": "石油现货价格"}),
        ("petroleum/pri/fut", {"label_en": "Petroleum futures prices", "label_zh": "石油期货价格"}),
        ("petroleum/stoc/wstk", {"label_en": "Weekly petroleum stocks", "label_zh": "石油周度库存"}),
        ("petroleum/cons/wpsup", {"label_en": "Weekly petroleum supply and demand", "label_zh": "石油周度供需"}),
        ("natural-gas/pri/fut", {"label_en": "Natural-gas spot and futures prices", "label_zh": "天然气现货与期货价格"}),
        ("natural-gas/stor/wkly", {"label_en": "Weekly natural-gas storage", "label_zh": "天然气周度库存"}),
        ("natural-gas/cons/sum", {"label_en": "Natural-gas consumption", "label_zh": "天然气消费"}),
    ]
)


def _response_json(url: str, params: list[tuple[str, str]] | dict[str, Any]) -> dict[str, Any]:
    response = requests.get(url, params=params, timeout=30)
    response.raise_for_status()
    payload = response.json()
    if payload.get("error"):
        message = str(payload["error"].get("message") or payload["error"])
        raise RuntimeError(message)
    return payload


def search_fred_series(query: str, limit: int = 30) -> list[dict[str, Any]]:
    """Return official FRED series-search results normalized for the UI."""
    query = str(query or "").strip()
    if not query:
        return []
    payload = _response_json(
        FRED_SEARCH_URL,
        {
            "api_key": _get_fred_api_key(),
            "file_type": "json",
            "search_text": query,
            "limit": max(1, min(int(limit), 100)),
            "order_by": "search_rank",
        },
    )
    results: list[dict[str, Any]] = []
    for series in payload.get("seriess", []):
        series_id = str(series.get("id", "")).strip()
        title = str(series.get("title", series_id)).strip()
        if not series_id:
            continue
        metadata = {"title": title, "description": str(series.get("notes", ""))}
        results.append(
            {
                "source": "FRED",
                "series_id": series_id,
                "title": title,
                "frequency": str(series.get("frequency_short") or series.get("frequency") or ""),
                "units": str(series.get("units_short") or series.get("units") or ""),
                "start": str(series.get("observation_start", "")),
                "end": str(series.get("observation_end", "")),
                "description": str(series.get("notes", "")),
                "economic_category": variable_economic_category(series_id, metadata),
            }
        )
    return results


def search_eia_series(
    query: str,
    route: str,
    limit: int = 60,
) -> list[dict[str, Any]]:
    """Search named series inside one official EIA v2 leaf dataset."""
    query = str(query or "").strip().lower()
    route = str(route or "").strip().strip("/")
    if not query or not route or not re.fullmatch(r"[A-Za-z0-9_-]+(?:/[A-Za-z0-9_-]+)*", route):
        return []
    api_key = _get_eia_api_key()
    metadata_payload = _response_json(f"{EIA_API_ROOT}/{route}/", {"api_key": api_key})
    metadata = metadata_payload.get("response", {})
    facet_ids = [str(item.get("id", "")) for item in metadata.get("facets", [])]
    if "series" not in facet_ids:
        raise ValueError(
            "This EIA route does not expose a named series catalog. Choose a leaf route with a series facet."
        )
    facet_values: list[dict[str, Any]] = []
    while True:
        facet_payload = _response_json(
            f"{EIA_API_ROOT}/{route}/facet/series/",
            {"api_key": api_key, "offset": len(facet_values), "length": 5000},
        )
        facet_response = facet_payload.get("response", {})
        page = facet_response.get("facets", [])
        facet_values.extend(page)
        total = int(facet_response.get("totalFacets", len(facet_values)) or len(facet_values))
        if not page or len(facet_values) >= total:
            break
    dataset = EIA_DATASET_ROUTES.get(route, {})
    dataset_label = dataset.get("label_en", route)
    frequencies = metadata.get("frequency", [])
    frequency_ids = [str(item.get("id", "")) for item in frequencies if item.get("id")]
    default_frequency = str(metadata.get("defaultFrequency") or (frequency_ids[0] if frequency_ids else ""))
    start = str(metadata.get("startPeriod", ""))
    end = str(metadata.get("endPeriod", ""))
    results: list[dict[str, Any]] = []
    for series in facet_values:
        series_id = str(series.get("id", "")).strip()
        title = str(series.get("name", series_id)).strip()
        searchable = f"{series_id} {title} {dataset_label}".lower()
        if query not in searchable and not all(token in searchable for token in query.split()):
            continue
        item_metadata = {"title": title, "description": dataset_label}
        results.append(
            {
                "source": "EIA",
                "series_id": series_id,
                "title": title,
                "route": route,
                "data_field": "value",
                "frequency": default_frequency,
                "available_frequencies": frequency_ids,
                "units": "",
                "start": start,
                "end": end,
                "description": dataset_label,
                "facets": {"series": [series_id]},
                "economic_category": variable_economic_category(series_id, item_metadata),
            }
        )
        if len(results) >= max(1, int(limit)):
            break
    return results


def _safe_variable_name(source: str, series_id: str) -> str:
    safe_id = re.sub(r"[^A-Za-z0-9]+", "_", str(series_id)).strip("_")
    return f"{source.upper()}_{safe_id}"[:80]


def catalog_item_to_registry_entry(item: dict[str, Any]) -> dict[str, Any]:
    """Convert one selected catalog item into a request-local variable entry."""
    source = str(item.get("source", "")).upper()
    series_id = str(item.get("series_id", "")).strip()
    if source not in {"FRED", "EIA"} or not series_id:
        raise ValueError("Catalog item is missing a supported source or series identifier.")
    name = _safe_variable_name(source, series_id)
    title = str(item.get("title") or series_id)
    frequency = str(item.get("frequency") or "Unknown")
    if source == "FRED":
        sources = [{"type": "fred", "id": series_id}]
    else:
        sources = [
            {
                "type": "eia_v2",
                "id": series_id,
                "route": str(item.get("route", "")).strip("/"),
                "data": str(item.get("data_field") or "value"),
                "frequency": frequency,
                "facets": dict(item.get("facets") or {"series": [series_id]}),
            }
        ]
    return {
        "name": name,
        "display_name": title,
        "description": title,
        "auto_download": True,
        "is_proxy": False,
        "frequency": frequency,
        "daily_alignment": "Forward-filled to the daily analysis calendar after official observations.",
        "daily_fill_forward": frequency.lower() not in {"daily", "d"},
        "economic_category": str(item.get("economic_category") or "other_indicators"),
        "sources": sources,
        "cache_file": f"data/raw/variable_pool/{name}.csv",
        "note": f"Added from the official {source} catalog; code {series_id}.",
    }


def fetch_eia_v2_series(
    source: dict[str, Any],
    name: str,
    start_date: str,
    end_date: str,
) -> pd.DataFrame:
    """Download one explicitly faceted EIA v2 series without implicit aggregation."""
    route = str(source.get("route", "")).strip().strip("/")
    data_field = str(source.get("data") or "value")
    frequency = str(source.get("frequency") or "daily")
    facets = source.get("facets") or {}
    if not route or not facets:
        raise ValueError("EIA series needs a leaf route and explicit facet selection.")
    base_params: list[tuple[str, str]] = [
        ("api_key", _get_eia_api_key()),
        ("frequency", frequency),
        ("data[0]", data_field),
        ("start", str(start_date)),
        ("end", str(end_date)),
        ("sort[0][column]", "period"),
        ("sort[0][direction]", "asc"),
    ]
    for facet, values in facets.items():
        for value in values if isinstance(values, list) else [values]:
            base_params.append((f"facets[{facet}][]", str(value)))
    rows: list[dict[str, Any]] = []
    page_size = 5000
    while True:
        params = [
            *base_params,
            ("offset", str(len(rows))),
            ("length", str(page_size)),
        ]
        payload = _response_json(f"{EIA_API_ROOT}/{route}/data/", params)
        response = payload.get("response", {})
        page = response.get("data", [])
        rows.extend(page)
        total = int(response.get("total", len(rows)) or len(rows))
        if not page or len(rows) >= total:
            break
    frame = pd.DataFrame(rows)
    if frame.empty or "period" not in frame or data_field not in frame:
        raise ValueError("EIA returned no observations for this series and date window.")
    frame["Date"] = pd.to_datetime(frame["period"], errors="coerce")
    frame[name] = pd.to_numeric(frame[data_field], errors="coerce")
    frame = frame.dropna(subset=["Date", name]).sort_values("Date")
    if frame["Date"].duplicated().any():
        raise ValueError("EIA selection still contains multiple series per period; refine its facets.")
    return frame[["Date", name]].reset_index(drop=True)
