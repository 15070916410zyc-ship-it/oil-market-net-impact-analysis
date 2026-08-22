"""Paper-aligned five-IMF oil-price forecasting baseline.

The original paper models interval high/low prices with CEMD, BPNN and ACI.
The website currently stores daily Brent and WTI point series rather than the
full high/low interval.  This module therefore provides a transparent point-price
baseline: five frequency-ordered VMD components, a neural-network model for
the highest-frequency component, autoregressive ridge models for the remaining
components, and an empirical validation-error band after reconstruction.
"""

from __future__ import annotations

from dataclasses import dataclass
import warnings

import numpy as np
import pandas as pd
from sklearn.exceptions import ConvergenceWarning
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.neural_network import MLPRegressor
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from src.quick_analysis import IMF_CHANNELS
from src.vmd_module import estimate_center_frequency, run_vmd


PREDICTION_INTERVAL_LEVELS = (50, 60, 70, 80, 90, 95, 99)


@dataclass(frozen=True)
class PriceForecastResult:
    """Forecast outputs used by the Streamlit result page."""

    history: pd.DataFrame
    forecast: pd.DataFrame
    components: pd.DataFrame
    metrics: dict[str, float | int | str]
    model_summary: pd.DataFrame


def _clean_price_data(data: pd.DataFrame, price_column: str) -> pd.DataFrame:
    required = {"Date", price_column}
    missing = required - set(data.columns)
    if missing:
        raise ValueError(f"Price data is missing required columns: {sorted(missing)}")
    cleaned = data[["Date", price_column]].copy()
    cleaned["Date"] = pd.to_datetime(cleaned["Date"], errors="coerce")
    cleaned[price_column] = pd.to_numeric(cleaned[price_column], errors="coerce")
    cleaned = (
        cleaned.dropna()
        .drop_duplicates(subset=["Date"], keep="last")
        .sort_values("Date")
        .reset_index(drop=True)
    )
    if len(cleaned) < 180:
        raise ValueError(f"At least 180 valid {price_column} observations are required for forecasting.")
    return cleaned


def _frequency_ordered_imfs(values: np.ndarray, count: int = 5) -> tuple[np.ndarray, list[float]]:
    raw = run_vmd(values, K=count, alpha=1000)
    frequencies = [estimate_center_frequency(raw[:, index])[0] for index in range(count)]
    order = sorted(
        range(count),
        key=lambda index: frequencies[index] if np.isfinite(frequencies[index]) else -np.inf,
        reverse=True,
    )
    return raw[:, order], [frequencies[index] for index in order]


def _lagged_xy(values: np.ndarray, lags: int) -> tuple[np.ndarray, np.ndarray]:
    if len(values) <= lags:
        raise ValueError("The component series is too short for the selected lag length.")
    x = np.vstack([values[index - lags : index] for index in range(lags, len(values))])
    y = values[lags:]
    return x, y


def _component_model(component_index: int):
    if component_index == 0:
        return make_pipeline(
            StandardScaler(),
            MLPRegressor(
                hidden_layer_sizes=(24, 12),
                activation="tanh",
                solver="lbfgs",
                alpha=0.001,
                max_iter=500,
                random_state=42,
            ),
        )
    return make_pipeline(StandardScaler(), Ridge(alpha=1.0 + component_index * 0.35))


def _recursive_component_forecast(
    values: np.ndarray,
    horizon: int,
    component_index: int,
    lags: int,
) -> np.ndarray:
    x, y = _lagged_xy(values, lags)
    model = _component_model(component_index)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", ConvergenceWarning)
        model.fit(x, y)
    working = list(np.asarray(values, dtype=float))
    output: list[float] = []
    for _ in range(horizon):
        next_value = float(model.predict(np.asarray(working[-lags:]).reshape(1, -1))[0])
        output.append(next_value)
        working.append(next_value)
    return np.asarray(output)


