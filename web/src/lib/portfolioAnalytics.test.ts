import { describe, expect, it } from "vitest";

import {
  buildConstrainedHedgeWeights,
  calculateHedgeScenarioMetrics,
  calculatePortfolioMetrics,
  priceHedgeLegs,
  type HedgeLeg,
} from "./portfolioAnalytics";

describe("portfolio analytics", () => {
  it("produces diversified normalized weights while respecting caps and minimum oil coverage", () => {
    const result = buildConstrainedHedgeWeights([
      { id: "CL", score: 0.9, volatility: 0.32, oilCore: true },
      { id: "GC", score: 0.6, volatility: 0.18 },
      { id: "DX", score: 0.4, volatility: 0.12 },
      { id: "ZN", score: 0.3, volatility: 0.08 },
    ], { maxWeight: 0.45, minimumOilWeight: 0.35 });
    expect(result.reduce((sum, row) => sum + row.weight, 0)).toBeCloseTo(1, 8);
    expect(result.find((row) => row.id === "CL")!.weight).toBeGreaterThanOrEqual(0.35);
    expect(Math.max(...result.map((row) => row.weight))).toBeLessThanOrEqual(0.45);
    expect(result.filter((row) => row.weight > 0).length).toBeGreaterThanOrEqual(3);
  });

  it("includes premium, margin, commission and slippage in executable leg costs", () => {
    const legs: HedgeLeg[] = [
      { id: "call", side: "buy", kind: "call", quantity: 10, multiplier: 1000, price: 2.5, marginRate: 0, commissionPerContract: 3, slippagePerUnit: 0.01 },
      { id: "future", side: "long", kind: "future", quantity: 4, multiplier: 1000, price: 80, marginRate: 0.12, commissionPerContract: 2, slippagePerUnit: 0.005 },
    ];
    const priced = priceHedgeLegs(legs);
    expect(priced.totalPremium).toBe(25_000);
    expect(priced.totalMargin).toBe(38_400);
    expect(priced.totalCommission).toBe(38);
    expect(priced.totalSlippage).toBe(120);
    expect(priced.cashRequired).toBe(63_558);
  });

  it("reports return, drawdown and tail risk from actual portfolio observations", () => {
    const metrics = calculatePortfolioMetrics([100, 104, 101, 108, 95, 110]);
    expect(metrics.totalReturn).toBeCloseTo(0.1, 8);
    expect(metrics.maxDrawdown).toBeCloseTo((95 - 108) / 108, 8);
    expect(metrics.observations).toBe(6);
    expect(Number.isFinite(metrics.cvar95)).toBe(true);
  });

  it("reports hedge effectiveness from matched unhedged and hedged scenarios", () => {
    const metrics = calculateHedgeScenarioMetrics([
      { unhedged: 80, hedged: 92 },
      { unhedged: 100, hedged: 98 },
      { unhedged: 140, hedged: 112 },
    ]);
    expect(metrics.unhedgedRange).toBe(60);
    expect(metrics.hedgedRange).toBe(20);
    expect(metrics.rangeReduction).toBeCloseTo(2 / 3, 6);
    expect(metrics.worstCaseSaving).toBe(28);
  });
});
