export type Frequency = "daily" | "monthly";
export type PriceRow = { date: string; actual?: number; forecast?: number; lo50?: number; hi50?: number; lo80?: number; hi80?: number; lo95?: number; hi95?: number };

const round = (n: number, d = 2) => Number(n.toFixed(d));
const seeded = (seed: number) => () => ((seed = Math.imul(48271, seed) % 2147483647) & 2147483647) / 2147483647;

export function makeForecast(frequency: Frequency, horizon = frequency === "daily" ? 30 : 12): PriceRow[] {
  const rng = seeded(20260821);
  const stepDays = frequency === "daily" ? 1 : 30;
  const historyCount = frequency === "daily" ? 100 : 48;
  const start = new Date("2026-08-21T00:00:00Z");
  let price = 82.4;
  const rows: PriceRow[] = [];
  for (let i = historyCount - 1; i >= 0; i--) {
    const date = new Date(start.getTime() - i * stepDays * 86400000).toISOString().slice(0, 10);
    price += (rng() - 0.48) * (frequency === "daily" ? 1.5 : 3.2) + (84 - price) * 0.035;
    rows.push({ date, actual: round(price) });
  }
  const cutoff = rows.at(-1)!;
  cutoff.forecast = cutoff.actual;
  cutoff.lo50 = cutoff.hi50 = cutoff.lo80 = cutoff.hi80 = cutoff.lo95 = cutoff.hi95 = cutoff.actual;
  let level = cutoff.actual!;
  for (let i = 1; i <= horizon; i++) {
    level += Math.sin(i / 3.3) * 0.25 + (84.8 - level) * 0.08;
    const sigma = Math.sqrt(i) * (frequency === "daily" ? 0.72 : 2.1);
    const date = new Date(start.getTime() + i * stepDays * 86400000).toISOString().slice(0, 10);
    rows.push({ date, forecast: round(level), lo50: round(level - sigma * .67), hi50: round(level + sigma * .67), lo80: round(level - sigma * 1.28), hi80: round(level + sigma * 1.28), lo95: round(level - sigma * 1.96), hi95: round(level + sigma * 1.96) });
  }
  return rows;
}

export function makeForecastFromHistory(
  points: Array<{ date: string; value: number }>,
  frequency: Frequency,
  horizon = frequency === "daily" ? 30 : 12,
): PriceRow[] {
  if (points.length < 8) return makeForecast(frequency, horizon);
  const history = points.slice(-(frequency === "daily" ? 120 : 60));
  const rows: PriceRow[] = history.map((point) => ({ date: point.date, actual: point.value }));
  const changes = history.slice(1).map((point, index) => point.value - history[index].value);
  const recent = changes.slice(-Math.min(changes.length, frequency === "daily" ? 30 : 12));
  const drift = recent.reduce((sum, value) => sum + value, 0) / Math.max(1, recent.length);
  const variance = recent.reduce((sum, value) => sum + (value - drift) ** 2, 0) / Math.max(1, recent.length - 1);
  const volatility = Math.max(Math.sqrt(variance), frequency === "daily" ? 0.35 : 1.1);
  const last = history.at(-1)!;
  const cutoff = rows.at(-1)!;
  cutoff.forecast = cutoff.actual;
  cutoff.lo50 = cutoff.hi50 = cutoff.lo80 = cutoff.hi80 = cutoff.lo95 = cutoff.hi95 = cutoff.actual;
  const start = new Date(`${last.date.length === 7 ? `${last.date}-01` : last.date}T00:00:00Z`);
  for (let i = 1; i <= horizon; i++) {
    const step = frequency === "daily" ? 86400000 : 30 * 86400000;
    const level = last.value + drift * i;
    const sigma = volatility * Math.sqrt(i);
    rows.push({
      date: new Date(start.getTime() + i * step).toISOString().slice(0, frequency === "daily" ? 10 : 7),
      forecast: round(level),
      lo50: round(level - sigma * .67), hi50: round(level + sigma * .67),
      lo80: round(level - sigma * 1.28), hi80: round(level + sigma * 1.28),
      lo95: round(level - sigma * 1.96), hi95: round(level + sigma * 1.96),
    });
  }
  return rows;
}

export const drivers = [
  { name: "OPEC+产量纪律", value: 3.42, group: "供给" },
  { name: "地缘与航运扰动", value: 2.74, group: "事件" },
  { name: "中国需求景气", value: 1.86, group: "需求" },
  { name: "炼厂开工与裂解价差", value: .94, group: "需求" },
  { name: "投机净持仓", value: -.71, group: "金融" },
  { name: "实际利率预期", value: -.83, group: "宏观" },
  { name: "OECD商业库存", value: -1.28, group: "供给" },
  { name: "美元指数", value: -1.62, group: "宏观" },
  { name: "美国页岩油产量", value: -2.15, group: "供给" },
];

export const riskRows = Array.from({ length: 18 }, (_, i) => ({
  date: new Date(Date.UTC(2026, 7, 21 + i * 5)).toISOString().slice(0, 10),
  baseline: round(28 + i * 1.35 + Math.sin(i / 2) * 7, 1),
  stress: round(39 + i * 1.6 + Math.sin(i / 1.7) * 9, 1),
}));

export type DataSeries = { id: string; name: string; source: string; unit: string; frequency: string; updated: string; color: string };
export const catalog: DataSeries[] = [
  { id: "EIA-BRENT", name: "Brent现货价格", source: "EIA", unit: "美元/桶", frequency: "日度", updated: "2026-08-21", color: "#1c7c72" },
  { id: "EIA-STOCKS", name: "美国商业原油库存", source: "EIA", unit: "千桶", frequency: "周度", updated: "2026-08-19", color: "#377dce" },
  { id: "FRED-DTWEXBGS", name: "美元广义指数", source: "FRED", unit: "指数", frequency: "日度", updated: "2026-08-20", color: "#c07843" },
  { id: "FRED-DGS10", name: "美国10年期国债收益率", source: "FRED", unit: "%", frequency: "日度", updated: "2026-08-20", color: "#6b77bd" },
  { id: "WB-GDP", name: "世界经济增长", source: "World Bank", unit: "%", frequency: "年度", updated: "2026-07-01", color: "#65936f" },
  { id: "IMF-CPI", name: "全球通胀指标", source: "IMF", unit: "%", frequency: "月度", updated: "2026-07-31", color: "#b85d5d" },
  { id: "OECD-CLI", name: "OECD综合领先指标", source: "OECD", unit: "指数", frequency: "月度", updated: "2026-07-31", color: "#6d8893" },
];

export function seriesPreview(id: string) {
  const base = catalog.findIndex((s) => s.id === id) + 1;
  return Array.from({ length: 36 }, (_, i) => ({
    date: new Date(Date.UTC(2023, i, 1)).toISOString().slice(0, 7),
    value: round(72 + base * 4 + Math.sin(i / 3 + base) * (4 + base) + i * .18, 2),
  }));
}
