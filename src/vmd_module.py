"""Variational Mode Decomposition (VMD) utilities for WTI.

The decomposition can use a configurable number of IMFs. The IMF order is the
raw output order from ``vmdpy.VMD`` and is not reordered by center frequency.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from src.plot_utils import apply_publication_plot_style, mark_start_end_dates, save_figure_pair


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT_PATH = PROJECT_ROOT / "data" / "processed" / "model_ready_data.xlsx"
DEFAULT_OUTPUT_PATH = PROJECT_ROOT / "data" / "processed" / "wti_vmd_imfs.xlsx"
CHANGE_INPUT_PATH = PROJECT_ROOT / "data" / "processed" / "wti_change_data.xlsx"
CHANGE_OUTPUT_PATH = PROJECT_ROOT / "data" / "processed" / "wti_change_vmd_imfs.xlsx"
DIAGNOSTICS_PATH = PROJECT_ROOT / "outputs" / "tables" / "vmd_diagnostics.xlsx"
CHANGE_DIAGNOSTICS_PATH = PROJECT_ROOT / "outputs" / "tables" / "wti_change_vmd_diagnostics.xlsx"
FIGURE_PNG_PATH = PROJECT_ROOT / "outputs" / "figures" / "wti_vmd_decomposition.png"
FIGURE_PDF_PATH = PROJECT_ROOT / "outputs" / "figures" / "wti_vmd_decomposition.pdf"
CHANGE_FIGURE_PNG_PATH = PROJECT_ROOT / "outputs" / "figures" / "wti_change_vmd_decomposition.png"
CHANGE_FIGURE_PDF_PATH = PROJECT_ROOT / "outputs" / "figures" / "wti_change_vmd_decomposition.pdf"


def _resolve_project_path(path: str | Path) -> Path:
    """Resolve a relative path against the project root."""
    path = Path(path)
    if path.is_absolute():
        return path
    return PROJECT_ROOT / path


def _ensure_output_directories() -> None:
    """Create output directories used by VMD artifacts."""
    DEFAULT_OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    DIAGNOSTICS_PATH.parent.mkdir(parents=True, exist_ok=True)
    FIGURE_PNG_PATH.parent.mkdir(parents=True, exist_ok=True)


def imf_columns_from_frame(data: pd.DataFrame, prefix: str = "WTI_IMF") -> list[str]:
    """Return IMF columns sorted by numeric suffix."""
    columns: list[tuple[int, str]] = []
    for column in data.columns:
        text = str(column)
        if not text.startswith(prefix):
            continue
        suffix = text.replace(prefix, "", 1)
        if suffix.isdigit():
            columns.append((int(suffix), text))
    return [column for _, column in sorted(columns)]


def estimate_center_frequency(values: pd.Series | np.ndarray) -> tuple[float, float]:
    """Estimate spectral center frequency and period for one IMF.

    Frequency is reported in cycles per observation. The period is therefore
    measured in observations/trading days for daily data.
    """
    array = np.asarray(values, dtype=float).reshape(-1)
    array = array[np.isfinite(array)]
    if len(array) < 3 or np.nanstd(array) <= 1e-12:
        return np.nan, np.nan
    centered = array - np.nanmean(array)
    spectrum = np.fft.rfft(centered)
    frequencies = np.fft.rfftfreq(len(centered), d=1.0)
    power = np.abs(spectrum) ** 2
    if len(power) > 1:
        frequencies = frequencies[1:]
        power = power[1:]
    total_power = float(np.nansum(power))
    if total_power <= 0 or not np.isfinite(total_power):
        return np.nan, np.nan
    center_frequency = float(np.nansum(frequencies * power) / total_power)
    center_period = float(1.0 / center_frequency) if center_frequency > 0 else np.nan
    return center_frequency, center_period


def load_model_ready_data(
    input_path: str | Path = DEFAULT_INPUT_PATH,
) -> pd.DataFrame:
    """Load model-ready WTI data.

    Args:
        input_path: Path to ``model_ready_data.xlsx``.

    Returns:
        DataFrame sorted by Date with non-missing WTI values.
    """
    path = _resolve_project_path(input_path)
    if not path.exists():
        raise FileNotFoundError(f"Model-ready data not found: {path}")

    data = pd.read_excel(path)
    required_columns = {"Date", "WTI"}
    missing_columns = required_columns - set(data.columns)
    if missing_columns:
        raise ValueError(f"Input data must contain columns: {sorted(missing_columns)}")

    cleaned = data.copy()
    cleaned["Date"] = pd.to_datetime(cleaned["Date"], errors="coerce")
    cleaned = cleaned.dropna(subset=["Date", "WTI"])
    cleaned = cleaned.drop_duplicates(subset=["Date"], keep="last")
    cleaned = cleaned.sort_values("Date").reset_index(drop=True)
    return cleaned


def run_vmd(
    series: pd.Series | np.ndarray,
    K: int = 4,
    alpha: float = 1000,
    tau: float = 0,
    DC: int = 0,
    init: int = 1,
    tol: float = 1e-7,
) -> np.ndarray:
    """Run VMD on a one-dimensional WTI series.

    Args:
        series: One-dimensional WTI sequence. It is not standardized.
        K: Number of IMFs.
        alpha: VMD bandwidth constraint.
        tau: VMD noise-tolerance parameter.
        DC: Whether to force the first mode to DC.
        init: Frequency initialization option passed to ``vmdpy.VMD``.
        tol: Convergence tolerance.

    Returns:
        IMF matrix with shape ``T x K``. The columns preserve the raw VMD
        output order and are not reordered by center frequency.
    """
    values = np.asarray(series, dtype=float).reshape(-1)
    original_length = len(values)
    if values.ndim != 1 or original_length == 0:
        raise ValueError("series must be a non-empty one-dimensional sequence.")
    if np.isnan(values).any():
        raise ValueError("series contains NaN values; clean WTI before running VMD.")

    # vmdpy can return one fewer point for odd-length signals because of its
    # internal mirrored extension. Padding only the temporary analysis vector
    # keeps the original WTI values unchanged while preserving a T x K output.
    analysis_values = values
    if original_length % 2 == 1:
        analysis_values = np.append(values, values[-1])

    u = _run_vmd_memory_efficient(analysis_values, alpha, tau, K, DC, init, tol)
    imf_matrix = np.asarray(u, dtype=float).T[:original_length, :]

    if imf_matrix.shape[1] != K:
        raise ValueError(f"Expected {K} IMFs, got shape {imf_matrix.shape}.")
    if imf_matrix.shape[0] != original_length:
        raise ValueError(
            f"Expected {original_length} rows after VMD, got {imf_matrix.shape[0]}."
        )

    return imf_matrix


def _run_vmd_memory_efficient(
    signal: np.ndarray,
    alpha: float,
    tau: float,
    mode_count: int,
    dc_mode: int,
    init: int,
    tolerance: float,
) -> np.ndarray:
    """Run the vmdpy algorithm using two iteration buffers instead of 500.

    ``vmdpy.VMD`` retains every complex spectrum for every iteration.  Its
    allocation therefore grows as ``500 * samples * modes`` and can exceed a
    hosted Streamlit worker's memory when the UI requests many modes.  The
    recurrence only needs the current and previous iteration, so two buffers
    preserve the numerical result with bounded memory.
    """
    values = np.asarray(signal, dtype=float).reshape(-1)
    if mode_count < 1:
        raise ValueError("K must be at least 1.")
    if len(values) % 2:
        values = values[:-1]

    sampling_frequency = 1.0 / len(values)
    half_length = len(values) // 2
    mirrored = np.append(np.flip(values[:half_length]), values)
    mirrored = np.append(mirrored, np.flip(values[-half_length:]))
    sample_count = len(mirrored)
    time = np.arange(1, sample_count + 1) / sample_count
    frequencies = time - 0.5 - (1 / sample_count)
    max_iterations = 500
    alpha_by_mode = float(alpha) * np.ones(mode_count)

    signal_spectrum = np.fft.fftshift(np.fft.fft(mirrored))
    positive_spectrum = np.copy(signal_spectrum)
    positive_spectrum[: sample_count // 2] = 0

    previous_omega = np.zeros(mode_count)
    if init == 1:
        previous_omega = np.arange(mode_count, dtype=float) * (0.5 / mode_count)
    elif init == 2:
        previous_omega = np.sort(
            np.exp(
                np.log(sampling_frequency)
                + (np.log(0.5) - np.log(sampling_frequency))
                * np.random.rand(mode_count)
            )
        )
    if dc_mode:
        previous_omega[0] = 0

    current_omega = np.zeros_like(previous_omega)
    previous_modes = np.zeros((sample_count, mode_count), dtype=complex)
    current_modes = np.zeros_like(previous_modes)
    previous_dual = np.zeros(sample_count, dtype=complex)
    current_dual = np.zeros_like(previous_dual)
    mode_sum: float | np.ndarray = 0.0
    difference = tolerance + np.spacing(1)
    iteration = 0

    while difference > tolerance and iteration < max_iterations - 1:
        mode_sum = previous_modes[:, mode_count - 1] + mode_sum - previous_modes[:, 0]
        current_modes[:, 0] = (
            positive_spectrum - mode_sum - previous_dual / 2
        ) / (1 + alpha_by_mode[0] * (frequencies - previous_omega[0]) ** 2)
        if not dc_mode:
            positive = current_modes[sample_count // 2 :, 0]
            power = np.abs(positive) ** 2
            current_omega[0] = np.dot(frequencies[sample_count // 2 :], power) / np.sum(power)

        for mode_index in range(1, mode_count):
            mode_sum = (
                current_modes[:, mode_index - 1]
                + mode_sum
                - previous_modes[:, mode_index]
            )
            current_modes[:, mode_index] = (
                positive_spectrum - mode_sum - previous_dual / 2
            ) / (
                1
                + alpha_by_mode[mode_index]
                * (frequencies - previous_omega[mode_index]) ** 2
            )
            positive = current_modes[sample_count // 2 :, mode_index]
            power = np.abs(positive) ** 2
            current_omega[mode_index] = (
                np.dot(frequencies[sample_count // 2 :], power) / np.sum(power)
            )

        current_dual[:] = previous_dual + tau * (
            np.sum(current_modes, axis=1) - positive_spectrum
        )
        iteration += 1
        difference = np.spacing(1)
        for mode_index in range(mode_count):
            delta = current_modes[:, mode_index] - previous_modes[:, mode_index]
            difference += (1 / sample_count) * np.dot(delta, np.conj(delta))
        difference = float(np.abs(difference))

        previous_modes, current_modes = current_modes, previous_modes
        previous_omega, current_omega = current_omega, previous_omega
        previous_dual, current_dual = current_dual, previous_dual

    # Match vmdpy's post-processing, which reconstructs from the penultimate
    # stored iteration (the buffer now named current_modes after the swap).
    final_modes = current_modes
    reverse_indices = np.flip(np.arange(1, sample_count // 2 + 1))
    full_spectrum = np.zeros((sample_count, mode_count), dtype=complex)
    full_spectrum[sample_count // 2 :, :] = final_modes[sample_count // 2 :, :]
    full_spectrum[reverse_indices, :] = np.conj(
        final_modes[sample_count // 2 :, :]
    )
    full_spectrum[0, :] = np.conj(full_spectrum[-1, :])

    decomposed = np.zeros((mode_count, sample_count))
    for mode_index in range(mode_count):
        decomposed[mode_index, :] = np.real(
            np.fft.ifft(np.fft.ifftshift(full_spectrum[:, mode_index]))
        )
    return decomposed[:, sample_count // 4 : 3 * sample_count // 4]


def decompose_vmd(
    series: pd.Series | np.ndarray,
    num_modes: int = 4,
) -> pd.DataFrame:
    """Decompose a WTI series into ``WTI_IMF1`` through ``WTI_IMF{num_modes}``."""
    imfs = run_vmd(series, K=num_modes)
    columns = [f"WTI_IMF{i}" for i in range(1, num_modes + 1)]
    return pd.DataFrame(imfs, columns=columns)


def decompose_wti_vmd(
    input_path: str | Path = DEFAULT_INPUT_PATH,
    output_path: str | Path = DEFAULT_OUTPUT_PATH,
    K: int = 4,
    alpha: float = 1000,
    tau: float = 0,
    DC: int = 0,
    init: int = 1,
    tol: float = 1e-7,
) -> pd.DataFrame:
    """Decompose WTI into VMD IMFs and save all VMD artifacts.

    Args:
        input_path: Path to model-ready WTI data.
        output_path: Destination workbook for decomposed IMFs.
        K: Number of IMFs.
        alpha: VMD bandwidth constraint.
        tau: VMD noise-tolerance parameter.
        DC: Whether to force the first mode to DC.
        init: Frequency initialization option.
        tol: Convergence tolerance.

    Returns:
        DataFrame containing WTI, IMFs, reconstruction, and error.
    """
    if K < 1:
        raise ValueError("K must be at least 1.")

    _ensure_output_directories()
    output_path = _resolve_project_path(output_path)
    data = load_model_ready_data(input_path)

    imf_matrix = run_vmd(
        data["WTI"].to_numpy(dtype=float),
        K=K,
        alpha=alpha,
        tau=tau,
        DC=DC,
        init=init,
        tol=tol,
    )

    imf_columns = [f"WTI_IMF{i}" for i in range(1, K + 1)]
    vmd_df = data[["Date", "WTI"]].copy()
    for idx, column in enumerate(imf_columns):
        vmd_df[column] = imf_matrix[:, idx]

    vmd_df["WTI_Reconstructed"] = vmd_df[imf_columns].sum(axis=1)
    vmd_df["WTI_Reconstruction_Error"] = (
        vmd_df["WTI"] - vmd_df["WTI_Reconstructed"]
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    vmd_df.to_excel(output_path, index=False)

    compute_vmd_diagnostics(vmd_df)
    plot_wti_vmd(vmd_df)

    return vmd_df


def compute_vmd_diagnostics(vmd_df: pd.DataFrame) -> pd.DataFrame:
    """Compute and save VMD IMF diagnostics.

    Args:
        vmd_df: DataFrame returned by ``decompose_wti_vmd``.

    Returns:
        Diagnostics table rounded to three decimals.
    """
    imf_columns = imf_columns_from_frame(vmd_df, prefix="WTI_IMF")
    validate_imf_frame(vmd_df, expected_modes=len(imf_columns), prefix="WTI_IMF")

    variances = vmd_df[imf_columns].var(ddof=0)
    variance_total = float(variances.sum())
    rows = []
    for column in imf_columns:
        variance = float(variances[column])
        contribution = variance / variance_total * 100 if variance_total else np.nan
        correlation = vmd_df[column].corr(vmd_df["WTI"])
        center_frequency, center_period = estimate_center_frequency(vmd_df[column])
        rows.append(
            {
                "IMF": column.replace("WTI_", ""),
                "Mean": vmd_df[column].mean(),
                "Std": vmd_df[column].std(ddof=0),
                "Variance": variance,
                "VarianceContributionPercent": contribution,
                "CorrelationWithWTI": correlation,
                "CenterFrequencyCyclesPerObservation": center_frequency,
                "CenterPeriodObservations": center_period,
            }
        )

    diagnostics = pd.DataFrame(rows).round(3)
    DIAGNOSTICS_PATH.parent.mkdir(parents=True, exist_ok=True)
    diagnostics.to_excel(DIAGNOSTICS_PATH, index=False)
    return diagnostics


def plot_wti_vmd(vmd_df: pd.DataFrame) -> None:
    """Plot and save the WTI VMD decomposition figure."""
    imf_columns = imf_columns_from_frame(vmd_df, prefix="WTI_IMF")
    validate_imf_frame(vmd_df, expected_modes=len(imf_columns), prefix="WTI_IMF")

    apply_publication_plot_style()

    plot_items = [("WTI", "WTI")]
    plot_items.extend((column, column.replace("WTI_", "")) for column in imf_columns)
    plot_items.append(("WTI_Reconstruction_Error", "Reconstruction Error"))

    fig, axes = plt.subplots(
        len(plot_items),
        1,
        figsize=(10, 12),
        sharex=True,
        constrained_layout=True,
    )

    dates = pd.to_datetime(vmd_df["Date"])
    for ax, (column, label) in zip(axes, plot_items):
        ax.plot(dates, vmd_df[column], color="black", linewidth=1.0)
        ax.set_ylabel(label)
        ax.grid(True, color="#d9d9d9", linewidth=0.5, alpha=0.8)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)

    axes[-1].set_xlabel("Date")
    mark_start_end_dates(axes[-1], dates, line_axes=axes)

    FIGURE_PNG_PATH.parent.mkdir(parents=True, exist_ok=True)
    save_figure_pair(fig, FIGURE_PNG_PATH, FIGURE_PDF_PATH)


def decompose_wti_change_vmd(
    input_path: str | Path = CHANGE_INPUT_PATH,
    output_path: str | Path = CHANGE_OUTPUT_PATH,
    K: int = 4,
    alpha: float = 1000,
    tau: float = 0,
    DC: int = 0,
    init: int = 1,
    tol: float = 1e-7,
) -> pd.DataFrame:
    """Decompose Delta_WTI into Delta_IMF1 through Delta_IMF{K} with VMD."""
    if K < 1:
        raise ValueError("K must be at least 1.")

    input_path = _resolve_project_path(input_path)
    output_path = _resolve_project_path(output_path)
    if not input_path.exists():
        raise FileNotFoundError(f"WTI change data not found: {input_path}")

    data = pd.read_excel(input_path)
    required_columns = {"Date", "WTI", "Delta_WTI"}
    missing_columns = required_columns - set(data.columns)
    if missing_columns:
        raise ValueError(f"{input_path} is missing columns: {sorted(missing_columns)}")

    data = data.copy()
    data["Date"] = pd.to_datetime(data["Date"], errors="coerce")
    data["WTI"] = pd.to_numeric(data["WTI"], errors="coerce")
    data["Delta_WTI"] = pd.to_numeric(data["Delta_WTI"], errors="coerce")
    data = data.dropna(subset=["Date", "WTI", "Delta_WTI"])
    data = data.drop_duplicates(subset=["Date"], keep="last")
    data = data.sort_values("Date").reset_index(drop=True)

    imf_matrix = run_vmd(
        data["Delta_WTI"].to_numpy(dtype=float),
        K=K,
        alpha=alpha,
        tau=tau,
        DC=DC,
        init=init,
        tol=tol,
    )

    result = data[["Date", "WTI", "Delta_WTI"]].copy()
    imf_columns = [f"Delta_IMF{i}" for i in range(1, K + 1)]
    for idx, column in enumerate(imf_columns):
        result[column] = imf_matrix[:, idx]

    result["Delta_Reconstructed"] = result[imf_columns].sum(axis=1)
    result["Delta_Reconstruction_Error"] = (
        result["Delta_WTI"] - result["Delta_Reconstructed"]
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    result.to_excel(output_path, index=False)
    compute_wti_change_vmd_diagnostics(result)
    plot_wti_change_vmd(result)
    return result


def compute_wti_change_vmd_diagnostics(vmd_df: pd.DataFrame) -> pd.DataFrame:
    """Compute diagnostics for Delta_WTI VMD decomposition."""
    imf_columns = imf_columns_from_frame(vmd_df, prefix="Delta_IMF")
    validate_imf_frame(vmd_df, expected_modes=len(imf_columns), prefix="Delta_IMF")

    variances = vmd_df[imf_columns].var(ddof=0)
    variance_total = float(variances.sum())
    rows = []
    for column in imf_columns:
        variance = float(variances[column])
        contribution = variance / variance_total * 100 if variance_total else np.nan
        correlation = vmd_df[column].corr(vmd_df["Delta_WTI"])
        center_frequency, center_period = estimate_center_frequency(vmd_df[column])
        rows.append(
            {
                "IMF": column,
                "Mean": vmd_df[column].mean(),
                "Std": vmd_df[column].std(ddof=0),
                "Variance": variance,
                "VarianceContributionPercent": contribution,
                "CorrelationWithDeltaWTI": correlation,
                "CenterFrequencyCyclesPerObservation": center_frequency,
                "CenterPeriodObservations": center_period,
            }
        )

    diagnostics = pd.DataFrame(rows).round(3)
    CHANGE_DIAGNOSTICS_PATH.parent.mkdir(parents=True, exist_ok=True)
    diagnostics.to_excel(CHANGE_DIAGNOSTICS_PATH, index=False)
    return diagnostics


def plot_wti_change_vmd(vmd_df: pd.DataFrame) -> None:
    """Plot and save Delta_WTI VMD decomposition."""
    imf_columns = imf_columns_from_frame(vmd_df, prefix="Delta_IMF")
    validate_imf_frame(vmd_df, expected_modes=len(imf_columns), prefix="Delta_IMF")

    apply_publication_plot_style()

    plot_items = [("Delta_WTI", "Delta WTI")]
    plot_items.extend((column, column.replace("Delta_", "")) for column in imf_columns)
    plot_items.append(("Delta_Reconstruction_Error", "Reconstruction Error"))

    fig, axes = plt.subplots(
        len(plot_items),
        1,
        figsize=(10, 12),
        sharex=True,
        constrained_layout=True,
    )
    dates = pd.to_datetime(vmd_df["Date"])
    for ax, (column, label) in zip(axes, plot_items):
        ax.plot(dates, vmd_df[column], color="black", linewidth=1.0)
        ax.set_ylabel(label)
        ax.grid(True, color="#d9d9d9", linewidth=0.5, alpha=0.8)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)

    axes[-1].set_xlabel("Date")
    mark_start_end_dates(axes[-1], dates, line_axes=axes)

    CHANGE_FIGURE_PNG_PATH.parent.mkdir(parents=True, exist_ok=True)
    save_figure_pair(fig, CHANGE_FIGURE_PNG_PATH, CHANGE_FIGURE_PDF_PATH)


def validate_imf_frame(
    imf_data: pd.DataFrame,
    expected_modes: int = 4,
    prefix: str = "WTI_IMF",
) -> None:
    """Validate that an IMF DataFrame contains the expected WTI IMF columns."""
    expected_columns = [f"{prefix}{i}" for i in range(1, expected_modes + 1)]
    missing_columns = [column for column in expected_columns if column not in imf_data]
    if missing_columns:
        raise ValueError(f"Missing IMF columns: {missing_columns}")
