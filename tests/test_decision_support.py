from __future__ import annotations

from types import SimpleNamespace
import unittest

import pandas as pd

from src.decision_support import build_buyer_hedge_scenarios, build_investment_decision


def sample_result() -> SimpleNamespace:
    return SimpleNamespace(
        metrics={
            "LatestPrice": 80.0,
            "ProjectedChangePercent": 6.0,
            "DirectionalAccuracyPercent": 62.0,
        },
        forecast=pd.DataFrame(
            {
                "Date": pd.to_datetime(["2026-08-24", "2026-09-18"]),
                "PointForecast": [82.0, 84.8],
                "Lower80": [77.0, 76.0],
                "Upper80": [87.0, 92.0],
                "Lower95": [74.0, 70.0],
                "Upper95": [90.0, 98.0],
            }
        ),
    )


class DecisionSupportTests(unittest.TestCase):
    def test_investment_signal_is_bounded_and_validated(self) -> None:
        decision = build_investment_decision(sample_result())
        self.assertGreater(decision.score, 0)
        self.assertLessEqual(decision.position_high, 0.35)
        self.assertFalse(decision.gated)

    def test_hedge_scenario_reconciles_net_cost(self) -> None:
        scenarios = build_buyer_hedge_scenarios(
            sample_result(),
            exposure_volume=100_000,
            budget_price=82.0,
            hedge_ratio=0.60,
            futures_share=0.70,
            option_premium=2.0,
        )
        calculated = (
            scenarios["PhysicalCost"]
            - scenarios["FuturesPnL"]
            - scenarios["OptionPayoff"]
            + scenarios["OptionPremium"]
        )
        pd.testing.assert_series_equal(calculated, scenarios["NetCost"], check_names=False)
        self.assertTrue((scenarios["Contracts"] == 60).all())

    def test_detailed_procurement_conditions_reconcile_local_cost(self) -> None:
        scenarios = build_buyer_hedge_scenarios(
            sample_result(),
            exposure_volume=100_000,
            budget_price=82.0,
            hedge_ratio=0.60,
            futures_share=0.70,
            option_strike=84.0,
            option_premium=1.5,
            budget_basis=1.0,
            purchase_basis=2.5,
            budget_fx_rate=7.10,
            settlement_fx_rate=7.25,
            futures_entry_price=81.0,
            margin_rate=0.12,
            annual_funding_rate=0.045,
            holding_days=60,
            futures_fee_per_contract=8.0,
        )
        row = scenarios.iloc[2]
        self.assertEqual(row["FuturesContracts"], 42)
        self.assertAlmostEqual(row["PhysicalUnitPrice"], row["OilPrice"] + 2.5)
        self.assertAlmostEqual(row["NetCostCNY"], row["NetCost"] * 7.25)
        self.assertAlmostEqual(row["BudgetCostCNY"], 100_000 * 83.0 * 7.10)
        self.assertAlmostEqual(row["BasisImpactCNY"], 100_000 * 1.5 * 7.25)
        self.assertAlmostEqual(row["InitialMargin"], 42_000 * 81.0 * 0.12)
        self.assertGreater(row["MarginFundingCost"], 0.0)

    def test_detailed_procurement_conditions_validate_fx_and_holding_period(self) -> None:
        with self.assertRaisesRegex(ValueError, "FX rates"):
            build_buyer_hedge_scenarios(
                sample_result(), exposure_volume=1_000, budget_price=80.0, settlement_fx_rate=0.0
            )
        with self.assertRaisesRegex(ValueError, "Holding days"):
            build_buyer_hedge_scenarios(
                sample_result(), exposure_volume=1_000, budget_price=80.0, holding_days=-1
            )


if __name__ == "__main__":
    unittest.main()
