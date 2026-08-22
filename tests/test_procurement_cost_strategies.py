from __future__ import annotations

from types import SimpleNamespace
import unittest

import pandas as pd

from src.decision_support import (
    HedgeStage,
    HedgeStrategy,
    build_buyer_hedge_scenarios,
    compare_buyer_hedge_strategies,
)


def sample_result() -> SimpleNamespace:
    return SimpleNamespace(
        metrics={
            "LatestPrice": 80.0,
            "ProjectedChangePercent": 6.0,
            "DirectionalAccuracyPercent": 62.0,
        },
        forecast=pd.DataFrame(
            {
                "PointForecast": [82.0, 84.8],
                "Lower80": [77.0, 76.0],
                "Upper80": [87.0, 92.0],
                "Lower95": [74.0, 70.0],
                "Upper95": [90.0, 98.0],
            }
        ),
    )


class ProcurementCostStrategyTests(unittest.TestCase):
    def test_cost_components_collar_and_margin_liquidity_reconcile(self) -> None:
        scenarios = build_buyer_hedge_scenarios(
            sample_result(),
            exposure_volume=100_000,
            budget_price=81.0,
            hedge_ratio=0.60,
            futures_share=0.50,
            futures_entry_price=80.0,
            option_strike=84.0,
            option_style="collar",
            collar_floor=75.0,
            option_premium=2.0,
            collar_put_premium=0.75,
            purchase_basis=1.0,
            quality_differential_per_unit=-0.5,
            freight_per_unit=1.25,
            taxes_per_unit=2.0,
            other_unit_cost=0.25,
            budget_basis=0.5,
            budget_freight_per_unit=1.0,
            margin_rate=0.10,
            annual_funding_rate=0.10,
            holding_days=30,
            variation_margin_days=20,
            futures_fee_per_contract=5.0,
        )
        lower = scenarios.iloc[0]
        # 30,000 futures units lose $10 each at the lower-95% scenario.
        self.assertEqual(lower["FuturesContracts"], 30)
        self.assertAlmostEqual(lower["VariationMarginPosted"], 300_000.0)
        self.assertAlmostEqual(lower["OptionPayoff"], -150_000.0)  # written put payout
        self.assertAlmostEqual(lower["PhysicalUnitPrice"], 74.0)
        self.assertGreater(lower["LiquidityRequirement"], lower["InitialMargin"])
        reconciled = (
            lower["PhysicalCost"]
            - lower["FuturesPnL"]
            - lower["OptionPayoff"]
            + lower["OptionPremium"]
            + lower["TransactionCost"]
            + lower["MarginFundingCost"]
        )
        self.assertAlmostEqual(lower["NetCost"], reconciled)
        self.assertAlmostEqual(lower["BudgetDeviation"], lower["BudgetVariance"])
        self.assertAlmostEqual(lower["LiquidityRequirementCNY"], lower["InitialMargin"] + lower["VariationMarginPosted"] + lower["OptionPremium"] + lower["TransactionCost"])

    def test_default_comparison_has_all_policy_types_and_budget_pressure(self) -> None:
        comparison = compare_buyer_hedge_strategies(
            sample_result(),
            exposure_volume=100_000,
            budget_price=81.0,
            purchase_basis=1.0,
            settlement_fx_rate=7.2,
            budget_fx_rate=7.1,
            margin_rate=0.12,
            annual_funding_rate=0.05,
            holding_days=45,
            option_premium=1.5,
            collar_floor=72.0,
        )
        self.assertEqual(len(comparison), 25)
        self.assertEqual(
            set(comparison["Strategy"]),
            {"Unhedged", "Futures", "Options / collar", "Mixed", "Staged futures"},
        )
        self.assertTrue({"BudgetDeviation", "LiquidityRequirement", "VariationMarginPosted", "StrategyType"}.issubset(comparison.columns))
        unhedged = comparison[comparison["Strategy"] == "Unhedged"]
        self.assertTrue((unhedged["FuturesPnL"] == 0.0).all())
        self.assertTrue((unhedged["LiquidityRequirement"] == 0.0).all())
        self.assertTrue((comparison[comparison["Strategy"] == "Staged futures"]["IsStaged"]).all())

    def test_explicit_staged_policy_adds_rounded_contracts_per_tranche(self) -> None:
        strategy = HedgeStrategy(
            name="Two tranches",
            stages=(
                HedgeStage(volume_share=0.5, hedge_ratio=1.0, futures_share=1.0, futures_entry_price=80.0, option_style="none"),
                HedgeStage(volume_share=0.5, hedge_ratio=1.0, futures_share=1.0, futures_entry_price=82.0, option_style="none"),
            ),
        )
        comparison = compare_buyer_hedge_strategies(
            sample_result(),
            exposure_volume=20_000,
            budget_price=80.0,
            strategies=[strategy],
            contract_size=1_000,
        )
        point = comparison[comparison["Scenario"] == "Model path"].iloc[0]
        self.assertEqual(point["FuturesContracts"], 20)
        # Two 10,000-unit futures tranches: (84.8 - 80) + (84.8 - 82).
        self.assertAlmostEqual(point["FuturesPnL"], 76_000.0)
        self.assertAlmostEqual(point["HedgeRatio"], 1.0)

    def test_cost_and_staged_boundaries_are_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "Freight"):
            build_buyer_hedge_scenarios(
                sample_result(), exposure_volume=1_000, budget_price=80.0, freight_per_unit=-0.01
            )
        with self.assertRaisesRegex(ValueError, "collar requires"):
            build_buyer_hedge_scenarios(
                sample_result(), exposure_volume=1_000, budget_price=80.0, option_style="collar"
            )
        invalid = HedgeStrategy(
            name="Invalid staged",
            stages=(HedgeStage(volume_share=0.7, hedge_ratio=0.5), HedgeStage(volume_share=0.2, hedge_ratio=0.5)),
        )
        with self.assertRaisesRegex(ValueError, "sum to 1"):
            compare_buyer_hedge_strategies(
                sample_result(), exposure_volume=1_000, budget_price=80.0, strategies=[invalid]
            )


if __name__ == "__main__":
    unittest.main()
