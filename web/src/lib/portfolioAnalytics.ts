export type HedgeAsset = {
  id: string;
  score: number;
  volatility: number;
  oilCore?: boolean;
};

export type HedgeWeight = HedgeAsset & { weight: number };

export type HedgeLeg = {
  id: string;
  side: "buy" | "sell" | "long" | "short";
  kind: "call" | "put" | "future";
  quantity: number;
  multiplier: number;
  price: number;
  marginRate: number;
  commissionPerContract: number;
  slippagePerUnit: number;
};

export type PortfolioMetrics = {
  observations: number;
  totalReturn: number;
  annualizedReturn: number;
  annualizedVolatility: number;
  sharpe: number;
  maxDrawdown: number;
  var95: number;
  cvar95: number;
};

export type HedgeScenarioMetrics = {
  observations: number;
  unhedgedRange: number;
  hedgedRange: number;
  rangeReduction: number;
  averageSaving: number;
  worstCaseSaving: number;
};

function cappedNormalize(raw: number[], cap: number): number[] {
  if (!raw.length) return [];
  const weights = raw.map(() => 0);
  const active = new Set(raw.map((_, index) => index));
  let remaining = 1;
  for (let pass = 0; pass < raw.length + 2 && active.size; pass += 1) {
    const denominator = [...active].reduce((sum, index) => sum + raw[index], 0);
    if (denominator <= 0) break;
    let changed = false;
    for (const index of [...active]) {
      const proposed = remaining * raw[index] / denominator;
      if (proposed > cap) {
        weights[index] = cap;
        remaining -= cap;
        active.delete(index);
        changed = true;
      }
    }
    if (!changed) {
      for (const index of active) weights[index] = remaining * raw[index] / denominator;
      active.clear();
    }
  }
  const sum = weights.reduce((total, value) => total + value, 0);
  return sum > 0 ? weights.map((value) => value / sum) : raw.map(() => 1 / raw.length);
}

export function buildConstrainedHedgeWeights(
  assets: HedgeAsset[],
  constraints: { maxWeight?: number; minimumOilWeight?: number } = {},
): HedgeWeight[] {
  if (!assets.length) return [];
  const maxWeight = Math.min(1, Math.max(1 / assets.length, constraints.maxWeight ?? 0.5));
  const raw = assets.map((asset) => Math.max(Math.abs(asset.score), 1e-6) / Math.max(asset.volatility, 1e-4));
  const weights = cappedNormalize(raw, maxWeight);
  const oilIndexes = assets.map((asset, index) => asset.oilCore ? index : -1).filter((index) => index >= 0);
  const minimumOilWeight = Math.min(maxWeight * Math.max(1, oilIndexes.length), Math.max(0, constraints.minimumOilWeight ?? 0));
  const oilWeight = oilIndexes.reduce((sum, index) => sum + weights[index], 0);
  if (oilIndexes.length && oilWeight < minimumOilWeight) {
    const deficit = minimumOilWeight - oilWeight;
    const nonOil = weights.map((_, index) => oilIndexes.includes(index) ? -1 : index).filter((index) => index >= 0);
    const available = nonOil.reduce((sum, index) => sum + weights[index], 0);
    if (available > 0) nonOil.forEach((index) => { weights[index] *= (available - deficit) / available; });
    const oilRaw = oilIndexes.reduce((sum, index) => sum + raw[index], 0);
    oilIndexes.forEach((index) => { weights[index] += deficit * raw[index] / oilRaw; });
  }
  return assets.map((asset, index) => ({ ...asset, weight: weights[index] }));
}

