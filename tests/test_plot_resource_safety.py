"""Regression tests for Streamlit Cloud plotting and VMD memory safety."""

from __future__ import annotations

from pathlib import Path
import unittest
from unittest.mock import patch

import matplotlib

matplotlib.use("Agg", force=True)
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


class PlotResourceSafetyTests(unittest.TestCase):
    def test_publication_style_uses_a_matplotlib_bundled_font(self) -> None:
        from matplotlib import font_manager

        from src.plot_utils import apply_publication_plot_style

        apply_publication_plot_style()

        configured_families = list(plt.rcParams["font.family"])
        self.assertNotIn("Times New Roman", configured_families)
        font_manager.findfont(configured_families[0], fallback_to_default=False)

    def test_raster_dpi_is_bounded_by_the_figure_pixel_budget(self) -> None:
        from src.plot_utils import safe_raster_dpi

        figure = plt.figure(figsize=(10, 136))
        try:
            dpi = safe_raster_dpi(figure, requested_dpi=600)
        finally:
            plt.close(figure)

        self.assertLess(dpi, 600)
        self.assertLessEqual(10 * dpi * 136 * dpi, 6_000_000)
        self.assertGreaterEqual(dpi, 1)

    def test_figure_is_closed_when_export_fails(self) -> None:
        from src.plot_utils import save_figure_pair

        figure = plt.figure(figsize=(4, 3))
        figure_number = figure.number
        with patch.object(figure, "savefig", side_effect=OSError("disk full")):
            with self.assertRaisesRegex(OSError, "disk full"):
                save_figure_pair(figure, Path("unused.png"), Path("unused.pdf"))

        self.assertNotIn(figure_number, plt.get_fignums())

    def test_run_vmd_avoids_vmdpy_iteration_history_allocation(self) -> None:
        from vmdpy import VMD

        from src.vmd_module import run_vmd

        x = np.linspace(0, 4 * np.pi, 64, endpoint=False)
        signal = np.sin(x) + 0.25 * np.sin(5 * x)
        expected, _, _ = VMD(signal, 1000, 0, 4, 0, 1, 1e-7)

        with patch("vmdpy.VMD", side_effect=AssertionError("legacy allocator used")):
            actual = run_vmd(signal, K=4)

        np.testing.assert_allclose(actual, expected.T, rtol=1e-10, atol=1e-10)

    def test_high_mode_vmd_figure_uses_a_compact_heatmap(self) -> None:
        from src.paper_replication import _create_vmd_decomposition_figure

        mode_count = 30
        dates = pd.date_range("2025-01-01", periods=32, freq="D")
        plot_data: dict[str, object] = {
            "Date": dates,
            "WTI": np.linspace(70, 75, len(dates)),
        }
        for mode_index in range(1, mode_count + 1):
            plot_data[f"WTI_IMF{mode_index}"] = np.sin(
                np.linspace(0, mode_index * np.pi, len(dates))
            )

        figure = _create_vmd_decomposition_figure(
            pd.DataFrame(plot_data),
            "WTI",
            mode_count,
        )
        try:
            self.assertLessEqual(len(figure.axes), 3)
            labels = [
                tick.get_text()
                for axis in figure.axes
                for tick in axis.get_yticklabels()
            ]
            self.assertIn("IMF1", labels)
            self.assertIn("IMF30", labels)
        finally:
            plt.close(figure)


if __name__ == "__main__":
    unittest.main()
