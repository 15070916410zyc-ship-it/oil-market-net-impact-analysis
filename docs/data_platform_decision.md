# Data platform decision

## Current decision

Do not add an external SQL database to the single-app deployment yet. The current workload is a provider catalog plus bounded analytical time series, so the simpler and more reliable architecture is:

1. Search official provider metadata live through FRED and EIA v2.
2. Register only the selected series in the current analysis session.
3. Refresh selected observations through the existing download layer.
4. Cache model-ready files locally and preserve the existing downloadable audit workbooks.

This avoids copying entire third-party catalogs into a database, keeps provider metadata current, and does not add a database service to Streamlit deployment. FRED exposes a full-text series-search API; EIA v2 exposes a self-documenting route tree, facets, frequencies, and series metadata.

## Source-governance rule

Source selection follows this order:

1. Match the requested instrument and measurement definition.
2. Prefer an official publisher or exchange when definitions are equal.
3. Retain a lower-ranked source only as a failure fallback.
4. Mark spot/futures or index/futures substitutions as proxy fallbacks.
5. Remove only exact duplicates with the same provider type and series identifier.

The current registry audit contains 24 variables and 50 source entries. It contains no exact provider-series duplicates. The multiple providers are therefore retained, while 5 definition-changing proxy fallbacks are explicitly labelled in the website.

## When PostgreSQL becomes justified

Add PostgreSQL only when at least one of these requirements becomes real:

- multiple authenticated enterprises need separate portfolios and hedge policies;
- users need durable saved searches and shared data selections;
- every recommendation needs an immutable as-of audit trail;
- provider observations must be versioned by both observation date and retrieval date;
- scheduled refresh jobs run independently of Streamlit sessions;
- the local cache exceeds practical repository or ephemeral-disk limits.

At that point the production target should be PostgreSQL 18 with UUIDv7 identifiers, `timestamptz` audit fields, temporal validity for source mappings and hedge policies, and time-based partitioning for large observation tables. Until then, direct official catalog search plus local analytical caching is the lower-risk design.

## Live verification on 2026-08-21

- FRED catalog search returned current metadata.
- EIA catalog search returned current petroleum stock series after using the verified Windows system TLS transport fallback.
- Brent, OVX, 10-year Treasury yield, VIX, and EIA crude-stock data refreshed successfully.
- WTI fell through to the Yahoo chart endpoint when the EIA futures response was empty and the Yahoo package endpoint was rate-limited, preserving daily continuity while recording the actual source.

The source audit and actual-source fields remain visible and downloadable from the Data Center page.
