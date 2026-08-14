from __future__ import annotations

import numpy as np
import pandas as pd
import unittest

from src.crisis_regime import _probability_of_hitting_regime, run_markov_crisis_forecast


def synthetic_regime_prices(rows: int = 1100) -> pd.DataFrame:
    rng = np.random.default_rng(29)
    volatility = np.full(rows, 0.007)
    volatility[350:470] = 0.035
    volatility[800:900] = 0.028
    returns = rng.normal(0.0001, volatility)
    prices = 70.0 * np.exp(np.cumsum(returns))
    return pd.DataFrame({"Date": pd.bdate_range("2020-01-02", periods=rows), "Brent": prices})


class CrisisRegimeForecastTests(unittest.TestCase):
    def test_markov_forecast_returns_bounded_probabilities_and_two_regimes(self) -> None:
        result = run_markov_crisis_forecast(synthetic_regime_prices(), max_history=1100)

        for probability in [
            result.current_probability,
            result.probability_1d,
            result.probability_5d,
        ]:
            self.assertGreaterEqual(probability, 0.0)
            self.assertLessEqual(probability, 1.0)
        self.assertGreater(result.crisis_annualized_volatility, result.calm_annualized_volatility)
        self.assertEqual(result.transition_matrix.shape, (2, 2))
        self.assertEqual(len(result.probability_history), 1099)

    def test_hitting_probability_increases_with_horizon(self) -> None:
        transition = np.array([[0.96, 0.20], [0.04, 0.80]])
        current = np.array([1.0, 0.0])

        one_day = _probability_of_hitting_regime(current, transition, 1, 1)
        five_day = _probability_of_hitting_regime(current, transition, 1, 5)

        self.assertAlmostEqual(one_day, 0.04)
        self.assertGreater(five_day, one_day)

    def test_one_day_hitting_probability_matches_next_state_probability(self) -> None:
        transition = np.array([[0.96, 0.20], [0.04, 0.80]])
        current = np.array([0.25, 0.75])

        expected = float((transition @ current)[1])
        actual = _probability_of_hitting_regime(current, transition, 1, 1)

        self.assertAlmostEqual(actual, expected)

    def test_short_price_history_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "500"):
            run_markov_crisis_forecast(synthetic_regime_prices(300))


if __name__ == "__main__":
    unittest.main()