def _forecast_from_signal(
    values: np.ndarray,
    horizon: int,
    lags: int,
) -> tuple[np.ndarray, np.ndarray, list[float]]:
    imfs, frequencies = _frequency_ordered_imfs(values, count=5)
    component_predictions = np.column_stack(
        [
            _recursive_component_forecast(imfs[:, index], horizon, index, lags)
            for index in range(imfs.shape[1])
        ]
    )
    reconstructed = component_predictions.sum(axis=1)
    reconstruction_gap = float(values[-1] - imfs[-1].sum())
    reconstructed = reconstructed + reconstruction_gap
    return reconstructed, component_predictions, frequencies


def _split_conformal_radius(errors: np.ndarray, level: int) -> float:
    """Return a finite-sample absolute-error radius from calibration data only."""
    absolute_errors = np.sort(np.abs(np.asarray(errors, dtype=float)))
    absolute_errors = absolute_errors[np.isfinite(absolute_errors)]
    if absolute_errors.size == 0:
        raise ValueError("Prediction-interval calibration requires at least one finite error.")
    coverage = float(level) / 100.0
    rank = int(np.ceil((absolute_errors.size + 1) * coverage))
    index = min(max(rank, 1), absolute_errors.size) - 1
    return max(float(absolute_errors[index]), 0.50)