export function priceHedgeLegs(legs: HedgeLeg[]) {
  let totalPremium = 0;
  let totalMargin = 0;
  let totalCommission = 0;
  let totalSlippage = 0;
  const pricedLegs = legs.map((leg) => {
    const units = Math.abs(leg.quantity) * leg.multiplier;
    const direction = leg.side === "sell" || leg.side === "short" ? -1 : 1;
    const premium = leg.kind === "future" ? 0 : direction * units * leg.price;
    const margin = leg.kind === "future" || direction < 0 ? units * leg.price * Math.max(0, leg.marginRate) : 0;
    const commission = Math.abs(leg.quantity) * Math.max(0, leg.commissionPerContract);
    const slippage = units * Math.max(0, leg.slippagePerUnit);
    totalPremium += premium;
    totalMargin += margin;
    totalCommission += commission;
    totalSlippage += slippage;
    return { ...leg, premium, margin, commission, slippage };
  });
  const cashRequired = Math.max(totalPremium, 0) + totalMargin + totalCommission + totalSlippage;
  return { legs: pricedLegs, totalPremium, totalMargin, totalCommission, totalSlippage, cashRequired };
}

const quantile = (sorted: number[], probability: number) => {
  if (!sorted.length) return 0;
  const position = (sorted.length - 1) * probability;
  const lower = Math.floor(position);
  const upper = Math.ceil(position);
  if (lower === upper) return sorted[lower];
  return sorted[lower] + (sorted[upper] - sorted[lower]) * (position - lower);
};

export function calculatePortfolioMetrics(values: number[], periodsPerYear = 252): PortfolioMetrics {
  const clean = values.filter((value) => Number.isFinite(value) && value > 0);
  if (clean.length < 2) throw new Error("At least two positive portfolio observations are required.");
  const returns = clean.slice(1).map((value, index) => value / clean[index] - 1);
  const mean = returns.reduce((sum, value) => sum + value, 0) / returns.length;
  const variance = returns.length > 1
    ? returns.reduce((sum, value) => sum + (value - mean) ** 2, 0) / (returns.length - 1)
    : 0;
  const annualizedVolatility = Math.sqrt(Math.max(variance, 0)) * Math.sqrt(periodsPerYear);
  const totalReturn = clean.at(-1)! / clean[0] - 1;
  const annualizedReturn = (clean.at(-1)! / clean[0]) ** (periodsPerYear / returns.length) - 1;
  let peak = clean[0];
  let maxDrawdown = 0;
  clean.forEach((value) => {
    peak = Math.max(peak, value);
    maxDrawdown = Math.min(maxDrawdown, value / peak - 1);
  });
  const sorted = [...returns].sort((a, b) => a - b);
  const var95 = quantile(sorted, 0.05);
  const tail = sorted.filter((value) => value <= var95);
  const cvar95 = tail.reduce((sum, value) => sum + value, 0) / Math.max(tail.length, 1);
  return {
    observations: clean.length,
    totalReturn,
    annualizedReturn,
    annualizedVolatility,
    sharpe: annualizedVolatility > 0 ? mean * periodsPerYear / annualizedVolatility : 0,
    maxDrawdown,
    var95,
    cvar95,
  };
}

export function calculateHedgeScenarioMetrics(rows: Array<{ unhedged: number; hedged: number }>): HedgeScenarioMetrics {
  const clean = rows.filter((row) => Number.isFinite(row.unhedged) && Number.isFinite(row.hedged));
  if (clean.length < 2) throw new Error("At least two matched hedge scenarios are required.");
  const unhedged = clean.map((row) => row.unhedged);
  const hedged = clean.map((row) => row.hedged);
  const savings = clean.map((row) => row.unhedged - row.hedged);
  const unhedgedRange = Math.max(...unhedged) - Math.min(...unhedged);
  const hedgedRange = Math.max(...hedged) - Math.min(...hedged);
  return {
    observations: clean.length,
    unhedgedRange,
    hedgedRange,
    rangeReduction: unhedgedRange > 0 ? 1 - hedgedRange / unhedgedRange : 0,
    averageSaving: savings.reduce((sum, value) => sum + value, 0) / savings.length,
    worstCaseSaving: Math.max(...savings),
  };
}
