"""Persistent catalog, observation, and analysis-snapshot storage.

Production uses PostgreSQL when ``DATABASE_URL`` is configured. Local runs and
tests fall back to SQLite so the data-center workflow remains fully usable
without a cloud account. API credentials are never written to either store.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import json
import os
from pathlib import Path
import sqlite3
from typing import Any, Iterator

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SQLITE_PATH = PROJECT_ROOT / "data" / "processed" / "research_store.sqlite3"
SNAPSHOT_TTL_HOURS = 6


def _json_default(value: Any) -> Any:
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()
    if hasattr(value, "item"):
        return value.item()
    raise TypeError(f"Cannot serialise {type(value).__name__}.")


def _normalise_entry(entry: dict[str, Any]) -> dict[str, Any]:
    sources = list(entry.get("sources") or [])
    primary = sources[0] if sources else {}
    return {
        "provider": str(primary.get("type") or entry.get("source") or "custom").upper(),
        "series_id": str(primary.get("id") or entry.get("series_id") or entry.get("name") or ""),
        "route": str(primary.get("route") or entry.get("route") or ""),
        "name": str(entry.get("name") or entry.get("series_id") or ""),
        "title": str(entry.get("display_name") or entry.get("title") or entry.get("name") or ""),
        "description": str(entry.get("description") or entry.get("note") or ""),
        "frequency": str(entry.get("frequency") or ""),
        "units": str(entry.get("units") or ""),
        "economic_category": str(entry.get("economic_category") or "other_indicators"),
        "metadata": entry,
    }


@dataclass(frozen=True)
class StoreStatus:
    backend: str
    shared: bool
    configured: bool
    message: str


class ResearchStore:
    """Small storage facade shared by the data center and decision dashboard."""

    def __init__(
        self,
        database_url: str | None = None,
        sqlite_path: str | Path = DEFAULT_SQLITE_PATH,
    ) -> None:
        self.database_url = str(database_url or os.getenv("DATABASE_URL", "")).strip()
        self.sqlite_path = Path(sqlite_path)
        self.backend = "postgresql" if self.database_url else "sqlite"
        self._initialised = False

    @property
    def status(self) -> StoreStatus:
        if self.backend == "postgresql":
            return StoreStatus(
                backend="PostgreSQL",
                shared=True,
                configured=True,
                message="共享变量库已连接。",
            )
        return StoreStatus(
            backend="SQLite",
            shared=False,
            configured=False,
            message="当前使用本地变量库；配置 DATABASE_URL 后会自动切换为共享 PostgreSQL。",
        )

    @contextmanager
    def _connection(self) -> Iterator[Any]:
        if self.backend == "postgresql":
            try:
                import psycopg
            except ImportError as exc:  # pragma: no cover - depends on deployment extras.
                raise RuntimeError("PostgreSQL storage requires psycopg.") from exc
            with psycopg.connect(self.database_url) as connection:
                yield connection
            return
        self.sqlite_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.sqlite_path)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def initialise(self) -> None:
        if self._initialised:
            return
        if self.backend == "postgresql":
            migration_path = PROJECT_ROOT / "migrations" / "202608220001_research_store_pg18.sql"
            sql = migration_path.read_text(encoding="utf-8")
            with self._connection() as connection:
                with connection.cursor() as cursor:
                    cursor.execute(sql)
        else:
            with self._connection() as connection:
                connection.executescript(
                    """
                    CREATE TABLE IF NOT EXISTS research_variables (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        provider TEXT NOT NULL,
                        series_id TEXT NOT NULL,
                        route TEXT NOT NULL DEFAULT '',
                        name TEXT NOT NULL,
                        title TEXT NOT NULL,
                        description TEXT NOT NULL DEFAULT '',
                        frequency TEXT NOT NULL DEFAULT '',
                        units TEXT NOT NULL DEFAULT '',
                        economic_category TEXT NOT NULL DEFAULT 'other_indicators',
                        metadata_json TEXT NOT NULL DEFAULT '{}',
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL,
                        deleted_at TEXT,
                        UNIQUE(provider, series_id, route)
                    );
                    CREATE INDEX IF NOT EXISTS idx_research_variables_category_updated
                        ON research_variables(economic_category, updated_at DESC);
                    CREATE TABLE IF NOT EXISTS series_observations (
                        variable_id INTEGER NOT NULL REFERENCES research_variables(id) ON DELETE CASCADE,
                        observed_at TEXT NOT NULL,
                        value REAL,
                        fetched_at TEXT NOT NULL,
                        PRIMARY KEY(variable_id, observed_at)
                    );
                    CREATE INDEX IF NOT EXISTS idx_series_observations_date
                        ON series_observations(observed_at);
                    CREATE TABLE IF NOT EXISTS analysis_snapshots (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        snapshot_type TEXT NOT NULL,
                        target TEXT NOT NULL,
                        as_of_date TEXT NOT NULL,
                        payload_json TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        expires_at TEXT NOT NULL
                    );
                    CREATE INDEX IF NOT EXISTS idx_analysis_snapshots_lookup
                        ON analysis_snapshots(snapshot_type, target, created_at DESC);
                    """
                )
        self._initialised = True

    def upsert_variable(self, entry: dict[str, Any]) -> dict[str, Any]:
        self.initialise()
        item = _normalise_entry(entry)
        if not item["series_id"] or not item["name"]:
            raise ValueError("The selected catalog item has no stable series identifier.")
        now = datetime.now(UTC).isoformat()
        metadata_json = json.dumps(item["metadata"], ensure_ascii=False, default=_json_default)
        with self._connection() as connection:
            if self.backend == "postgresql":
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        INSERT INTO research_variables (
                            provider, series_id, route, name, title, description,
                            frequency, units, economic_category, metadata
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
                        ON CONFLICT (provider, series_id, route) WHERE deleted_at IS NULL
                        DO UPDATE SET
                            name = EXCLUDED.name,
                            title = EXCLUDED.title,
                            description = EXCLUDED.description,
                            frequency = EXCLUDED.frequency,
                            units = EXCLUDED.units,
                            economic_category = EXCLUDED.economic_category,
                            metadata = EXCLUDED.metadata,
                            updated_at = now()
                        RETURNING id::text
                        """,
                        (
                            item["provider"], item["series_id"], item["route"], item["name"],
                            item["title"], item["description"], item["frequency"], item["units"],
                            item["economic_category"], metadata_json,
                        ),
                    )
                    variable_id = cursor.fetchone()[0]
            else:
                connection.execute(
                    """
                    INSERT INTO research_variables (
                        provider, series_id, route, name, title, description,
                        frequency, units, economic_category, metadata_json, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(provider, series_id, route) DO UPDATE SET
                        name=excluded.name, title=excluded.title, description=excluded.description,
                        frequency=excluded.frequency, units=excluded.units,
                        economic_category=excluded.economic_category,
                        metadata_json=excluded.metadata_json, updated_at=excluded.updated_at,
                        deleted_at=NULL
                    """,
                    (
                        item["provider"], item["series_id"], item["route"], item["name"],
                        item["title"], item["description"], item["frequency"], item["units"],
                        item["economic_category"], metadata_json, now, now,
                    ),
                )
                row = connection.execute(
                    "SELECT id FROM research_variables WHERE provider=? AND series_id=? AND route=?",
                    (item["provider"], item["series_id"], item["route"]),
                ).fetchone()
                variable_id = str(row[0])
        return {**item, "id": str(variable_id)}

    def list_variables(self) -> list[dict[str, Any]]:
        self.initialise()
        with self._connection() as connection:
            if self.backend == "postgresql":
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        SELECT id::text, provider, series_id, route, name, title, description,
                               frequency, units, economic_category, metadata::text, updated_at
                        FROM research_variables
                        WHERE deleted_at IS NULL
                        ORDER BY updated_at DESC
                        """
                    )
                    rows = cursor.fetchall()
            else:
                rows = connection.execute(
                    """
                    SELECT id, provider, series_id, route, name, title, description,
                           frequency, units, economic_category, metadata_json, updated_at
                    FROM research_variables
                    WHERE deleted_at IS NULL
                    ORDER BY updated_at DESC
                    """
                ).fetchall()
        output: list[dict[str, Any]] = []
        for row in rows:
            output.append(
                {
                    "id": str(row[0]), "provider": row[1], "series_id": row[2], "route": row[3],
                    "name": row[4], "title": row[5], "description": row[6], "frequency": row[7],
                    "units": row[8], "economic_category": row[9],
                    "metadata": json.loads(row[10] or "{}"), "updated_at": str(row[11]),
                }
            )
        return output

    def upsert_observations(self, variable_id: str, data: pd.DataFrame, value_column: str) -> int:
        self.initialise()
        if data.empty or "Date" not in data or value_column not in data:
            return 0
        frame = data[["Date", value_column]].copy()
        frame["Date"] = pd.to_datetime(frame["Date"], errors="coerce")
        frame[value_column] = pd.to_numeric(frame[value_column], errors="coerce")
        frame = frame.dropna().drop_duplicates("Date", keep="last")
        fetched_at = datetime.now(UTC).isoformat()
        with self._connection() as connection:
            if self.backend == "postgresql":
                with connection.cursor() as cursor:
                    cursor.executemany(
                        """
                        INSERT INTO series_observations(variable_id, observed_at, value, fetched_at)
                        VALUES (%s::uuid, %s, %s, %s)
                        ON CONFLICT(variable_id, observed_at) DO UPDATE SET
                            value=EXCLUDED.value, fetched_at=EXCLUDED.fetched_at
                        """,
                        [(variable_id, row.Date.date(), float(getattr(row, value_column)), fetched_at) for row in frame.itertuples()],
                    )
            else:
                connection.executemany(
                    """
                    INSERT INTO series_observations(variable_id, observed_at, value, fetched_at)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(variable_id, observed_at) DO UPDATE SET
                        value=excluded.value, fetched_at=excluded.fetched_at
                    """,
                    [(int(variable_id), row.Date.date().isoformat(), float(getattr(row, value_column)), fetched_at) for row in frame.itertuples()],
                )
        return len(frame)

    def save_snapshot(self, snapshot_type: str, target: str, as_of_date: str, payload: dict[str, Any]) -> None:
        self.initialise()
        created = datetime.now(UTC)
        expires = created + timedelta(hours=SNAPSHOT_TTL_HOURS)
        payload_json = json.dumps(payload, ensure_ascii=False, default=_json_default)
        with self._connection() as connection:
            if self.backend == "postgresql":
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        INSERT INTO analysis_snapshots(snapshot_type, target, as_of_date, payload, expires_at)
                        VALUES (%s, %s, %s, %s::jsonb, %s)
                        """,
                        (snapshot_type, target, as_of_date, payload_json, expires),
                    )
            else:
                connection.execute(
                    """
                    INSERT INTO analysis_snapshots(snapshot_type, target, as_of_date, payload_json, created_at, expires_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (snapshot_type, target, as_of_date, payload_json, created.isoformat(), expires.isoformat()),
                )

    def latest_snapshot(self, snapshot_type: str, target: str) -> dict[str, Any] | None:
        self.initialise()
        now = datetime.now(UTC)
        with self._connection() as connection:
            if self.backend == "postgresql":
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        SELECT payload::text, as_of_date::text, created_at, expires_at
                        FROM analysis_snapshots
                        WHERE snapshot_type=%s AND target=%s AND expires_at>%s
                        ORDER BY created_at DESC LIMIT 1
                        """,
                        (snapshot_type, target, now),
                    )
                    row = cursor.fetchone()
            else:
                row = connection.execute(
                    """
                    SELECT payload_json, as_of_date, created_at, expires_at
                    FROM analysis_snapshots
                    WHERE snapshot_type=? AND target=? AND expires_at>?
                    ORDER BY created_at DESC LIMIT 1
                    """,
                    (snapshot_type, target, now.isoformat()),
                ).fetchone()
        if row is None:
            return None
        return {
            "payload": json.loads(row[0]),
            "as_of_date": str(row[1]),
            "created_at": str(row[2]),
            "expires_at": str(row[3]),
        }


def get_research_store(database_url: str | None = None) -> ResearchStore:
    """Return a configured store without importing Streamlit into the data layer."""
    return ResearchStore(database_url=database_url)
