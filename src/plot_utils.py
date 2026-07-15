"""Shared plotting helpers for date-axis figures."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Iterable

import matplotlib.pyplot as plt
import pandas as pd


DEFAULT_RASTER_PIXEL_BUDGET = 6_000_000


def apply_publication_plot_style(**overrides: Any) -> None:
    """Apply a portable publication style without requesting system fonts.

    Matplotlib ships DejaVu Serif on every supported platform, including the
    Linux image used by Streamlit Community Cloud.  Using it prevents the
    thousands of repeated ``findfont`` warnings emitted for Times New Roman.
    """
    settings: dict[str, Any] = {
        "font.family": "DejaVu Serif",
        "axes.facecolor": "white",
        "figure.facecolor": "white",
        "savefig.facecolor": "white",
    }
    settings.update(overrides)
    plt.rcParams.update(settings)


def safe_raster_dpi(
    figure: plt.Figure,
    requested_dpi: int = 600,
    max_pixels: int = DEFAULT_RASTER_PIXEL_BUDGET,
) -> int:
    """Return a DPI that keeps rasterization within a fixed pixel budget."""
    width_inches, height_inches = figure.get_size_inches()
    area_inches = max(float(width_inches) * float(height_inches), 1.0)
    budget_dpi = int(math.floor(math.sqrt(max(1, int(max_pixels)) / area_inches)))
    return max(1, min(int(requested_dpi), budget_dpi))


def save_figure_pair(
    figure: plt.Figure,
    png_path: str | Path,
    pdf_path: str | Path,
    requested_dpi: int = 600,
) -> None:
    """Save raster/vector copies and always release the Matplotlib figure."""
    png = Path(png_path)
    pdf = Path(pdf_path)
    png.parent.mkdir(parents=True, exist_ok=True)
    pdf.parent.mkdir(parents=True, exist_ok=True)
    try:
        figure.savefig(
            png,
            dpi=safe_raster_dpi(figure, requested_dpi=requested_dpi),
            bbox_inches="tight",
        )
        figure.savefig(pdf, bbox_inches="tight")
    finally:
        plt.close(figure)


def normalise_plot_date(value: Any) -> pd.Timestamp | None:
    """Return one timezone-free normalized date for plotting annotations."""
    timestamp = pd.to_datetime(value, errors="coerce")
    if pd.isna(timestamp):
        return None
    timestamp = pd.Timestamp(timestamp)
    if timestamp.tzinfo is not None:
        timestamp = timestamp.tz_localize(None)
    return timestamp.normalize()


def _even_date_ticks(
    start: pd.Timestamp,
    end: pd.Timestamp,
    max_ticks: int,
) -> list[pd.Timestamp]:
    """Return evenly spaced date ticks that always include start and end."""
    start = start.normalize()
    end = end.normalize()
    if end <= start:
        return [start]
    span_days = max(1, (end - start).days)
    tick_count = max(2, min(max_ticks, span_days + 1))
    offsets = [round(index * span_days / (tick_count - 1)) for index in range(tick_count)]
    ticks = [start + pd.Timedelta(days=int(offset)) for offset in offsets]
    ticks[0] = start
    ticks[-1] = end
    unique_ticks: list[pd.Timestamp] = []
    for tick in ticks:
        if not unique_ticks or tick != unique_ticks[-1]:
            unique_ticks.append(tick)
    return unique_ticks


def mark_start_end_dates(
    ax: plt.Axes,
    dates: Any,
    start_date: Any | None = None,
    end_date: Any | None = None,
    line_axes: Iterable[plt.Axes] | None = None,
    annotate: bool = True,
) -> None:
    """Mark start/end dates and avoid nearby tick-label collisions."""
    parsed_dates = pd.to_datetime(pd.Series(dates), errors="coerce").dropna()
    if parsed_dates.empty:
        return
    data_start = normalise_plot_date(parsed_dates.min())
    data_end = normalise_plot_date(parsed_dates.max())
    label_start = normalise_plot_date(start_date) or data_start
    label_end = normalise_plot_date(end_date) or data_end
    if data_start is None or data_end is None or label_start is None or label_end is None:
        return
    label_start = max(data_start, min(label_start, data_end))
    label_end = max(data_start, min(label_end, data_end))
    if label_end < label_start:
        label_start, label_end = label_end, label_start

    figure_width = ax.figure.get_size_inches()[0] if ax.figure is not None else 8
    max_ticks = max(2, min(6, int(figure_width // 1.8)))
    ticks = _even_date_ticks(label_start, label_end, max_ticks=max_ticks)
    labels = []
    for tick in ticks:
        if tick == label_start:
            labels.append(f"Start\n{tick:%Y-%m-%d}")
        elif tick == label_end:
            labels.append(f"End\n{tick:%Y-%m-%d}")
        else:
            labels.append(tick.strftime("%Y-%m-%d"))

    ax.set_xlim(label_start, label_end)
    ax.set_xticks(ticks)
    ax.set_xticklabels(labels, rotation=30, ha="right")
    ax.tick_params(axis="x", labelsize=10, colors="#111827")
    targets = list(line_axes) if line_axes is not None else [ax]
    for target_ax in targets:
        target_ax.axvline(label_start, color="#111827", linestyle=":", linewidth=1.1)
        target_ax.axvline(label_end, color="#111827", linestyle=":", linewidth=1.1)

    if not annotate:
        return
    ax.annotate(
        "Start",
        xy=(label_start, 1.0),
        xycoords=("data", "axes fraction"),
        xytext=(3, -8),
        textcoords="offset points",
        ha="left",
        va="top",
        fontsize=8,
        color="#111827",
    )
    ax.annotate(
        "End",
        xy=(label_end, 1.0),
        xycoords=("data", "axes fraction"),
        xytext=(-3, -8),
        textcoords="offset points",
        ha="right",
        va="top",
        fontsize=8,
        color="#111827",
    )
