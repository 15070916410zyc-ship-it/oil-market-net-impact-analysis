export const catalog = [
  { id: "EIA-BRENT", providerId: "DCOILBRENTEU", name: "Brent现货价格", source: "EIA / FRED", unit: "美元/桶", frequency: "日度", color: "#1c7c72" },
  { id: "EIA-STOCKS", providerId: "WCESTUS1", name: "美国商业原油库存", source: "EIA / FRED", unit: "千桶", frequency: "周度", color: "#377dce" },
  { id: "FRED-DCOILWTICO", providerId: "DCOILWTICO", name: "WTI现货价格", source: "FRED", unit: "美元/桶", frequency: "日度", color: "#297f75" },
  { id: "FRED-DTWEXBGS", providerId: "DTWEXBGS", name: "美元广义指数", source: "FRED", unit: "指数", frequency: "日度", color: "#c07843" },
  { id: "FRED-DGS10", providerId: "DGS10", name: "美国10年期国债收益率", source: "FRED", unit: "%", frequency: "日度", color: "#6b77bd" },
  { id: "FRED-DGS2", providerId: "DGS2", name: "美国2年期国债收益率", source: "FRED", unit: "%", frequency: "日度", color: "#8873b5" },
  { id: "FRED-FEDFUNDS", providerId: "FEDFUNDS", name: "联邦基金有效利率", source: "FRED", unit: "%", frequency: "月度", color: "#a56f55" },
  { id: "FRED-CPIAUCSL", providerId: "CPIAUCSL", name: "美国消费者价格指数", source: "FRED", unit: "指数", frequency: "月度", color: "#b85d5d" },
  { id: "FRED-INDPRO", providerId: "INDPRO", name: "美国工业生产指数", source: "FRED", unit: "指数", frequency: "月度", color: "#65936f" },
  { id: "FRED-UNRATE", providerId: "UNRATE", name: "美国失业率", source: "FRED", unit: "%", frequency: "月度", color: "#6d8893" },
  { id: "FRED-T10YIE", providerId: "T10YIE", name: "美国10年期通胀预期", source: "FRED", unit: "%", frequency: "日度", color: "#c18c49" },
];

export function publicSeries(item, points) {
  const last = points.at(-1);
  return { ...item, updated: last?.date || "", points };
}
