"""Literature-based Markov-switching oil-crisis regime forecast.

The model is intentionally separate from the existing five-day Random Forest
warning.  It follows Hamilton's two-state regime-switching framework and labels
the state with the larger return variance as the oil-market crisis regime.
"""

from __future__ import annotations

from dataclasses import dataclass
import warnings

import numpy as np
import pandas as pd
from statsmodels.tsa.regime_switching.markov_regression import MarkovRegression


@dataclass(frozen=True)
class CrisisRegimeForecast:
    """Outputs for the independent Hamilton regime-probability panel."""

    target: str
    latest_date: pd.Timestamp
    current_probability: float
    probability_1d: float
    probability_5d: float
    crisis_regime: int
    crisis_persistence: float
    expected_duration_days: float
    calm_annualized_volatility: float
    crisis_annualized_volatility: float
    converged: bool
    aic: float
    bic: float
    probability_history: pd.DataFrame
    transition_matrix: pd.DataFrame
    model_note: str


def _clean_price_series(
    data: pd.DataFrame,
    price_column: str,
    max_history: int,
) -> pd.Series:
    if "Date" not in data or price_column not in data:
        raise ValueError(f"Regime data must contain Date and {price_column}.")
    frame = data[["Date", price_column]].copy()
    frame["Date"] = pd.to_datetime(frame["Date"], errors="coerce")
    frame[price_column] = pd.to_numeric(frame[price_column], errors="coerce")
    frame = (
        frame.dropna()
        .drop_duplicates("Date", keep="last")
        .sort_values("Date")
        .tail(max_history)
    )
    frame = frame[frame[price_column] > 0]
    if len(frame) < 500:
        raise ValueError("At least 500 positive oil-price observations are required.")
    return frame.set_index("Date")[price_column]


def _probability_of_hitting_regime(
    current: np.ndarray,
    transition: np.ndarray,
    target_regime: int,
    horizon: int,
) -> float:
    """Probability of entering ``target_regime`` at least once in future steps."""
    if horizon < 1:
        raise ValueError("Forecast horizon must be positive.")
    alive = np.asarray(current, dtype=float).copy()
    for _ in range(horizon):
        alive = transition @ alive
        alive[target_regime] = 0.0
    return float(np.clip(1.0 - alive.sum(), 0.0, 1.0))


def run_markov_crisis_forecast(
    data: pd.DataFrame,
    *,
    price_column: str = "Brent",
    max_history: int = 2500,
    horizon: int = 5,
) -> CrisisRegimeForecast:
    """Forecast the probability of an oil high-volatility regime.

    A two-state Gaussian Markov regression with regime-specific means and
    variances is fitted to daily log returns.  The regime with the larger
    conditional variance is labelled the crisis regime.  The five-day output
    is the probability of visiting that regime at least once over the next five
    trading days, conditional on the latest filtered state probabilities.
    """
    prices = _clean_price_series(data, price_column, max_history)
    returns = (np.log(prices).diff().dropna() * 100.0).rename("ReturnPercent")
    model = MarkovRegression(
        returns.to_numpy(dtype=float),
        k_regimes=2,
        trend="c",
        switching_trend=True,
        switching_variance=True,
    )
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        fitted = model.fit(
            disp=False,
            maxiter=400,
            em_iter=20,
            search_reps=0,
        )
    converged = bool(getattr(fitted, "mle_retvals", {}).get("converged", False))
    if not converged:
        raise ValueError("Hamilton Markov-switching estimation did not converge.")

    param_names = list(fitted.model.param_names)
    parameters = np.asarray(fitted.params, dtype=float)
    variances = np.asarray(
        [parameters[param_names.index(f"sigma2[{regime}]")] for regime in range(2)],
        dtype=float,
    )
    if not np.isfinite(variances).all() or np.any(variances <= 0):
        raise ValueError("Markov model returned invalid regime variances.")
    crisis_regime = int(np.argmax(variances))
    calm_regime = 1 - crisis_regime

    filtered = np.asarray(fitted.filtered_marginal_probabilities, dtype=float)
    if filtered.shape != (len(returns), 2):
        raise ValueError("Markov model returned an unexpected probability shape.")
    transition_raw = np.asarray(fitted.regime_transition, dtype=float)
    transition = transition_raw[:, :, -1] if transition_raw.ndim == 3 else transition_raw
    current = filtered[-1]
    next_distribution = transition @ current
    probability_1d = float(np.clip(next_distribution[crisis_regime], 0.0, 1.0))
    probability_5d = _probability_of_hitting_regime(
        current,
        transition,
        crisis_regime,
        horizon,
    )
    persistence = float(np.clip(transition[crisis_regime, crisis_regime], 0.0, 1.0))
    expected_duration = float(1.0 / max(1.0 - persistence, 1e-9))

    probability_history = pd.DataFrame(
        {
            "Date": returns.index,
            "CrisisRegimeProbability": filtered[:, crisis_regime] * 100.0,
            "Price": prices.reindex(returns.index).to_numpy(dtype=float),
        }
    )
    labels = ["Calm regime", "Crisis regime"]
    ordered_regimes = [calm_regime, crisis_regime]
    transition_matrix = pd.DataFrame(
        transition[np.ix_(ordered_regimes, ordered_regimes)],
        index=[f"To {label}" for label in labels],
        columns=[f"From {label}" for label in labels],
    )
    return CrisisRegimeForecast(
        target=price_column,
        latest_date=pd.Timestamp(returns.index[-1]),
        current_probability=float(np.clip(current[crisis_regime], 0.0, 1.0)),
        probability_1d=probability_1d,
        probability_5d=probability_5d,
        crisis_regime=crisis_regime,
        crisis_persistence=persistence,
        expected_duration_days=expected_duration,
        calm_annualized_volatility=float(np.sqrt(variances[calm_regime]) * np.sqrt(252.0)),
        crisis_annualized_volatility=float(np.sqrt(variances[crisis_regime]) * np.sqrt(252.0)),
        converged=converged,
        aic=float(fitted.aic),
        bic=float(fitted.bic),
        probability_history=probability_history,
        transition_matrix=transition_matrix,
        model_note=(
            "Hamilton two-state Markov-switching forecast. The probability refers to an oil-price "
            "high-volatility regime, not the date or cause of a geopolitical or macroeconomic crisis."
        ),
    )
