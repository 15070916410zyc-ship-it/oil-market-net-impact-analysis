from __future__ import annotations

import unittest

import pandas as pd

from src.data_governance import (
    aggregate_time_series,
    audit_registry_sources,
    deduplicate_catalog_results,
)


class DataGovernanceTests(unittest.TestCase):
    def test_registry_audit_distinguishes_duplicates_from_fallbacks(self) -> None:
        audit = audit_registry_sources(
            [
                {
                    "name": "Brent",
                    "description": "Brent futures price",
                    "sources": [
                        {"type": "yfinance", "id": "BZ=F"},
                        {"type": "fred", "id": "DCOILBRENTEU"},
                    ],
                },
                {
                    "name": "DuplicateBrent",
                    "sources": [{"type": "yfinance", "id": "BZ=F"}],
                },
            ]
        )
        self.assertEqual(audit.exact_duplicate_count, 1)
        self.assertEqual(audit.proxy_fallback_count, 1)
        self.assertTrue(audit.table.loc[audit.table["SeriesID"] == "BZ=F", "ExactDuplicate"].all())

    def test_catalog_deduplication_keeps_different_provider_series(self) -> None:
        results = deduplicate_catalog_results(
            [
                {"source": "FRED", "series_id": "DGS10", "description": "short"},
                {"source": "FRED", "series_id": "DGS10", "description": "longer description"},
                {"source": "EIA", "series_id": "DGS10", "description": "different provider"},
            ]
        )
        self.assertEqual(len(results), 2)
        fred = next(item for item in results if item["source"] == "FRED")
        self.assertEqual(fred["description"], "longer description")

    def test_monthly_aggregation_uses_last_for_price_and_sum_for_flow(self) -> None:
        data = pd.DataFrame(
            {
                "Date": pd.to_datetime(["2026-01-02", "2026-01-30", "2026-02-02"]),
                "Brent": [70.0, 74.0, 73.0],
                "Production": [10.0, 12.0, 9.0],
            }
        )
        monthly = aggregate_time_series(data, "monthly")
        self.assertEqual(monthly["Brent"].tolist(), [74.0, 73.0])
        self.assertEqual(monthly["Production"].tolist(), [22.0, 9.0])


if __name__ == "__main__":
    unittest.main()
