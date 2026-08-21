from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.research_store import ResearchStore


def _entry() -> dict[str, object]:
    return {
        "name": "FRED_TEST_SERIES",
        "display_name": "Test series",
        "economic_category": "real_economy_demand",
        "frequency": "Monthly",
        "sources": [{"type": "fred", "id": "TEST_SERIES"}],
    }


def test_sqlite_fallback_persists_variables_and_observations(tmp_path: Path) -> None:
    store = ResearchStore(sqlite_path=tmp_path / "research.sqlite3")
    stored = store.upsert_variable(_entry())
    count = store.upsert_observations(
        stored["id"],
        pd.DataFrame({"Date": ["2026-01-01", "2026-02-01"], "FRED_TEST_SERIES": [1.0, 2.0]}),
        "FRED_TEST_SERIES",
    )

    assert count == 2
    assert store.status.backend == "SQLite"
    assert store.status.shared is False
    assert store.list_variables()[0]["series_id"] == "TEST_SERIES"


def test_snapshot_respects_current_cache_window(tmp_path: Path) -> None:
    store = ResearchStore(sqlite_path=tmp_path / "research.sqlite3")
    store.save_snapshot("decision", "Brent", "2026-08-21", {"latest": 67.4})

    snapshot = store.latest_snapshot("decision", "Brent")

    assert snapshot is not None
    assert snapshot["payload"]["latest"] == 67.4