def run_oil_price_forecast(
    data: pd.DataFrame,
    *,
    price_column: str = "Brent",
    horizon: int = 20,
    max_history: int = 1500,
    lags: int = 12,
) -> PriceForecastResult:
    """Generate a five-IMF oil-price forecast with empirical prediction intervals.

    Validation decomposition uses only the pre-holdout signal, avoiding future
    information in the displayed holdout metrics.  The final future forecast is
    then fitted to all observations available at run time.  The configured
    prediction intervals use finite-sample holdout-error quantiles and widen
    gradually across the forecast horizon.
    """
    if horizon < 1 or horizon > 120:
        raise ValueError("Forecast horizon must be between 1 and 120 business days.")
    cleaned = _clean_price_data(data, price_column).tail(max_history).reset_index(drop=True)
    values = cleaned[price_column].to_numpy(dtype=float)
    # One chronological holdout is forecast from a genuinely earlier origin.
    # Its first half calibrates the empirical ranges; the second half evaluates
    # them without feeding those evaluation outcomes back into the ranges.
    holdout = min(max(40, int(horizon) * 2), 120, len(values) // 3)
    calibration_observations = holdout // 2
    train_values = values[:-holdout]
    validation_forecast, _, _ = _forecast_from_signal(train_values, holdout, lags)
    validation_actual = values[-holdout:]
    calibration_errors = (
        validation_actual[:calibration_observations]
        - validation_forecast[:calibration_observations]
    )
    evaluation_actual = validation_actual[calibration_observations:]
    evaluation_forecast = validation_forecast[calibration_observations:]

    point_forecast, component_forecasts, frequencies = _forecast_from_signal(values, horizon, lags)
    widening = np.sqrt(1.0 + np.arange(horizon) / max(holdout - 1, 1))
    validation_widening = np.sqrt(
        1.0 + np.arange(holdout) / max(calibration_observations - 1, 1)
    )
    future_dates = pd.bdate_range(cleaned["Date"].iloc[-1] + pd.offsets.BDay(1), periods=horizon)
    forecast_data: dict[str, object] = {
        "Date": future_dates,
        "PointForecast": point_forecast,
    }
    interval_radii: dict[int, float] = {}
    validation_coverages: dict[int, float] = {}
    for level in PREDICTION_INTERVAL_LEVELS:
        empirical_radius = _split_conformal_radius(calibration_errors, level)
        interval_radii[level] = empirical_radius
        radius = empirical_radius * widening
        forecast_data[f"Lower{level}"] = point_forecast - radius
        forecast_data[f"Upper{level}"] = point_forecast + radius
        evaluation_radius = (
            empirical_radius * validation_widening[calibration_observations:]
        )
        covered = (
            (evaluation_actual >= evaluation_forecast - evaluation_radius)
            & (evaluation_actual <= evaluation_forecast + evaluation_radius)
        )
        validation_coverages[level] = float(np.mean(covered) * 100.0)
    forecast = pd.DataFrame(forecast_data)

    component_rows: list[dict[str, object]] = []
    model_rows: list[dict[str, object]] = []
    for index in range(5):
        imf = f"IMF{index + 1}"
        channel = IMF_CHANNELS[imf]
        model_name = "BPNN" if index == 0 else "AR-Ridge"
        model_rows.append(
            {
                "IMF": imf,
                "ChannelEN": channel["channel_en"],
                "ChannelZH": channel["channel_zh"],
                "Model": model_name,
                "CenterFrequency": frequencies[index],
            }
        )
        for date, value in zip(future_dates, component_forecasts[:, index]):
            component_rows.append(
                {
                    "Date": date,
                    "IMF": imf,
                    "ChannelEN": channel["channel_en"],
                    "ChannelZH": channel["channel_zh"],
                    "Forecast": float(value),
                }
            )

    prior_actual = np.r_[
        validation_actual[calibration_observations - 1],
        evaluation_actual[:-1],
    ]
    prior_forecast = np.r_[
        validation_forecast[calibration_observations - 1],
        evaluation_forecast[:-1],
    ]
    actual_direction = np.sign(evaluation_actual - prior_actual)
    forecast_direction = np.sign(evaluation_forecast - prior_forecast)
    validation_mae = float(mean_absolute_error(evaluation_actual, evaluation_forecast))
    naive_forecast = np.full_like(
        evaluation_actual,
        validation_actual[calibration_observations - 1],
        dtype=float,
    )
    naive_mae = float(mean_absolute_error(evaluation_actual, naive_forecast))
    skill_percent = (
        float((1.0 - validation_mae / naive_mae) * 100.0)
        if naive_mae > 1e-12
        else 0.0
    )
    metrics: dict[str, float | int | str] = {
        "Target": price_column,
        "AsOfDate": cleaned["Date"].iloc[-1].strftime("%Y-%m-%d"),
        "ForecastHorizon": int(horizon),
        "LatestPrice": float(values[-1]),
        "ForecastEndPrice": float(point_forecast[-1]),
        "ProjectedChangePercent": float((point_forecast[-1] / values[-1] - 1.0) * 100.0),
        "ValidationMAE": validation_mae,
        "ValidationRMSE": float(mean_squared_error(evaluation_actual, evaluation_forecast) ** 0.5),
        "DirectionalAccuracyPercent": float(np.mean(actual_direction == forecast_direction) * 100.0),
        "ValidationNaiveMAE": naive_mae,
        "ValidationSkillPercent": skill_percent,
        "CalibrationObservations": int(calibration_observations),
        "ValidationObservations": int(len(evaluation_actual)),
        "ValidationStartDate": cleaned["Date"].iloc[-len(evaluation_actual)].strftime("%Y-%m-%d"),
        "ValidationEndDate": cleaned["Date"].iloc[-1].strftime("%Y-%m-%d"),
        "PredictionIntervalMethod": "chronological split calibration and evaluation",
    }
    for level in PREDICTION_INTERVAL_LEVELS:
        metrics[f"ValidationCoverage{level}Percent"] = validation_coverages[level]
        metrics[f"CalibrationRadius{level}"] = interval_radii[level]
    history = cleaned.tail(240).rename(columns={price_column: "Actual"})
    return PriceForecastResult(
        history=history,
        forecast=forecast,
        components=pd.DataFrame(component_rows),
        metrics=metrics,
        model_summary=pd.DataFrame(model_rows),
    )


def run_brent_price_forecast(
    data: pd.DataFrame,
    *,
    price_column: str = "Brent",
    horizon: int = 20,
    max_history: int = 1500,
    lags: int = 12,
) -> PriceForecastResult:
    """Backward-compatible wrapper around :func:`run_oil_price_forecast`."""
    return run_oil_price_forecast(
        data,
        price_column=price_column,
        horizon=horizon,
        max_history=max_history,
        lags=lags,
    )
