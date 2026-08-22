from __future__ import annotations

from pathlib import Path

import pandas as pd

from app.data_library import (
    _date_range_error,
    _load_selected_stored_inputs,
    _merge_search_results,
    _registry_entry_for_source,
    _stored_catalog_results,
    _stored_registry_entries,
)
from src.research_store import ResearchStore
from src import variable_pool


def _ui_text(english: str, chinese: str) -> str:
    return chinese


def _entry(name: str = "SavedStocks") -> dict[str, object]:
    return {
        "name": name,
        "display_name": "Saved crude stocks",
        "description": "A saved official test series.",
        "frequency": "weekly",
        "auto_download": False,
        "economic_category": "inventory_refining_products",
        "sources": [
            {"type": "fred", "id": "WRONG"},
            {"type": "eia_v2", "id": "WCESTUS1", "route": "petroleum/stoc/wstk"},
        ],
    }


def test_selected_official_source_becomes_the_persisted_identity() -> None:
    selected = {"type": "eia_v2", "id": "WCESTUS1", "route": "petroleum/stoc/wstk"}
    aligned = _registry_entry_for_source(_entry(), selected)

    assert aligned["sources"][0] == selected
    assert aligned["sources"][1]["id"] == "WRONG"


def test_saved_series_is_searchable_and_attached_to_analysis(tmp_path: Path) -> None:
    store = ResearchStore(sqlite_path=tmp_path / "research.sqlite3")
    stored = store.upsert_variable(_registry_entry_for_source(_entry(), _entry()["sources"][1]))
    observations = pd.DataFrame(
        {
            "Date": pd.to_datetime(["2026-01-02", "2026-01-09", "2026-01-16"]),
            "SavedStocks": [421.0, 419.5, 418.0],
        }
    )
    store.upsert_observations(stored["id"], observations, "SavedStocks")

    matches = _stored_catalog_results(store, "crude stocks")
    assert len(matches) == 1
    assert matches[0]["stored_variable_id"] == stored["id"]
    assert matches[0]["source"] == "EIA"

    registry = _stored_registry_entries(store)
    assert registry[0]["research_store_variable_id"] == stored["id"]
    assert registry[0]["_stored_observations"]["SavedStocks"].tolist() == [421.0, 419.5, 418.0]

    selected, merged = _load_selected_stored_inputs(store, registry)
    assert selected[0]["_stored_observations"]["SavedStocks"].tolist() == [421.0, 419.5, 418.0]
    assert merged["SavedStocks"].tolist() == [421.0, 419.5, 418.0]


def test_saved_result_wins_deduplication_for_same_provider_series() -> None:
    official = [{"source": "EIA", "series_id": "ABC", "route": "petroleum/x"}]
    saved = [{**official[0], "stored_variable_id": "saved-id"}]

    merged = _merge_search_results(saved, official)

    assert merged == saved


def test_date_range_validation_is_localized() -> None:
    assert _date_range_error("2026-08-02", "2026-08-01", _ui_text) == "开始时间不能晚于结束时间，请重新选择。"
    assert _date_range_error("2026-08-01", "2026-08-02", _ui_text) is None


def test_declared_model_ready_column_loads_without_network(
    tmp_path: Path,
    monkeypatch,
) -> None:
    model_ready = tmp_path / "model_ready.xlsx"
    pd.DataFrame(
        {
            "Date": pd.to_datetime(["2026-01-02", "2026-01-05"]),
            "WTI": [70.0, 71.0],
            "Gold": [2600.0, 2610.0],
        }
    ).to_excel(model_ready, index=False)
    monkeypatch.setattr(variable_pool, "MODEL_READY_PATH", model_ready)
    entry = {
        "name": "Gold",
        "auto_download": False,
        "is_proxy": False,
        "frequency": "daily",
        "sources": [{"type": "existing_model_ready_column", "id": "Gold"}],
    }

    data, status = variable_pool._fetch_registry_variable(
        entry,
        "2026-01-01",
        "2026-01-31",
        force_refresh=False,
    )

    assert data["Gold"].tolist() == [2600.0, 2610.0]
    assert status["Status"] == "ExistingModelReady"
    assert status["ActualSource"] == "model_ready_data.xlsx"
