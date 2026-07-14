"""Cloud-safety and result-export tests for the Streamlit application."""

from __future__ import annotations

from io import BytesIO
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

    def test_cloud_tool_menu_returns_before_local_maintenance_controls(self) -> None:
        from app import streamlit_app as app

        with (
            patch.object(app, "is_cloud_runtime", return_value=True),
            patch.object(app, "api_key_status") as api_key_status,
        ):
            app.render_top_tool_menu()

        api_key_status.assert_not_called()


if __name__ == "__main__":
    unittest.main()
