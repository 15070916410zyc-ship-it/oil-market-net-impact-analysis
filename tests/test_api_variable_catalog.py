from __future__ import annotations

import unittest
from unittest.mock import Mock, patch

from src.api_variable_catalog import (
    catalog_item_to_registry_entry,
    fetch_eia_v2_series,
    search_eia_series,
    search_fred_series,
)
from src.variable_pool import load_variable_registry


class ApiVariableCatalogTests(unittest.TestCase):
    @patch("src.api_variable_catalog._get_fred_api_key", return_value="a" * 32)
    @patch("src.api_variable_catalog.requests.get")
    def test_fred_search_normalises_official_metadata(self, get: Mock, _key: Mock) -> None:
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {
            "seriess": [
                {
                    "id": "INDPRO",
                    "title": "Industrial Production: Total Index",
                    "frequency_short": "M",
                    "units_short": "Index",
                    "observation_start": "1919-01-01",
                    "observation_end": "2026-01-01",
                }
            ]
        }
        get.return_value = response

        result = search_fred_series("industrial production")

        self.assertEqual(result[0]["series_id"], "INDPRO")
        self.assertEqual(result[0]["economic_category"], "real_economy_demand")

    @patch("src.api_variable_catalog._get_eia_api_key", return_value="key")
    @patch("src.api_variable_catalog.requests.get")
    def test_eia_search_returns_explicit_series_facet(self, get: Mock, _key: Mock) -> None:
        metadata_response = Mock()
        metadata_response.raise_for_status.return_value = None
        metadata_response.json.return_value = {
            "response": {
                "facets": [{"id": "series"}],
                "frequency": [{"id": "weekly"}],
                "defaultFrequency": "weekly",
                "startPeriod": "1982-01-01",
                "endPeriod": "2026-01-01",
            }
        }
        facet_response = Mock()
        facet_response.raise_for_status.return_value = None
        facet_response.json.return_value = {
            "response": {
                "facets": [{"id": "WCESTUS1", "name": "U.S. commercial crude oil stocks"}]
            }
        }
        get.side_effect = [metadata_response, facet_response]

        result = search_eia_series("crude oil stocks", "petroleum/stoc/wstk")

        self.assertEqual(result[0]["facets"], {"series": ["WCESTUS1"]})
        entry = catalog_item_to_registry_entry(result[0])
        self.assertEqual(entry["sources"][0]["type"], "eia_v2")
        self.assertEqual(entry["economic_category"], "inventories_refining")

    @patch("src.api_variable_catalog._get_eia_api_key", return_value="key")
    @patch("src.api_variable_catalog.requests.get")
    def test_eia_fetch_rejects_implicit_multi_series_rows(self, get: Mock, _key: Mock) -> None:
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {
            "response": {
                "data": [
                    {"period": "2024-01-05", "value": "1"},
                    {"period": "2024-01-05", "value": "2"},
                ]
            }
        }
        get.return_value = response
        with self.assertRaisesRegex(ValueError, "multiple series"):
            fetch_eia_v2_series(
                {
                    "route": "petroleum/stoc/wstk",
                    "data": "value",
                    "frequency": "weekly",
                    "facets": {"series": ["WCESTUS1"]},
                },
                "EIA_WCESTUS1",
                "2024-01-01",
                "2024-01-31",
            )

    def test_request_local_entry_keeps_eia_source_configuration(self) -> None:
        entry = catalog_item_to_registry_entry(
            {
                "source": "EIA",
                "series_id": "WCESTUS1",
                "title": "Crude stocks",
                "route": "petroleum/stoc/wstk",
                "data_field": "value",
                "frequency": "weekly",
                "facets": {"series": ["WCESTUS1"]},
                "economic_category": "inventories_refining",
            }
        )
        registry = load_variable_registry(extra_entries=[entry])
        dynamic = next(item for item in registry if item["name"] == "EIA_WCESTUS1")
        self.assertEqual(dynamic["sources"][0]["route"], "petroleum/stoc/wstk")
        self.assertTrue(dynamic["daily_fill_forward"])


if __name__ == "__main__":
    unittest.main()
