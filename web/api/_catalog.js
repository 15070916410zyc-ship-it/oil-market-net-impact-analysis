const row = (id, providerId, name, nameEn, category, unit, frequency, color) => ({ id, providerId, name, nameEn, category, source: "FRED / official source", unit, frequency, color });

export const catalog = [
  { id:"GPRD", providerId:"GPRD", name:"地缘政治风险指数（传统日度 GPR）", nameEn:"Geopolitical Risk Index (traditional daily GPR)", category:"地缘政治与事件风险", source:"Caldara-Iacoviello GPR", unit:"指数", frequency:"日度", color:"#c47d59", aliases:"GPR GPRD geopolitical risk 地缘政治风险 地缘风险" },
  row("EIA-BRENT", "DCOILBRENTEU", "Brent现货价格", "Brent spot price", "原油基准", "美元/桶", "日度", "#287b72"),
  row("FRED-DCOILWTICO", "DCOILWTICO", "WTI现货价格", "WTI spot price", "原油基准", "美元/桶", "日度", "#3f70a3"),
  row("FRED-PETINV", "A24STI", "美国石油与煤炭产品制造业库存", "US petroleum and coal products manufacturing inventories", "库存与炼化", "百万美元", "月度", "#6d75a6"),
  row("FRED-HENRYHUB", "DHHNGSP", "Henry Hub天然气现货价", "Henry Hub natural gas spot price", "替代能源", "美元/MMBtu", "日度", "#b4754d"),
  row("FRED-GASOLINE", "GASREGW", "美国常规汽油零售价", "US regular gasoline retail price", "库存与炼化", "美元/加仑", "周度", "#bd8258"),
  row("FRED-DTWEXBGS", "DTWEXBGS", "美元广义指数", "Broad US dollar index", "金融条件", "指数", "日度", "#825f91"),
  row("FRED-DGS10", "DGS10", "美国10年期国债收益率", "US 10-year Treasury yield", "金融条件", "%", "日度", "#6878aa"),
  row("FRED-DGS2", "DGS2", "美国2年期国债收益率", "US 2-year Treasury yield", "金融条件", "%", "日度", "#7d6ea8"),
  row("FRED-FEDFUNDS", "FEDFUNDS", "联邦基金有效利率", "Effective federal funds rate", "金融条件", "%", "月度", "#9c6a59"),
  row("FRED-T10YIE", "T10YIE", "美国10年期通胀预期", "US 10-year inflation expectation", "金融条件", "%", "日度", "#b18643"),
  row("FRED-HYSPREAD", "BAMLH0A0HYM2", "美国高收益债利差", "US high-yield credit spread", "金融条件", "%", "日度", "#a95f64"),
  row("FRED-VIXCLS", "VIXCLS", "VIX波动率指数", "VIX volatility index", "风险偏好", "指数", "日度", "#c06c52"),
  row("FRED-SP500", "SP500", "标普500指数", "S&P 500 index", "风险偏好", "指数", "日度", "#657f9a"),
  row("FRED-CPIAUCSL", "CPIAUCSL", "美国消费者价格指数", "US consumer price index", "需求与通胀", "指数", "月度", "#aa6262"),
  row("FRED-PPI", "PPIACO", "美国生产者价格指数", "US producer price index", "需求与通胀", "指数", "月度", "#b46d65"),
  row("FRED-INDPRO", "INDPRO", "美国工业生产指数", "US industrial production index", "实体需求", "指数", "月度", "#5f8b78"),
  row("FRED-UNRATE", "UNRATE", "美国失业率", "US unemployment rate", "实体需求", "%", "月度", "#718993"),
  row("FRED-PAYEMS", "PAYEMS", "美国非农就业", "US nonfarm payrolls", "实体需求", "千人", "月度", "#5b8798"),
  row("FRED-RSAFS", "RSAFS", "美国零售销售", "US retail sales", "实体需求", "百万美元", "月度", "#538f86"),
];

export function publicSeries(item, points) {
  const last = points.at(-1);
  return { ...item, updated: last?.date || "", points };
}
