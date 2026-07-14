"""Per-user API credential isolation and persistence tests."""

from __future__ import annotations

import base64
from contextvars import copy_context
import json
import os
import unittest
from unittest.mock import patch

from cryptography.fernet import Fernet


class ApiCredentialTests(unittest.TestCase):
    def tearDown(self) -> None:
        try:
            from src.api_credentials import clear_session_api_keys

            clear_session_api_keys()
        except ImportError:
            pass

    def test_browser_cookie_payload_is_encrypted_and_round_trips_allowed_keys(self) -> None:
        from src.api_credentials import decrypt_api_keys, encrypt_api_keys

        encryption_key = base64.urlsafe_b64encode(b"0" * 32).decode("ascii")
        api_keys = {
            "FRED_API_KEY": "a" * 32,
            "EIA_API_KEY": "private-eia-key",
            "UNSUPPORTED_KEY": "must-not-be-saved",
        }

        token = encrypt_api_keys(api_keys, encryption_key)

        self.assertNotIn("private-eia-key", token)
        self.assertNotIn("must-not-be-saved", token)
        self.assertEqual(
            decrypt_api_keys(token, encryption_key),
            {
                "FRED_API_KEY": "a" * 32,
                "EIA_API_KEY": "private-eia-key",
            },
        )

    def test_invalid_or_tampered_cookie_is_ignored(self) -> None:
        from src.api_credentials import decrypt_api_keys

        encryption_key = base64.urlsafe_b64encode(b"1" * 32).decode("ascii")

        self.assertEqual(decrypt_api_keys("not-a-valid-token", encryption_key), {})
        self.assertEqual(decrypt_api_keys("", encryption_key), {})
        self.assertEqual(decrypt_api_keys("token", ""), {})

        unsupported_version = Fernet(encryption_key).encrypt(
            json.dumps({"version": 2, "keys": {"FRED_API_KEY": "a" * 32}}).encode()
        ).decode()
        malformed_keys = Fernet(encryption_key).encrypt(
            json.dumps({"version": 1, "keys": ["not", "a", "mapping"]}).encode()
        ).decode()
        self.assertEqual(decrypt_api_keys(unsupported_version, encryption_key), {})
        self.assertEqual(decrypt_api_keys(malformed_keys, encryption_key), {})

    def test_session_keys_are_context_local_and_can_be_cleared(self) -> None:
        from src.api_credentials import (
            clear_session_api_keys,
            get_session_api_key,
            set_session_api_keys,
        )

        set_session_api_keys({"FRED_API_KEY": "a" * 32})
        isolated_context = copy_context()
        isolated_context.run(clear_session_api_keys)

        self.assertEqual(get_session_api_key("FRED_API_KEY"), "a" * 32)
        self.assertEqual(isolated_context.run(get_session_api_key, "FRED_API_KEY"), "")

        clear_session_api_keys()
        self.assertEqual(get_session_api_key("FRED_API_KEY"), "")
        self.assertEqual(get_session_api_key("UNSUPPORTED_KEY"), "")

    def test_session_keys_take_priority_without_mutating_process_environment(self) -> None:
        from src.api_credentials import set_session_api_keys
        from src import data_fetcher

        session_fred_key = "b" * 32
        set_session_api_keys(
            {
                "FRED_API_KEY": session_fred_key,
                "EIA_API_KEY": "session-eia-key",
            }
        )

        with (
            patch.object(data_fetcher, "_load_environment_files"),
            patch.object(data_fetcher, "_read_env_file_value", return_value=""),
            patch.dict(
                os.environ,
                {"FRED_API_KEY": "c" * 32, "EIA_API_KEY": "environment-eia-key"},
                clear=False,
            ),
        ):
            self.assertEqual(data_fetcher._get_fred_api_key(), session_fred_key)
            self.assertEqual(data_fetcher._get_eia_api_key(), "session-eia-key")
            self.assertTrue(data_fetcher._has_configured_fred_api_key())
            self.assertTrue(data_fetcher._has_configured_eia_api_key())

        self.assertNotEqual(os.environ.get("FRED_API_KEY"), session_fred_key)
        self.assertNotEqual(os.environ.get("EIA_API_KEY"), "session-eia-key")

    def test_configured_session_api_source_is_prioritised(self) -> None:
        from src.api_credentials import set_session_api_keys
        from src import data_fetcher

        sources = [
            {"type": "yfinance", "id": "CL=F"},
            {"type": "eia", "id": "RCLC1"},
            {"type": "stooq", "id": "CL.F"},
        ]
        set_session_api_keys({"EIA_API_KEY": "session-eia-key"})

        with patch.object(data_fetcher, "_load_environment_files"):
            ordered = data_fetcher._prioritise_api_sources(sources)

        self.assertEqual(ordered[0], {"type": "eia", "id": "RCLC1"})
        self.assertEqual(ordered[1:], [sources[0], sources[2]])

    def test_cloud_session_can_disable_shared_environment_key_fallback(self) -> None:
        from src.api_credentials import set_session_api_keys
        from src import data_fetcher

        set_session_api_keys({}, allow_shared_fallback=False)

        with (
            patch.object(data_fetcher, "_load_environment_files"),
            patch.object(data_fetcher, "_read_env_file_value", return_value=""),
            patch.dict(
                os.environ,
                {"FRED_API_KEY": "d" * 32, "EIA_API_KEY": "shared-eia-key"},
                clear=False,
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "FRED_API_KEY was not found"):
                data_fetcher._get_fred_api_key()
            self.assertEqual(data_fetcher._get_eia_api_key(), "DEMO_KEY")
            self.assertFalse(data_fetcher._has_configured_fred_api_key())
            self.assertFalse(data_fetcher._has_configured_eia_api_key())


if __name__ == "__main__":
    unittest.main()
