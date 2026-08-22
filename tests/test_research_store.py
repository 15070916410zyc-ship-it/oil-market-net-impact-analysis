from __future__ import annotations

from pathlib import Path
import sqlite3
import sys
from types import SimpleNamespace

import pandas as pd
import pytest

from src.research_store import (
    POSTGRES_CONNECT_TIMEOUT_SECONDS,
    ResearchStore,
    ResearchStoreSchemaError,
)


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
    status = store.status
    assert status.backend == "SQLite"
    assert status.shared is False
    assert status.connected is True
    assert status.schema_ready is True
    assert status.healthy is True
    assert store.list_variables()[0]["series_id"] == "TEST_SERIES"
    observations = store.read_observations(stored["id"])
    assert list(observations) == ["Date", "FRED_TEST_SERIES"]
    assert observations["Date"].tolist() == [pd.Timestamp("2026-01-01"), pd.Timestamp("2026-02-01")]
    assert observations["FRED_TEST_SERIES"].tolist() == [1.0, 2.0]


def test_sqlite_observation_readback_filters_dates_inclusively(tmp_path: Path) -> None:
    store = ResearchStore(sqlite_path=tmp_path / "research.sqlite3")
    stored = store.upsert_variable(_entry())
    store.upsert_observations(
        stored["id"],
        pd.DataFrame(
            {
                "Date": ["2026-01-01", "2026-02-01", "2026-03-01"],
                "FRED_TEST_SERIES": [1.0, 2.0, 3.0],
            }
        ),
        "FRED_TEST_SERIES",
    )

    filtered = store.read_observations(
        stored["id"],
        start_date="2026-02-01",
        end_date="2026-02-28",
        value_column="Value",
    )

    assert filtered.to_dict("records") == [{"Date": pd.Timestamp("2026-02-01"), "Value": 2.0}]
    with pytest.raises(ValueError, match="start_date must not be after end_date"):
        store.read_observations(stored["id"], "2026-03-01", "2026-01-01")


def test_saved_registry_and_observations_load_as_analysis_inputs(tmp_path: Path) -> None:
    store = ResearchStore(sqlite_path=tmp_path / "research.sqlite3")
    stored = store.upsert_variable(_entry())
    store.upsert_observations(
        stored["id"],
        pd.DataFrame({"Date": ["2026-01-01", "2026-02-01"], "FRED_TEST_SERIES": [1.0, 2.0]}),
        "FRED_TEST_SERIES",
    )

    registry, data = store.load_analysis_data(start_date="2026-02-01")

    assert registry[0]["name"] == "FRED_TEST_SERIES"
    assert registry[0]["research_store_variable_id"] == stored["id"]
    assert data.to_dict("records") == [
        {"Date": pd.Timestamp("2026-02-01"), "FRED_TEST_SERIES": 2.0}
    ]


def test_healthcheck_reports_a_missing_sqlite_table(tmp_path: Path) -> None:
    database_path = tmp_path / "research.sqlite3"
    store = ResearchStore(sqlite_path=database_path)
    store.initialise()
    with sqlite3.connect(database_path) as connection:
        connection.execute("DROP TABLE series_observations")

    status = store.healthcheck()

    assert status.connected is True
    assert status.schema_ready is False
    assert status.shared is False
    assert status.error_code == "schema_missing"
    assert status.missing_tables == ("series_observations",)


class _PostgresCursor:
    def __init__(self, tables: tuple[object, ...]) -> None:
        self.tables = tables
        self.executed: list[tuple[str, object]] = []

    def __enter__(self) -> "_PostgresCursor":
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def execute(self, statement: str, parameters: object = None) -> None:
        self.executed.append((statement, parameters))

    def fetchone(self) -> tuple[object, ...]:
        return self.tables


class _PostgresConnection:
    def __init__(self, cursor: _PostgresCursor) -> None:
        self._cursor = cursor

    def __enter__(self) -> "_PostgresConnection":
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def cursor(self) -> _PostgresCursor:
        return self._cursor


def test_postgres_healthcheck_uses_timeout_and_does_not_run_ddl(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cursor = _PostgresCursor(
        (
            "research_variables",
            "series_observations",
            "analysis_snapshots",
            "series_observations_default",
        )
    )
    connection = _PostgresConnection(cursor)
    connect_calls: list[tuple[str, dict[str, object]]] = []

    def connect(database_url: str, **kwargs: object) -> _PostgresConnection:
        connect_calls.append((database_url, kwargs))
        return connection

    monkeypatch.setitem(sys.modules, "psycopg", SimpleNamespace(connect=connect))
    store = ResearchStore(database_url="postgresql://user:secret@example.invalid/db")

    status = store.healthcheck()

    assert status.healthy is True
    assert status.shared is True
    assert connect_calls == [
        (
            "postgresql://user:secret@example.invalid/db",
            {"connect_timeout": POSTGRES_CONNECT_TIMEOUT_SECONDS},
        )
    ]
    assert all("CREATE TABLE" not in statement.upper() for statement, _ in cursor.executed)


def test_postgres_status_does_not_claim_a_connection_from_url_alone(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_connect(*_args: object, **_kwargs: object) -> None:
        raise OSError("connection refused")

    monkeypatch.setitem(sys.modules, "psycopg", SimpleNamespace(connect=fail_connect))
    store = ResearchStore(database_url="postgresql://user:secret@example.invalid/db")

    status = store.status

    assert status.configured is True
    assert status.connected is False
    assert status.schema_ready is False
    assert status.shared is False
    assert status.error_code == "connection_failed"
    assert "secret" not in status.message


def test_postgres_initialise_requires_applied_migration(monkeypatch: pytest.MonkeyPatch) -> None:
    cursor = _PostgresCursor(
        ("research_variables", None, "analysis_snapshots", "series_observations_default")
    )
    connection = _PostgresConnection(cursor)
    monkeypatch.setitem(
        sys.modules,
        "psycopg",
        SimpleNamespace(connect=lambda *_args, **_kwargs: connection),
    )
    store = ResearchStore(database_url="postgresql://configured.invalid/db")

    with pytest.raises(ResearchStoreSchemaError, match="Apply migrations/202608220001"):
        store.initialise()

    assert all("CREATE TABLE" not in statement.upper() for statement, _ in cursor.executed)


def test_snapshot_respects_current_cache_window(tmp_path: Path) -> None:
    store = ResearchStore(sqlite_path=tmp_path / "research.sqlite3")
    store.save_snapshot("decision", "Brent", "2026-08-21", {"latest": 67.4})

    snapshot = store.latest_snapshot("decision", "Brent")

    assert snapshot is not None
    assert snapshot["payload"]["latest"] == 67.4
