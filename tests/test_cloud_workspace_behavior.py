"""Cloud-safety and result-export tests for the Streamlit application."""

from __future__ import annotations

from io import BytesIO
import hashlib
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from zipfile import ZipFile


class CloudWorkspaceBehaviorTests(unittest.TestCase):
    def test_cloud_runtime_detection_supports_override_and_streamlit_marker(self) -> None:
        from app.streamlit_app import is_cloud_runtime

        self.assertTrue(is_cloud_runtime({"NET_IMPACT_RUNTIME_MODE": "cloud"}, Path("C:/project")))
        self.assertFalse(is_cloud_runtime({"NET_IMPACT_RUNTIME_MODE": "local"}, Path("/mount/src/app")))
        self.assertTrue(is_cloud_runtime({"STREAMLIT_SHARING_MODE": "true"}, Path("C:/project")))
        self.assertTrue(is_cloud_runtime({}, Path("/mount/src/net-impact")))
        self.assertFalse(is_cloud_runtime({}, Path("C:/project")))
        with patch.dict(os.environ, {"NET_IMPACT_RUNTIME_MODE": "cloud"}, clear=True):
            self.assertTrue(is_cloud_runtime(project_root=Path("C:/project")))

    def test_upload_priority_maps_to_existing_value_preference(self) -> None:
        from app.streamlit_app import prefer_existing_variable_values

        self.assertFalse(prefer_existing_variable_values({"use_uploaded_local_data_first": True}))
        self.assertTrue(prefer_existing_variable_values({"use_uploaded_local_data_first": False}))
        self.assertFalse(prefer_existing_variable_values({}))

    def test_result_archive_contains_outputs_and_excludes_workspace_secrets(self) -> None:
        from app.streamlit_app import build_results_archive

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            table = root / "outputs" / "tables" / "summary.xlsx"
            figure = root / "outputs" / "figures" / "impact.png"
            secret = root / "API.env"
            upload = root / "data" / "raw" / "uploads" / "private.csv"
            table.parent.mkdir(parents=True)
            figure.parent.mkdir(parents=True)
            (table.parent / "empty-directory").mkdir()
            upload.parent.mkdir(parents=True)
            table.write_bytes(b"table")
            figure.write_bytes(b"figure")
            secret.write_text("FRED_API_KEY=secret", encoding="utf-8")
            upload.write_text("private", encoding="utf-8")

            archive_bytes, archive_names = build_results_archive(root)

            self.assertEqual(
                archive_names,
                ["outputs/figures/impact.png", "outputs/tables/summary.xlsx"],
            )
            with ZipFile(BytesIO(archive_bytes)) as archive:
                self.assertEqual(sorted(archive.namelist()), archive_names)
                self.assertEqual(archive.read("outputs/tables/summary.xlsx"), b"table")
                self.assertNotIn("API.env", archive.namelist())
                self.assertNotIn("data/raw/uploads/private.csv", archive.namelist())

    def test_result_archive_is_empty_when_no_results_exist(self) -> None:
        from app.streamlit_app import build_results_archive

        with tempfile.TemporaryDirectory() as temp_dir:
            archive_bytes, archive_names = build_results_archive(Path(temp_dir))

        self.assertEqual(archive_bytes, b"")
        self.assertEqual(archive_names, [])

    def test_upload_priority_checkbox_is_removed_from_the_interface(self) -> None:
        source = (Path(__file__).resolve().parents[1] / "app" / "streamlit_app.py").read_text(encoding="utf-8")

        self.assertNotIn("Use uploaded local data first", source)
        self.assertNotIn("优先使用本地上传数据", source)

    def test_cloud_tool_menu_renders_per_browser_api_controls_only(self) -> None:
        from app import streamlit_app as app

        with (
            patch.object(app, "is_cloud_runtime", return_value=True),
            patch.object(app, "render_cloud_api_tool_menu") as cloud_api_menu,
        ):
            app.render_top_tool_menu()

        cloud_api_menu.assert_called_once_with()

    def test_cloud_cookie_keys_are_restored_into_request_local_context(self) -> None:
        from app import streamlit_app as app
        from src.api_credentials import encrypt_api_keys

        encryption_key = "MDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDA="
        token = encrypt_api_keys({"FRED_API_KEY": "a" * 32}, encryption_key)

        session_state: dict[str, object] = {}
        with (
            patch.object(app, "is_cloud_runtime", return_value=True),
            patch.object(app, "browser_api_cookie_encryption_key", return_value=encryption_key),
            patch.object(app, "read_browser_api_cookie", return_value=token),
            patch.object(app.st, "session_state", session_state),
            patch.object(app, "set_session_api_keys") as activate_keys,
        ):
            restored = app.restore_api_credentials_for_request()

        self.assertEqual(restored, {"FRED_API_KEY": "a" * 32})
        self.assertEqual(session_state[app.BROWSER_API_SESSION_STATE], restored)
        activate_keys.assert_called_once_with(restored, allow_shared_fallback=False)

    def test_cloud_cookie_restore_fails_closed_without_crashing_the_app(self) -> None:
        from app import streamlit_app as app

        with (
            patch.object(app, "is_cloud_runtime", return_value=True),
            patch.object(
                app,
                "browser_api_cookie_encryption_key",
                side_effect=RuntimeError("cloud secrets are temporarily unavailable"),
            ),
            patch.object(app, "set_session_api_keys") as activate_keys,
        ):
            restored = app.restore_api_credentials_for_request()

        self.assertEqual(restored, {})
        activate_keys.assert_called_once_with({}, allow_shared_fallback=False)

    def test_cloud_api_status_ignores_shared_file_and_environment_keys(self) -> None:
        from app import streamlit_app as app

        with (
            patch.object(app, "read_api_env_values", return_value={"EIA_API_KEY": "shared-file-key"}),
            patch.dict(os.environ, {"EIA_API_KEY": "shared-environment-key"}, clear=False),
            patch.object(
                app,
                "validate_fred_api_key",
                return_value={"status": "valid", "message": "verified"},
            ),
        ):
            status = app.api_key_status(
                {"FRED_API_KEY": "a" * 32},
                include_shared_sources=False,
            )

        self.assertTrue(status["keys"]["FRED_API_KEY"]["configured"])
        self.assertEqual(status["keys"]["FRED_API_KEY"]["source"], "this browser")
        self.assertFalse(status["keys"]["EIA_API_KEY"]["configured"])

    def test_api_panel_save_does_not_interrupt_the_rest_of_the_page_rerun(self) -> None:
        import inspect

        from app import streamlit_app as app

        source = inspect.getsource(app.render_api_settings_panel)

        self.assertNotIn("st.rerun()", source)

    def test_browser_cookie_secure_flag_follows_the_access_protocol(self) -> None:
        from app.streamlit_app import browser_api_cookie_is_secure

        self.assertTrue(browser_api_cookie_is_secure("https://example.streamlit.app"))
        self.assertFalse(browser_api_cookie_is_secure("http://localhost:8501"))

    def test_browser_cookie_value_is_url_decoded_before_decryption(self) -> None:
        from app.streamlit_app import decode_browser_api_cookie_value

        self.assertEqual(decode_browser_api_cookie_value("encrypted-token%3D%3D"), "encrypted-token==")

    def test_clear_browser_keys_expires_cookie_even_for_a_new_session(self) -> None:
        from app import streamlit_app as app

        class NewSessionController:
            def __init__(self) -> None:
                self.set_calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

            def set(self, *args: object, **kwargs: object) -> None:
                self.set_calls.append((args, kwargs))

        controller = NewSessionController()
        session_state = {app.BROWSER_API_SESSION_STATE: {"EIA_API_KEY": "private"}}
        with (
            patch.object(app, "get_browser_cookie_controller", return_value=controller),
            patch.object(app, "browser_api_cookie_is_secure", return_value=True),
            patch.object(app.st, "session_state", session_state),
            patch.object(app, "set_session_api_keys") as activate_keys,
        ):
            app.clear_browser_api_values()

        self.assertEqual(len(controller.set_calls), 1)
        args, kwargs = controller.set_calls[0]
        self.assertEqual(args, (app.BROWSER_API_COOKIE_NAME, ""))
        self.assertEqual(kwargs["max_age"], 0)
        self.assertEqual(session_state[app.BROWSER_API_SESSION_STATE], {})
        activate_keys.assert_called_once_with({}, allow_shared_fallback=False)

    def test_fred_validation_cache_uses_a_digest_instead_of_the_secret(self) -> None:
        from app import streamlit_app as app

        class ValidFredResponse:
            status_code = 200
            text = ""

            @staticmethod
            def json() -> dict[str, object]:
                return {"seriess": [{"id": "DGS10"}]}

        api_key = "a" * 32
        app.API_VALIDATION_CACHE.clear()
        with patch("requests.get", return_value=ValidFredResponse()):
            result = app.validate_fred_api_key(api_key)

        expected_cache_key = f"fred:{hashlib.sha256(api_key.encode()).hexdigest()}"
        self.assertEqual(result["status"], "valid")
        self.assertIn(expected_cache_key, app.API_VALIDATION_CACHE)
        self.assertTrue(all(api_key not in cache_key for cache_key in app.API_VALIDATION_CACHE))


if __name__ == "__main__":
    unittest.main()
