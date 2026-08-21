# Data platform decision

## Current decision

Use PostgreSQL 18 for the production research library and keep SQLite as a zero-configuration local fallback. The application selects the backend from `DATABASE_URL`; API keys remain in deployment secrets and are never stored in either database.

The database persists only data that users choose to add, plus compact six-hour analysis snapshots. It does not copy the full FRED or EIA catalogs. Search follows a two-level path:

1. Match the synchronized index of connected official series immediately.
2. If no indexed series matches, expand the same query into the live FRED and EIA catalogs.
3. Fetch observations only for the selected series.
4. Let the user choose a date range and frequency, download Excel, or add the series to the shared research library.

This preserves current provider metadata, avoids an unnecessary catalog replica, and gives common oil, inventory, interest-rate, currency, and risk queries a fast path.

## Data model

The migration `migrations/202608220001_research_store_pg18.sql` creates:

- `research_variables`: one durable definition per provider and series identifier, including the full request-safe registry entry;
- `series_observations`: time-partitioned observations keyed by variable, observation date, and retrieval time;
- `analysis_snapshots`: latest successful result summaries keyed by result type, target, as-of date, and parameter signature.

PostgreSQL 18 native UUIDv7 identifiers keep time locality without application-generated IDs. Composite indexes support variable/time lookups, GIN supports JSON metadata, and BRIN supports long observation histories. SQLite mirrors the same logical entities for local development and automated tests.

## Refresh and failure behavior

- Decision results and official-catalog search results use a six-hour cache.
- The decision page offers a manual refresh control.
- A failed provider does not discard successful results from other providers.
- The page keeps the most recent successful result visible while fresh data is prepared.
- Added variables and observations are upserted, so a refresh extends rather than duplicates the series.

## Source-governance rule

Source selection follows this order:

1. Match the requested instrument and measurement definition.
2. Prefer an official publisher or exchange when definitions are equal.
3. Retain a lower-ranked source only as a failure fallback.
4. Mark spot/futures or index/futures substitutions as proxy fallbacks.
5. Remove only exact duplicates with the same provider type and series identifier.

The website exposes the source audit in professional mode. Multiple providers remain when they provide genuine fallback coverage; exact duplicates are removed without collapsing definition-changing proxies.

## Production setup

1. Provision PostgreSQL 18.
2. Apply `migrations/202608220001_research_store_pg18.sql` with a migration role.
3. Give the application role `SELECT`, `INSERT`, and `UPDATE` on the three application tables and required sequences; do not give it schema-owner privileges.
4. Add the connection string as the deployment secret `DATABASE_URL`.
5. Keep FRED, EIA, and model API credentials as separate deployment secrets.

Without `DATABASE_URL`, the app reports `SQLite | local fallback` and remains fully usable on one machine. With it, the same UI reports `PostgreSQL | shared`, and saved variables become available to all application instances using that database.
