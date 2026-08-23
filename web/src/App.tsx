import { useEffect, useMemo, useState } from "react";
import {
  Activity,
  ArrowRight,
  BarChart3,
  BookOpen,
  ChevronRight,
  CircleDollarSign,
  Database,
  Download,
  FlaskConical,
  Gauge,
  Globe2,
  Languages,
  Menu,
  Minus,
  MoveHorizontal,
  Plus,
  Radio,
  Save,
  Search,
  Settings2,
  ShieldCheck,
  Sparkles,
  TrendingUp,
  X,
  ZoomIn,
  ZoomOut,
} from "lucide-react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  Brush,
  CartesianGrid,
  Cell,
  ComposedChart,
  Legend,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import {
  type DataSeries,
  type Frequency,
  type PriceRow,
} from "./data";
import { checkApiHealth, fetchCatalog, fetchSeries, readLocalRecords, requestLiveAnalysis, saveLocalRecord } from "./storage";

type Lang = "zh" | "en";
type Mode = "landing" | "decision" | "professional";
type ProTab = "impact" | "forecast" | "risk" | "data";
const tx = (lang: Lang, zh: string, en: string) => (lang === "zh" ? zh : en);

type DriverResult = { id: string; nameZh: string; nameEn: string; impact: number; coefficient: number };
type ComponentResult = { imf: string; channelZh: string; channelEn: string; centerFrequency: number; volatilityShare: number; points: Array<{ date: string; value: number }> };
type GrangerResult = { id: string; nameZh: string; nameEn: string; lag: number; fStatistic: number; pValue: number; significant: boolean };
type ScaleGrangerResult = GrangerResult & { imf: string };
type NetImpactResult = { mode: string; method: string; asOf: string; observations: number; rSquared: number; drivers: DriverResult[]; granger: GrangerResult[]; scaleGranger: ScaleGrangerResult[]; selectedScales: Array<{id:string;nameZh:string;nameEn:string;imf:string;pValue:number}>; components: ComponentResult[]; fevd: Array<{id:string;nameZh:string;nameEn:string;share:number}>; fevdOwnShare:number; fevdHorizon:number; varLag:number; rolling: Array<{ date: string; observed: number; fitted: number }>; rollingFevd:Array<{date:string;externalShare:number;ownShare:number;lag:number}>; breakTest:{candidateCount:number;bestDate:string;rssImprovementPercent:number;profile:Array<{date:string;rss:number;improvementPercent:number}>}; sources: Array<{ id: string; providerId: string; nameZh: string; nameEn: string }> };
type RiskResult = { mode: string; method: string; latestDate: string; riskScore: number; alertThreshold: number; alert: boolean; history: Array<{ date: string; score: number }> };
type ForecastResult = { mode: string; method: string; asOf: string; latestPrice: number; history: Array<{ Date: string; Actual: number }>; forecast: Array<Record<string, number | string>>; metrics: Record<string, number>; components: Array<{ imf: string; channelZh: string; channelEn: string; centerFrequency: number; latestForecast: number }> };

const driverNamesEn: Record<string, string> = {
  "OPEC+产量纪律": "OPEC+ production discipline",
  "地缘与航运扰动": "Geopolitical & shipping disruption",
  "中国需求景气": "China demand momentum",
  "炼厂开工与裂解价差": "Refinery runs & crack spreads",
  "投机净持仓": "Speculative net positioning",
  "实际利率预期": "Real-rate expectations",
  "OECD商业库存": "OECD commercial inventories",
  "美元指数": "US dollar index",
  "美国页岩油产量": "US shale production",
};

const seriesNamesEn: Record<string, string> = {
  "EIA-BRENT": "Brent spot price",
  "FRED-DCOILWTICO": "WTI spot price",
  "EIA-STOCKS": "US commercial crude inventories",
  "FRED-DTWEXBGS": "Broad US dollar index",
  "FRED-DGS10": "US 10-year Treasury yield",
  "FRED-DGS2": "US 2-year Treasury yield",
  "FRED-FEDFUNDS": "Effective federal funds rate",
  "FRED-CPIAUCSL": "US consumer price index",
  "FRED-INDPRO": "US industrial production",
  "FRED-UNRATE": "US unemployment rate",
  "FRED-T10YIE": "US 10-year inflation expectations",
  "WB-GDP": "World economic growth",
  "IMF-CPI": "Global inflation indicator",
  "OECD-CLI": "OECD composite leading indicator",
};

const seriesText = (item: DataSeries, lang: Lang) => ({
  name: lang === "en" ? item.nameEn || seriesNamesEn[item.id] || item.name : item.name,
  frequency: lang === "en" ? ({ 日度: "Daily", 周度: "Weekly", 月度: "Monthly", 年度: "Annual" }[item.frequency] || item.frequency) : item.frequency,
  unit: lang === "en" ? ({ "美元/桶": "USD/bbl", 千桶: "thousand bbl", 指数: "index", 年度: "annual" }[item.unit] || item.unit) : item.unit,
});

const copy = {
  zh: {
    brand: "油价智析",
    decision: "决策模式",
    professional: "专业模式",
    demo: "数据暂不可用",
    hero: "看清油价，也看清下一步",
    sub: "把影响因素、价格路径和风险预警连成一套可执行的采购与投资判断。",
    enter: "查看最新判断",
    research: "进入专业模式",
    overview: "今日市场判断",
    drivers: "最近什么在推动油价",
    forecast: "市场路径与决策区间",
    risk: "未来风险温度",
    hedge: "采购成本与套保方案",
    advice: "行动建议",
    source: "数据中心",
    brandTag: "Oil Price Intelligence",
  },
  en: {
    brand: "Oil Price Intelligence",
    decision: "Decision",
    professional: "Research",
    demo: "Data unavailable",
    hero: "See the oil market—and your next move",
    sub: "One connected view of drivers, price paths, risk signals and executable hedging decisions.",
    enter: "View latest call",
    research: "Open research mode",
    overview: "Market call",
    drivers: "What is moving oil",
    forecast: "Market path & decision range",
    risk: "Forward risk temperature",
    hedge: "Procurement & hedge plan",
    advice: "Recommended actions",
    source: "Data workspace",
    brandTag: "Research & decision system",
  },
} as const;

function routeFromPath(): Mode {
  if (location.pathname.startsWith("/professional")) return "professional";
  if (location.pathname.startsWith("/decision")) return "decision";
  return "landing";
}

function App() {
  const [mode, setMode] = useState<Mode>(routeFromPath);
  const [lang, setLang] = useState<Lang>(
    () => (localStorage.getItem("opi.lang") as Lang) || "zh",
  );
  const [menu, setMenu] = useState(false);
  const [apiLive, setApiLive] = useState(false);
  const t = copy[lang];

  useEffect(() => {
    const onPop = () => setMode(routeFromPath());
    addEventListener("popstate", onPop);
    return () => removeEventListener("popstate", onPop);
  }, []);
  useEffect(() => {
    void checkApiHealth().then(setApiLive);
  }, []);
  useEffect(() => {
    document.documentElement.lang = lang === "zh" ? "zh-CN" : "en";
    document.title =
      lang === "zh"
        ? "油价智析 · 原油市场研究与决策"
        : "Oil Price Intelligence · Market Research & Decisions";
  }, [lang]);

  const navigate = (next: Mode) => {
    history.pushState({}, "", next === "landing" ? "/" : `/${next}`);
    setMode(next);
    setMenu(false);
    scrollTo({ top: 0, behavior: "smooth" });
  };
  const toggleLang = () =>
    setLang((l) => {
      const next = l === "zh" ? "en" : "zh";
      localStorage.setItem("opi.lang", next);
      return next;
    });

  return (
    <div className="site-shell">
      <Ambient />
      <a href="#main" className="skip-link">
        {tx(lang, "跳到主要内容", "Skip to main content")}
      </a>
      <header className="topbar">
        <button
          className="brand"
          onClick={() => navigate("landing")}
          aria-label={tx(lang, "返回首页", "Back to home")}
        >
          <span className="brand-orbit">
            <i />
          </span>
          <span>
            <b>{t.brand}</b>
            <small>{t.brandTag}</small>
          </span>
        </button>
        {mode !== "landing" && (
          <nav className="mode-switch" aria-label={tx(lang, "模式切换", "Mode switcher")}>
            <button
              className={mode === "decision" ? "active" : ""}
              onClick={() => navigate("decision")}
            >
              {t.decision}
            </button>
            <button
              className={mode === "professional" ? "active" : ""}
              onClick={() => navigate("professional")}
            >
              {t.professional}
            </button>
          </nav>
        )}
        <div className="utility">
          <span title={apiLive ? tx(lang, "官方数据接口已连接", "Official data feed connected") : tx(lang, "数据接口暂不可用；不会显示替代数据", "Data feed unavailable; no substitute data is shown")}>
            <Radio size={13} /> <em>{apiLive ? tx(lang, "实时数据", "Live data") : t.demo}</em>
          </span>
          <button onClick={toggleLang}>
            <Languages size={14} /> {lang === "zh" ? "中" : "EN"}
          </button>
        </div>
        <button
          className="mobile-menu"
          onClick={() => setMenu(!menu)}
          aria-expanded={menu}
        >
          {menu ? <X /> : <Menu />}
        </button>
        {menu && (
          <div className="mobile-panel">
            <button onClick={() => navigate("decision")}>{t.decision}</button>
            <button onClick={() => navigate("professional")}>
              {t.professional}
            </button>
            <button onClick={toggleLang}>中 / EN</button>
          </div>
        )}
      </header>
      <main id="main">
        <div key={mode} className={`route-view route-${mode}`}>
          {mode === "landing" && (
            <Landing
              lang={lang}
              t={t}
              onDecision={() => navigate("decision")}
              onProfessional={() => navigate("professional")}
            />
          )}
          {mode === "decision" && <Decision lang={lang} t={t} />}
          {mode === "professional" && <Professional lang={lang} t={t} />}
        </div>
      </main>
      <footer>
        <span>© 2026 {t.brand}</span>
        <span>{apiLive ? tx(lang, "官方数据接口已连接", "Official data feed connected") : t.demo} · {tx(lang, "研究结果不构成投资建议", "Research output is not investment advice")}</span>
      </footer>
    </div>
  );
}

function Ambient() {
  return (
    <div className="ambient" aria-hidden="true">
      <div className="wash one" />
      <div className="wash two" />
      <div className="ambient-grid" />
      <div className="ambient-radar radar-one" />
      <div className="ambient-radar radar-two" />
      <svg className="ambient-lines" viewBox="0 0 1400 900" preserveAspectRatio="none">
        <path d="M-90 140C230 30 360 260 710 123s510-70 790 40" />
        <path d="M-120 320c290-140 520 45 770-60s520-180 890 30" />
        <path d="M-80 720c330-250 560 140 860-80s460-170 760-20" />
        <path className="dash" d="M80 520C320 390 520 590 760 430s410-110 610-10" />
        <circle cx="230" cy="169" r="6" />
        <circle cx="1090" cy="214" r="8" />
        <circle cx="790" cy="640" r="5" />
      </svg>
      <div className="ambient-coordinate coordinate-one">35°N · 51°E</div>
      <div className="ambient-coordinate coordinate-two">FLOW / 07</div>
      <div className="grain" />
    </div>
  );
}

function Landing({
  lang,
  t,
  onDecision,
  onProfessional,
}: {
  lang: Lang;
  t: typeof copy.zh | typeof copy.en;
  onDecision: () => void;
  onProfessional: () => void;
}) {
  const [quotes, setQuotes] = useState<{brent: number | null; brentMove: number | null; wti: number | null; wtiMove: number | null; updated: string}>({
    brent: null,
    brentMove: null,
    wti: null,
    wtiMove: null,
    updated: "",
  });
  const [riskScore, setRiskScore] = useState<number | null>(null);

  useEffect(() => {
    let active = true;
    const loadQuote = async (id: string) => {
      const result = await fetchSeries(id, "daily");
      const latest = result.points.at(-1);
      const previous = result.points.at(-2);
      return {
        value: latest?.value,
        move:
          latest && previous
            ? ((latest.value / previous.value - 1) * 100)
            : undefined,
        updated: result.updated,
      };
    };
    void Promise.allSettled([loadQuote("EIA-BRENT"), loadQuote("FRED-DCOILWTICO")]).then(
      ([brentResult, wtiResult]) => {
        if (!active) return;
        const brent = brentResult.status === "fulfilled" ? brentResult.value : null;
        const wti = wtiResult.status === "fulfilled" ? wtiResult.value : null;
        setQuotes((current) => ({
          brent: brent?.value ?? null,
          brentMove: brent?.move ?? null,
          wti: wti?.value ?? null,
          wtiMove: wti?.move ?? null,
          updated: [brent?.updated, wti?.updated].filter(Boolean).sort().at(-1) || "",
        }));
      },
    );
    void requestLiveAnalysis<{ riskScore: number }>("/api/models/risk", {})
      .then((result) => {
        if (active && Number.isFinite(result?.riskScore)) setRiskScore(result!.riskScore);
      })
      .catch(() => {});
    return () => {
      active = false;
    };
  }, []);

  return (
    <section className="hero">
      <div className="hero-copy">
        <p className="eyebrow">
          <Sparkles size={14} /> Multi-scale market intelligence
        </p>
        <h1>{t.hero}</h1>
        <p className="hero-sub">{t.sub}</p>
        <div className="hero-actions">
          <button className="primary" onClick={onDecision}>
            {t.enter}
            <ArrowRight size={17} />
          </button>
          <button className="text-action" onClick={onProfessional}>
            {t.research}
            <ChevronRight size={17} />
          </button>
        </div>
        <div className="trust-row">
          <span>{tx(lang, "多源数据", "Multi-source data")}</span>
          <span>{tx(lang, "多尺度归因", "Multi-scale attribution")}</span>
          <span>{tx(lang, "情景预测", "Scenario forecasts")}</span>
          <span>{tx(lang, "企业套保", "Enterprise hedging")}</span>
        </div>
      </div>
      <div className="signal-stage">
        <EnergyGlobe riskScore={riskScore} lang={lang} />
        <div className="metric-float mf-one">
          <small>BRENT</small>
          <strong>{quotes.brent == null ? "—" : `$${quotes.brent.toFixed(2)}`}</strong>
          <em>{quotes.brentMove == null ? tx(lang,"等待官方数据","Awaiting official data") : `${quotes.brentMove >= 0 ? "+" : ""}${quotes.brentMove.toFixed(1)}%`}</em>
        </div>
        <div className="metric-float mf-two">
          <small>WTI</small>
          <strong>{quotes.wti == null ? "—" : `$${quotes.wti.toFixed(2)}`}</strong>
          <em>{quotes.wtiMove == null ? tx(lang,"等待官方数据","Awaiting official data") : `${quotes.wtiMove >= 0 ? "+" : ""}${quotes.wtiMove.toFixed(1)}%`}</em>
        </div>
        <div className="metric-float mf-three">
          <small>MARKET RISK</small>
          <strong>{riskScore == null ? "—" : riskScore.toFixed(1)}</strong>
          <em>{riskScore == null ? tx(lang,"等待模型","Awaiting model") : riskScore >= 60 ? tx(lang, "中高", "Elevated") : tx(lang, "较低", "Low")}</em>
        </div>
        <div className="pulse-line">
          <span>{quotes.updated ? tx(lang, `官方数据更新至 ${quotes.updated}`, `Official data updated ${quotes.updated}`) : tx(lang, "正在同步官方市场数据；此处不显示替代曲线", "Syncing official market data; no substitute curve is displayed")}</span>
          <div className="source-seal"><Database/><b>FRED · EIA</b><small>{tx(lang,"可追溯官方序列","Traceable official series")}</small></div>
        </div>
      </div>
    </section>
  );
}

function EnergyGlobe({ riskScore, lang }: { riskScore: number | null; lang: Lang }) {
  const riskTone = riskScore != null && riskScore >= 60 ? "risk-high" : "risk-low";
  return (
    <div className={`energy-globe ${riskTone}`} aria-label={tx(lang, "持续转动的全球能源与市场数据网络", "Rotating global energy and market data network")}>
      <div className="globe-halo" />
      <div className="globe-sphere">
        <div className="globe-grid" />
        <div className="world-belt">
          <svg viewBox="0 0 1200 420" role="img" aria-label={tx(lang, "世界能源市场地图", "Global energy market map")}>
            <g className="land" transform="translate(0 2)">
              <path d="M82 94l48-32 72 9 40 31 53 11 27 39-22 37-49 13-18 45-45 31-21-52-43-22-18-49-39-19z" />
              <path d="M245 250l38 22 19 53-18 70-30-23-9-55-24-38z" />
              <path d="M443 91l54-30 73 10 36 25 63-10 94 35 38 37-29 32-67-7-41 24-56-9-33 41-36-17-24-51-48-11-34-31z" />
              <path d="M529 214l58 8 38 45-13 77-41 44-43-37-22-73z" />
              <path d="M803 292l53-22 47 26 11 46-59 24-47-24z" />
              <path d="M1004 95l48-31 72 8 40 31 53 11 27 39-23 37-48 13-18 45-45 31-21-52-43-22-18-49-39-19z" />
            </g>
            <g className="energy-routes">
              <path d="M142 174 Q320 42 546 192 T884 165" />
              <path d="M276 282 Q470 168 648 286 T1010 204" />
              <circle cx="142" cy="174" r="5" />
              <circle cx="546" cy="192" r="5" />
              <circle cx="884" cy="165" r="5" />
              <circle cx="648" cy="286" r="5" />
            </g>
          </svg>
        </div>
        <div className="globe-shade" />
        <div className="globe-scan" />
      </div>
      <div className="energy-orbit orbit-a"><i /></div>
      <div className="energy-orbit orbit-b"><i /></div>
      <div className="oil-signal" aria-hidden="true">
        <svg viewBox="0 0 32 42"><path d="M16 1C13 8 4 17 4 27a12 12 0 0 0 24 0C28 17 19 8 16 1Z" /></svg>
        <span>{riskScore == null ? "AWAITING DATA" : riskScore >= 60 ? "RISK PULSE" : "ENERGY FLOW"}</span>
      </div>
    </div>
  );
}

function PageIntro({
  eyebrow,
  title,
  desc,
}: {
  eyebrow: string;
  title: string;
  desc: string;
}) {
  return (
    <div className="page-intro">
      <p className="eyebrow">{eyebrow}</p>
      <h1>{title}</h1>
      <p>{desc}</p>
    </div>
  );
}

function Card({
  title,
  desc,
  action,
  children,
  className = "",
}: {
  title: string;
  desc?: string;
  action?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <section className={`card ${className}`}>
      <div className="card-head">
        <div>
          <h2>{title}</h2>
          {desc && <p>{desc}</p>}
        </div>
        {action}
      </div>
      {children}
    </section>
  );
}

function Decision({
  lang,
  t,
}: {
  lang: Lang;
  t: typeof copy.zh | typeof copy.en;
}) {
  const [frequency, setFrequency] = useState<Frequency>("daily");
  const [forecast, setForecast] = useState<PriceRow[]>([]);
  const [forecastResult, setForecastResult] = useState<ForecastResult | null>(null);
  const [impact, setImpact] = useState<NetImpactResult | null>(null);
  const [risk, setRisk] = useState<RiskResult | null>(null);
  const [wti, setWti] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  useEffect(() => {
    let active = true;
    setLoading(true); setError("");
    void Promise.all([
      requestLiveAnalysis<ForecastResult>("/api/models/forecast", { horizon: frequency === "daily" ? 30 : 12 }),
      requestLiveAnalysis<NetImpactResult>("/api/models/net-impact", {}),
      requestLiveAnalysis<RiskResult>("/api/models/risk", {}),
      fetchSeries("FRED-DCOILWTICO", frequency),
    ]).then(([forecastPayload, impactPayload, riskPayload, wtiPayload]) => {
      if (!active || !forecastPayload || !impactPayload || !riskPayload) return;
      setForecastResult(forecastPayload); setImpact(impactPayload); setRisk(riskPayload);
      setForecast([
        ...forecastPayload.history.map((row) => ({ date: row.Date, actual: row.Actual })),
        ...forecastPayload.forecast.map((row) => ({ date: String(row.Date), forecast: Number(row.PointForecast), lo50: Number(row.Lower50), hi50: Number(row.Upper50), lo80: Number(row.Lower80), hi80: Number(row.Upper80), lo95: Number(row.Lower95), hi95: Number(row.Upper95) })),
      ]);
      setWti(wtiPayload.points.at(-1)?.value ?? null);
    }).catch((reason) => { if (active) setError(reason instanceof Error ? reason.message : String(reason)); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [frequency]);
  if (loading) return <div className="page"><StatusPanel text={tx(lang, "正在从官方来源更新数据并运行模型…", "Updating official data and running verified models…")} /></div>;
  if (error || !forecastResult || !impact || !risk) return <div className="page"><StatusPanel error text={tx(lang, `无法生成可靠结果：${error}`, `Verified results are unavailable: ${error}`)} /></div>;
  const latest = forecastResult.latestPrice;
  const median = forecastResult.forecast.at(-1)?.PointForecast as number;
  const low = Math.min(...forecastResult.forecast.map((r) => Number(r.Lower95)));
  const high = Math.max(...forecastResult.forecast.map((r) => Number(r.Upper95)));
  const suggestedRatio = Math.round(Math.min(85, Math.max(35, 35 + risk.riskScore * .45)));
  return (
    <div className="page">
      <PageIntro
        eyebrow={`Decision intelligence · ${forecastResult.asOf}`}
        title={lang === "zh" ? "今天需要关注什么" : "What matters today"}
        desc={
          lang === "zh"
            ? "先看市场状态，再顺着影响因素、价格路径和风险信号，落到采购与套保动作。"
            : "A connected path from market state to drivers, forecast, risk and action."
        }
      />
      <div className="kpi-grid">
        <Kpi label={tx(lang, "最新数据", "Latest observation")} value={forecastResult.asOf} />
        <Kpi
          label="Brent"
          value={`$${latest.toFixed(2)}`}
          delta={tx(lang, "官方现货序列", "Official spot series")}
        />
        <Kpi label="WTI" value={wti == null ? tx(lang, "同步中", "Syncing") : `$${wti.toFixed(2)}`} delta={tx(lang, "美国原油现货", "US crude spot")}/>
        <Kpi label={tx(lang, "预测期末中位路径", "End-of-horizon median")} value={`$${Number(median).toFixed(2)}`} delta={`${((Number(median) / latest - 1) * 100).toFixed(1)}%`} />
        <Kpi label={tx(lang, "95%决策区间", "95% decision range")} value={`$${low.toFixed(1)}—${high.toFixed(1)}`} />
        <Kpi
          label={tx(lang, "风险温度", "Risk temperature")}
          value={risk.riskScore.toFixed(1)}
          delta={risk.alert ? tx(lang, "已超过历史触发阈值", "Above historical review threshold") : tx(lang, "未超过历史触发阈值", "Below historical review threshold")}
          tone="warm"
        />
      </div>
      <div className="story-rail">
        <span>{tx(lang, "01 市场状态", "01 Market state")}</span>
        <span>{tx(lang, "02 影响因素", "02 Drivers")}</span>
        <span>{tx(lang, "03 价格路径", "03 Price path")}</span>
        <span>{tx(lang, "04 风险预警", "04 Risk alert")}</span>
        <span>{tx(lang, "05 行动方案", "05 Action plan")}</span>
      </div>
      <Card
        title={t.drivers}
        desc={tx(lang, "净影响表示该因素与当前油价变动的方向和估计幅度，不代表单一因果关系。", "Net impact estimates direction and magnitude; it does not claim a single causal relationship.")}
        action={<span className="data-badge">{tx(lang, `计算至 ${impact.asOf}`, `Calculated through ${impact.asOf}`)}</span>}
      >
        <DriverChart lang={lang} data={impact.drivers} />
        <div className="insight-strip">
          <b>{tx(lang, "模型说明", "Model note")}</b>
          <span>{tx(lang, `基于 ${impact.observations} 个月度共同样本；贡献是模型估计，不作单一因果解释。`, `Based on ${impact.observations} aligned monthly observations. Contributions are model estimates, not single-cause claims.`)}</span>
        </div>
      </Card>
      <Card
        title={t.forecast}
        desc={tx(lang, "历史线与预测线在同一截点连接；颜色由浅到深分别表示95%、80%与50%区间。", "History and forecast meet at one cutoff; layered color bands show the 95%, 80% and 50% ranges.")}
        action={
          <Segment
            value={frequency}
            onChange={setFrequency}
            options={[
              { v: "daily", l: tx(lang, "日度", "Daily") },
              { v: "monthly", l: tx(lang, "月度", "Monthly") },
            ]}
          />
        }
      >
        <ForecastChart data={forecast} lang={lang} />
      </Card>
      <div className="two-col">
        <Card
          title={t.risk}
          desc={tx(lang, "风险上升意味着需要更早准备保证金和采购预算，不等同于危机必然发生。", "Rising risk calls for earlier margin and procurement planning; it does not mean a crisis is certain.")}
        >
          <RiskChart lang={lang} data={risk.history} threshold={risk.alertThreshold} />
          <div className="risk-summary">
            <Gauge />
            <div>
              <b>{tx(lang, `当前历史风险分位：${risk.riskScore.toFixed(1)}`, `Current historical risk percentile: ${risk.riskScore.toFixed(1)}`)}</b>
              <p>
                {tx(lang, `复核阈值为 ${risk.alertThreshold.toFixed(1)}；该指标用于排序和触发复核，并非危机发生概率。`, `The review threshold is ${risk.alertThreshold.toFixed(1)}. This is a ranking signal, not a crisis probability.`)}
              </p>
            </div>
          </div>
        </Card>
        <ScaleCard lang={lang} components={impact.components} />
      </div>
      <HedgeCalculator lang={lang} market={latest} suggestedRatio={suggestedRatio} />
      <Card title={t.advice} className="advice">
        <div className="advice-grid">
          <Advice
            n="01"
            title={tx(lang, "采购节奏", "Procurement cadence")}
            text={tx(lang, `预测区间较宽，建议按三批执行并在每批前用最新数据重算。`, `The forecast interval is wide; execute in three tranches and rerun the model before each tranche.`)}
          />
          <Advice
            n="02"
            title={tx(lang, "套保比例", "Hedge ratio")}
            text={tx(lang, `按当前风险分位，测算起点为 ${suggestedRatio}% 覆盖；最终比例仍应结合合同和现金约束。`, `At the current risk percentile, ${suggestedRatio}% is the calculation starting point; final coverage must reflect contract and cash constraints.`)}
          />
          <Advice
            n="03"
            title={tx(lang, "资金准备", "Liquidity planning")}
            text={tx(lang, "使用下方真实参数测算器，把保证金、汇率、基差和融资成本同时纳入预算。", "Use the parameterized calculator below to budget margin, FX, basis and funding costs together.")}
          />
          <Advice
            n="04"
            title={tx(lang, "触发条件", "Review triggers")}
            text={tx(lang, `风险分位超过 ${risk.alertThreshold.toFixed(1)} 或价格超出95%区间时立即复核，不使用固定人为阈值。`, `Review immediately if risk exceeds ${risk.alertThreshold.toFixed(1)} or price leaves the 95% interval; no arbitrary fixed trigger is used.`)}
          />
        </div>
      </Card>
    </div>
  );
}

function Kpi({
  label,
  value,
  delta,
  tone,
}: {
  label: string;
  value: string;
  delta?: string;
  tone?: string;
}) {
  return (
    <div className={`kpi ${tone || ""}`}>
      <small>{label}</small>
      <strong>{value}</strong>
      {delta && <em>{delta}</em>}
    </div>
  );
}

function Segment<T extends string>({
  value,
  onChange,
  options,
}: {
  value: T;
  onChange: (v: T) => void;
  options: { v: T; l: string }[];
}) {
  return (
    <div className="segment">
      {options.map((o) => (
        <button
          key={o.v}
          className={value === o.v ? "active" : ""}
          onClick={() => onChange(o.v)}
        >
          {o.l}
        </button>
      ))}
    </div>
  );
}

function StatusPanel({ text, error = false }: { text: string; error?: boolean }) {
  return <div className={`status-panel ${error ? "error" : ""}`}><Activity /> <span>{text}</span></div>;
}

function ChartFrame({ children, label }: { children: React.ReactNode; label: string }) {
  const [zoom, setZoom] = useState(1);
  return <div className="chart-frame">
    <div className="chart-tools" aria-label={label}>
      <span><MoveHorizontal />{label}</span>
      <button onClick={() => setZoom((z) => Math.min(3, z + .25))} aria-label="Zoom in"><ZoomIn /></button>
      <button onClick={() => setZoom((z) => Math.max(1, z - .25))} aria-label="Zoom out"><ZoomOut /></button>
      <button onClick={() => setZoom(1)} aria-label="Reset">1:1</button>
    </div>
    <div className="chart-scroll"><div style={{ width: `${zoom * 100}%`, minWidth: "100%" }}>{children}</div></div>
  </div>;
}

function DriverChart({ lang, data }: { lang: Lang; data: DriverResult[] }) {
  const localizedDrivers = data.map((driver) => ({ ...driver, name: lang === "en" ? driver.nameEn : driver.nameZh, value: driver.impact }));
  return (
    <ChartFrame label={tx(lang, "缩放后可左右浏览", "Zoom, then scroll horizontally")}><div className="chart medium">
      <ResponsiveContainer>
        <BarChart
          data={localizedDrivers}
          layout="vertical"
          margin={{ left: 28, right: 28 }}
        >
          <CartesianGrid horizontal={false} stroke="#e6e0dc" />
          <XAxis type="number" tick={{ fontSize: 11 }} unit={tx(lang, " 美元", " USD")} />
          <YAxis
            type="category"
            dataKey="name"
            width={126}
            tick={{ fontSize: 11 }}
          />
          <Tooltip formatter={(v) => [tx(lang, `${v} 美元/桶`, `$${v}/bbl`), tx(lang, "估计净影响", "Estimated net impact")]} />
          <ReferenceLine x={0} stroke="#968d87" />
          <Bar dataKey="value" radius={[0, 8, 8, 0]}>
            {localizedDrivers.map((d, i) => (
              <Cell key={i} fill={d.value > 0 ? "#587a9a" : "#c47d59"} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div></ChartFrame>
  );
}

function ForecastChart({ data, lang }: { data: PriceRow[]; lang: Lang }) {
  const rows = data.map((r) => ({
    ...r,
    band95: r.lo95 == null ? undefined : [r.lo95, r.hi95],
    band80: r.lo80 == null ? undefined : [r.lo80, r.hi80],
    band50: r.lo50 == null ? undefined : [r.lo50, r.hi50],
  }));
  const cutoff = data.filter((r) => r.actual != null).at(-1)?.date;
  return (
    <ChartFrame label={tx(lang, "拖动底部范围条或缩放图表", "Drag the range selector or zoom the chart")}><div className="chart large">
      <ResponsiveContainer>
        <ComposedChart
          data={rows}
          margin={{ left: 2, right: 16, top: 15, bottom: 5 }}
        >
          <CartesianGrid vertical={false} stroke="#e6e0dc" />
          <XAxis dataKey="date" minTickGap={45} tick={{ fontSize: 11 }} />
          <YAxis
            domain={["dataMin - 3", "dataMax + 3"]}
            tick={{ fontSize: 11 }}
            unit="$"
          />
          <Tooltip />
          <Legend />
          <Area
            dataKey="band95"
            name={tx(lang, "95%区间", "95% range")}
            stroke="#a9bacb"
            fill="#dfe7ee"
            fillOpacity={0.62}
          />
          <Area
            dataKey="band80"
            name={tx(lang, "80%区间", "80% range")}
            stroke="#8b87b5"
            fill="#d9d6e8"
            fillOpacity={0.62}
          />
          <Area
            dataKey="band50"
            name={tx(lang, "50%区间", "50% range")}
            stroke="#c78a67"
            fill="#ead2c2"
            fillOpacity={0.72}
          />
          <Line
            dataKey="actual"
            name={tx(lang, "实际价格", "Actual price")}
            stroke="#30343d"
            strokeWidth={2.4}
            dot={false}
          />
          <Line
            dataKey="forecast"
            name={tx(lang, "预测中位路径", "Median forecast")}
            stroke="#69649b"
            strokeWidth={2.6}
            dot={false}
          />
          {cutoff && (
            <ReferenceLine
              x={cutoff}
              stroke="#928985"
              strokeDasharray="4 4"
              label={{ value: tx(lang, "预测起点", "Forecast start"), fontSize: 11, fill: "#746e6a" }}
            />
          )}
          <Brush dataKey="date" height={24} stroke="#6f69a2" travellerWidth={8} />
        </ComposedChart>
      </ResponsiveContainer>
    </div></ChartFrame>
  );
}

function RiskChart({ lang, data, threshold }: { lang: Lang; data: Array<{ date: string; score: number }>; threshold: number }) {
  return (
    <ChartFrame label={tx(lang, "拖动底部范围条查看历史", "Drag the range selector to inspect history")}><div className="chart small">
      <ResponsiveContainer>
        <AreaChart data={data}>
          <CartesianGrid vertical={false} stroke="#e6e0dc" />
          <XAxis dataKey="date" minTickGap={35} tick={{ fontSize: 10 }} />
          <YAxis domain={[0, 100]} tick={{ fontSize: 10 }} />
          <Tooltip />
          <Area
            dataKey="score"
            name={tx(lang, "历史风险分位", "Historical risk percentile")}
            stroke="#7771a7"
            fill="#d6d2e7"
            fillOpacity={0.55}
          />
          <ReferenceLine
            y={threshold}
            label={tx(lang, "复核阈值", "Review threshold")}
            stroke="#ab5e59"
            strokeDasharray="4 4"
          />
          <Brush dataKey="date" height={20} stroke="#7771a7" />
        </AreaChart>
      </ResponsiveContainer>
    </div></ChartFrame>
  );
}

function ScaleCard({ lang, components }: { lang: Lang; components: ComponentResult[] }) {
  const dates = components[0]?.points.map((point) => point.date) || [];
  const rows = dates.map((date, index) => Object.fromEntries([["date", date], ...components.map((component) => [component.imf, component.points[index]?.value])]));
  return (
    <Card
      title={tx(lang, "油价自身的三层波动", "Three layers of oil-price movement")}
      desc={tx(lang, "把复杂分量整理为可理解的短、中、长周期；专业模式保留全部中间分量。", "Complex components are grouped into intuitive short-, medium- and long-horizon movements; research mode keeps every component.")}
    >
      <div className="scale-legend">{components.map((component, index) => <span key={component.imf}><i style={{background:["#c47d59","#587a9a","#756fa5","#4f8b7d","#b49958","#8b6e78","#527f91","#9a7454"][index]}} />{component.imf} · {(lang === "zh" ? component.channelZh : component.channelEn)} · {component.volatilityShare.toFixed(1)}%</span>)}</div>
      <ChartFrame label={tx(lang, "缩放并左右浏览分量", "Zoom and scroll through components")}><div className="chart small">
        <ResponsiveContainer>
          <LineChart data={rows}>
            <CartesianGrid vertical={false} stroke="#e6e0dc" />
            <XAxis dataKey="date" minTickGap={35} tick={{fontSize:10}} />
            <YAxis tick={{ fontSize: 10 }} />
            <Tooltip />
            {components.map((component, index) => <Line key={component.imf} dataKey={component.imf} name={component.imf} stroke={["#c47d59","#587a9a","#756fa5","#4f8b7d","#b49958","#8b6e78","#527f91","#9a7454"][index]} strokeWidth={index === components.length - 1 ? 2.4 : 1.4} dot={false} />)}
            <Brush dataKey="date" height={18} stroke="#756fa5" />
          </LineChart>
        </ResponsiveContainer>
      </div></ChartFrame>
      <p className="plain-note">{tx(lang, "分量名称沿用研究方法中的经济解释；图中数值均由当前目标序列的VMD结果生成。", "Component labels follow the research interpretation; every plotted value comes from the current target series VMD run.")}</p>
    </Card>
  );
}

type Hedge = {
  volume: number;
  budget: number;
  ratio: number;
  futures: number;
  basis: number;
  fx: number;
  margin: number;
  finance: number;
  contract: number;
  fee: number;
  horizon: number;
};
function HedgeCalculator({ lang, market, suggestedRatio }: { lang: Lang; market: number; suggestedRatio: number }) {
  const [v, setV] = useState<Hedge>({
    volume: 300000,
    budget: market,
    ratio: suggestedRatio,
    futures: 70,
    basis: 1.2,
    fx: 7.18,
    margin: 12,
    finance: 3.4,
    contract: 1000,
    fee: 0.035,
    horizon: 90,
  });
  const set = (k: keyof Hedge, n: number) => setV((s) => ({ ...s, [k]: n }));
  const unhedged = v.volume * market * v.fx;
  const protectedBarrels = (v.volume * v.ratio) / 100;
  const futuresGain =
    ((protectedBarrels * v.futures) / 100) *
    (market - v.budget - v.basis) *
    v.fx;
  const optionLike =
    protectedBarrels *
    (1 - v.futures / 100) *
    Math.max(0, market - v.budget) *
    0.62 *
    v.fx;
  const finance =
    ((protectedBarrels * v.budget * v.fx * v.margin) / 100) *
    (v.finance / 100) *
    (v.horizon / 365);
  const fees = (protectedBarrels / v.contract) * v.fee * v.contract * v.fx;
  const hedged = unhedged - futuresGain - optionLike + finance + fees;
  const budget = v.volume * v.budget * v.fx;
  const marginReq = (protectedBarrels * v.budget * v.fx * v.margin) / 100;
  return (
    <Card
      title={tx(lang, "采购成本预警测算", "Procurement cost stress test")}
      desc={tx(lang, "把基差、汇率、保证金、融资和交易费用放进同一张账，不再只看期货盈亏。", "Combine basis, FX, margin, financing and transaction costs in one calculation—not just futures P&L.")}
    >
      <div className="calc-grid">
        <Field
          label={tx(lang, "采购量", "Purchase volume")}
          value={v.volume}
          suffix={tx(lang, "桶", "bbl")}
          onChange={(n) => set("volume", n)}
        />
        <Field
          label={tx(lang, "预算单价", "Budget price")}
          value={v.budget}
          suffix={tx(lang, "美元/桶", "USD/bbl")}
          onChange={(n) => set("budget", n)}
        />
        <Field
          label={tx(lang, "套保覆盖", "Hedge coverage")}
          value={v.ratio}
          suffix="%"
          onChange={(n) => set("ratio", n)}
        />
        <Field
          label={tx(lang, "期货占比", "Futures share")}
          value={v.futures}
          suffix="%"
          onChange={(n) => set("futures", n)}
        />
        <Field
          label={tx(lang, "预计基差", "Expected basis")}
          value={v.basis}
          suffix={tx(lang, "美元/桶", "USD/bbl")}
          onChange={(n) => set("basis", n)}
        />
        <Field
          label={tx(lang, "美元兑人民币", "USD/CNY")}
          value={v.fx}
          suffix="CNY"
          step={0.01}
          onChange={(n) => set("fx", n)}
        />
        <Field
          label={tx(lang, "保证金比例", "Margin rate")}
          value={v.margin}
          suffix="%"
          onChange={(n) => set("margin", n)}
        />
        <Field
          label={tx(lang, "融资年利率", "Annual funding rate")}
          value={v.finance}
          suffix="%"
          step={0.1}
          onChange={(n) => set("finance", n)}
        />
        <Field
          label={tx(lang, "合约规模", "Contract size")}
          value={v.contract}
          suffix={tx(lang, "桶", "bbl")}
          onChange={(n) => set("contract", n)}
        />
        <Field
          label={tx(lang, "单边费用", "One-way fee")}
          value={v.fee}
          suffix={tx(lang, "美元/桶", "USD/bbl")}
          step={0.005}
          onChange={(n) => set("fee", n)}
        />
        <Field
          label={tx(lang, "方案期限", "Plan horizon")}
          value={v.horizon}
          suffix={tx(lang, "天", "days")}
          onChange={(n) => set("horizon", n)}
        />
      </div>
      <div className="result-grid">
        <Kpi
          label={tx(lang, "未套保成本", "Unhedged cost")}
          value={tx(lang, `${(unhedged / 1e6).toFixed(1)} 百万元`, `RMB ${(unhedged / 1e6).toFixed(1)}m`)}
        />
        <Kpi
          label={tx(lang, "套保后净成本", "Net hedged cost")}
          value={tx(lang, `${(hedged / 1e6).toFixed(1)} 百万元`, `RMB ${(hedged / 1e6).toFixed(1)}m`)}
          delta={tx(lang, `节省 ${((unhedged - hedged) / 1e6).toFixed(1)} 百万元`, `Saving RMB ${((unhedged - hedged) / 1e6).toFixed(1)}m`)}
        />
        <Kpi
          label={tx(lang, "相对预算", "Versus budget")}
          value={tx(lang, `${((hedged - budget) / 1e6).toFixed(1)} 百万元`, `RMB ${((hedged - budget) / 1e6).toFixed(1)}m`)}
          tone={hedged > budget ? "warm" : ""}
        />
        <Kpi
          label={tx(lang, "保证金需求", "Margin requirement")}
          value={tx(lang, `${(marginReq / 1e6).toFixed(1)} 百万元`, `RMB ${(marginReq / 1e6).toFixed(1)}m`)}
          delta={tx(lang, `融资成本 ${(finance / 1e4).toFixed(1)} 万元`, `Funding cost RMB ${(finance / 1e3).toFixed(0)}k`)}
        />
      </div>
    </Card>
  );
}

function Field({
  label,
  value,
  suffix,
  onChange,
  step = 1,
  min,
  max,
}: {
  label: string;
  value: number;
  suffix: string;
  onChange: (n: number) => void;
  step?: number;
  min?: number;
  max?: number;
}) {
  const clamp = (next: number) => onChange(Math.min(max ?? Number.POSITIVE_INFINITY, Math.max(min ?? Number.NEGATIVE_INFINITY, next)));
  return (
    <label className="field">
      <span>{label}</span>
      <div>
        <input
          type="number"
          value={value}
          step={step}
          min={min}
          max={max}
          onChange={(e) => { const next = Number(e.target.value); if (Number.isFinite(next)) clamp(next); }}
        />
        <em>{suffix}</em>
        <span className="stepper"><button type="button" onClick={() => clamp(value-step)} aria-label="Decrease"><Minus /></button><button type="button" onClick={() => clamp(value+step)} aria-label="Increase"><Plus /></button></span>
      </div>
    </label>
  );
}

function DateField({ lang, label, value, onChange }: { lang: Lang; label: string; value: string; onChange: (value: string) => void }) {
  const valid = /^\d{4}-\d{2}-\d{2}$/.test(value) && !Number.isNaN(Date.parse(`${value}T00:00:00Z`));
  return <label className={`field date-field ${valid ? "" : "invalid"}`}><span>{label}</span><div><input lang={lang === "zh" ? "zh-CN" : "en-US"} type="text" inputMode="numeric" autoComplete="off" value={value} placeholder={lang === "zh" ? "年-月-日" : "YYYY-MM-DD"} aria-label={label} onChange={(e) => onChange(e.target.value)} /><em>{lang === "zh" ? "年-月-日" : "YYYY-MM-DD"}</em></div>{!valid && <small>{tx(lang,"请输入有效日期，例如 2020-01-31","Enter a valid date, for example 2020-01-31")}</small>}</label>;
}

function GrangerChart({ lang, data, alpha }: { lang: Lang; data: GrangerResult[]; alpha: number }) {
  const rows = data.map((row) => ({ name: lang === "zh" ? row.nameZh : row.nameEn, score: -Math.log10(Math.max(row.pValue, 1e-12)) }));
  return <ChartFrame label={tx(lang,"缩放查看检验结果","Zoom to inspect test results")}><div className="chart medium"><ResponsiveContainer><BarChart data={rows} layout="vertical" margin={{left:35,right:25}}><CartesianGrid horizontal={false}/><XAxis type="number"/><YAxis type="category" dataKey="name" width={150} tick={{fontSize:10}}/><Tooltip formatter={(v) => [Number(v).toFixed(3), "−log10(p)"]}/><ReferenceLine x={-Math.log10(alpha)} stroke="#c47d59" strokeDasharray="5 4" label={{value:`α=${alpha}`,fontSize:10}}/><Bar dataKey="score" fill="#587a9a" radius={[0,8,8,0]}/></BarChart></ResponsiveContainer></div></ChartFrame>;
}

function RollingImpactChart({ lang, data }: { lang: Lang; data: NetImpactResult["rolling"] }) {
  return <ChartFrame label={tx(lang,"拖动底部范围条查看滚动结果","Drag the range selector to inspect the rolling result")}><div className="chart medium"><ResponsiveContainer><LineChart data={data}><CartesianGrid vertical={false}/><XAxis dataKey="date" minTickGap={35} tick={{fontSize:10}}/><YAxis tick={{fontSize:10}}/><Tooltip/><Legend/><Line dataKey="observed" name={tx(lang,"实际变动","Observed change")} stroke="#30343d" dot={false}/><Line dataKey="fitted" name={tx(lang,"模型拟合","Model fit")} stroke="#6f69a2" dot={false}/><Brush dataKey="date" height={22} stroke="#6f69a2"/></LineChart></ResponsiveContainer></div></ChartFrame>;
}

function FevdChart({ lang, data }: { lang: Lang; data: NetImpactResult["fevd"] }) {
  const rows = data.map((row) => ({ name: lang === "zh" ? row.nameZh : row.nameEn, share: row.share }));
  return <ChartFrame label={tx(lang,"缩放查看各因素对油价预测误差的解释份额","Zoom to inspect factor shares of oil-price forecast error variance")}><div className="chart medium"><ResponsiveContainer><BarChart data={rows} layout="vertical" margin={{left:35,right:30}}><CartesianGrid horizontal={false}/><XAxis type="number" unit="%"/><YAxis type="category" dataKey="name" width={150} tick={{fontSize:10}}/><Tooltip formatter={(v)=>[`${Number(v).toFixed(2)}%`,tx(lang,"份额","Share")]}/><Bar dataKey="share" fill="#c47d59" radius={[0,8,8,0]}/></BarChart></ResponsiveContainer></div></ChartFrame>;
}

function RollingFevdChart({ lang, data }: { lang: Lang; data: NetImpactResult["rollingFevd"] }) {
  return <ChartFrame label={tx(lang,"拖动范围条查看冲击来源随时间的变化","Drag the range selector to inspect changing shock sources")}><div className="chart medium"><ResponsiveContainer><AreaChart data={data}><CartesianGrid vertical={false}/><XAxis dataKey="date" minTickGap={35} tick={{fontSize:10}}/><YAxis domain={[0,100]} unit="%"/><Tooltip formatter={(v)=>`${Number(v).toFixed(2)}%`}/><Legend/><Area dataKey="externalShare" name={tx(lang,"外部因素冲击","External-factor shocks")} stackId="1" stroke="#c47d59" fill="#ead0c1"/><Area dataKey="ownShare" name={tx(lang,"油价自身冲击","Oil-price own shocks")} stackId="1" stroke="#6f69a2" fill="#d9d5ea"/><Brush dataKey="date" height={22} stroke="#6f69a2"/></AreaChart></ResponsiveContainer></div></ChartFrame>;
}

function BreakChart({ lang, data }: { lang: Lang; data: NetImpactResult["breakTest"]["profile"] }) {
  return <ChartFrame label={tx(lang,"拖动范围条检查候选结构变化日期","Drag the range selector to inspect candidate break dates")}><div className="chart medium"><ResponsiveContainer><LineChart data={data}><CartesianGrid vertical={false}/><XAxis dataKey="date" minTickGap={35} tick={{fontSize:10}}/><YAxis unit="%"/><Tooltip formatter={(v)=>[`${Number(v).toFixed(2)}%`,tx(lang,"分段拟合改善","Segmented-fit improvement")]}/><Line dataKey="improvementPercent" stroke="#587a9a" dot={false}/><Brush dataKey="date" height={22} stroke="#587a9a"/></LineChart></ResponsiveContainer></div></ChartFrame>;
}

function ScaleGrangerMatrix({ lang, data }: { lang: Lang; data: ScaleGrangerResult[] }) {
  const imfs = [...new Set(data.map((row) => row.imf))];
  const factors = [...new Map(data.map((row) => [row.id, { id: row.id, name: lang === "zh" ? row.nameZh : row.nameEn }])).values()];
  return <div className="scale-matrix" style={{"--imf-count":imfs.length} as React.CSSProperties}>
    <div className="matrix-head"><b>{tx(lang,"解释变量","Factor")}</b>{imfs.map((imf)=><b key={imf}>{imf}</b>)}</div>
    {factors.map((factor)=><div className="matrix-row" key={factor.id}><strong>{factor.name}</strong>{imfs.map((imf)=>{const row=data.find((item)=>item.id===factor.id&&item.imf===imf)!; const intensity=Math.min(1,Math.max(0,-Math.log10(Math.max(row.pValue,1e-12))/4)); return <span key={imf} className={row.significant?"significant":""} style={{"--strength":intensity} as React.CSSProperties} title={`${factor.name} · ${imf} · lag ${row.lag} · F ${row.fStatistic.toFixed(3)} · p ${row.pValue.toFixed(4)}`}>{row.pValue.toFixed(3)}</span>})}</div>)}
  </div>;
}
function Advice({
  n,
  title,
  text,
}: {
  n: string;
  title: string;
  text: string;
}) {
  return (
    <article>
      <small>{n}</small>
      <h3>{title}</h3>
      <p>{text}</p>
    </article>
  );
}

function Professional({
  lang,
  t,
}: {
  lang: Lang;
  t: typeof copy.zh | typeof copy.en;
}) {
  const [tab, setTab] = useState<ProTab>("impact");
  return (
    <div className="page">
      <PageIntro
        eyebrow="Research workspace"
        title={
          lang === "zh"
            ? "验证每一步，而不是只看结论"
            : "Inspect every step, not only the answer"
        }
        desc={
          lang === "zh"
            ? "净影响、价格预测、危机预警和数据工具彼此独立，参数与中间结果完整保留。"
            : "Full parameters and intermediate outputs for reproducible research."
        }
      />
      <div className="pro-tabs" role="tablist">
        <Tab id="impact" active={tab} set={setTab} icon={<BarChart3 />}>
          {tx(lang, "净影响分析", "Net-impact analysis")}
        </Tab>
        <Tab id="forecast" active={tab} set={setTab} icon={<TrendingUp />}>
          {tx(lang, "价格预测", "Price forecast")}
        </Tab>
        <Tab id="risk" active={tab} set={setTab} icon={<ShieldCheck />}>
          {tx(lang, "危机预警", "Risk warning")}
        </Tab>
        <Tab id="data" active={tab} set={setTab} icon={<Database />}>
          {t.source}
        </Tab>
      </div>
      {tab === "impact" && <ImpactLab lang={lang} />}
      {tab === "forecast" && <ForecastLab lang={lang} />}
      {tab === "risk" && <RiskLab lang={lang} />}
      {tab === "data" && <DataLab lang={lang} />}
    </div>
  );
}
function Tab({
  id,
  active,
  set,
  icon,
  children,
}: {
  id: ProTab;
  active: ProTab;
  set: (v: ProTab) => void;
  icon: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <button
      role="tab"
      aria-selected={active === id}
      className={active === id ? "active" : ""}
      onClick={() => set(id)}
    >
      {icon}
      {children}
    </button>
  );
}

function ImpactLab({ lang }: { lang: Lang }) {
  const [imf, setImf] = useState(5);
  const [window, setWindow] = useState(60);
  const [maxLag, setMaxLag] = useState(5);
  const [fevdHorizon, setFevdHorizon] = useState(12);
  const [alpha, setAlpha] = useState(.1);
  const [start, setStart] = useState("2005-01-01");
  const [end, setEnd] = useState(new Date().toISOString().slice(0, 10));
  const [target, setTarget] = useState("EIA-BRENT");
  const [available, setAvailable] = useState<DataSeries[]>([]);
  const [factors, setFactors] = useState<Set<string>>(new Set());
  const [result, setResult] = useState<NetImpactResult | null>(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => {
    void fetchCatalog().then((items) => {
      const baseRows = items as unknown as DataSeries[];
      const records = readLocalRecords().filter((r) => r.kind === "series");
      const savedRows = records.filter((record) => !baseRows.some((item) => item.id === record.id)).map((record) => ({ id: record.id, name: String(record.payload.name || record.label), nameEn: String(record.payload.nameEn || record.label), source: String(record.payload.source || "FRED"), unit: String(record.payload.unit || ""), frequency: String(record.payload.frequency || ""), updated: record.savedAt.slice(0,10), color: String(record.payload.color || "#587a9a") }));
      const rows = [...baseRows, ...savedRows]; setAvailable(rows);
      const saved = new Set(records.map((r) => r.id));
      const defaults = rows.filter((item) => item.id !== target && (saved.has(item.id) || ["FRED-PETINV","FRED-DTWEXBGS","FRED-DGS10","FRED-INDPRO","FRED-T10YIE","FRED-VIXCLS","FRED-HENRYHUB"].includes(item.id))).map((item) => item.id);
      setFactors(new Set(defaults));
    }).catch((reason) => setError(reason instanceof Error ? reason.message : String(reason)));
  }, [target]);
  const run = async () => {
    setRunning(true); setError(""); setResult(null);
    try {
      const payload = await requestLiveAnalysis<NetImpactResult>("/api/models/net-impact", { imf, window, maxLag, fevdHorizon, alpha, start, end, target, factors: [...factors] });
      if (payload) setResult(payload);
    } catch (reason) { setError(reason instanceof Error ? reason.message : String(reason)); }
    finally { setRunning(false); }
  };
  const eligible = available.filter((item) => item.id !== target);
  const toggleFactor = (id: string) => setFactors((current) => { const next = new Set(current); next.has(id) ? next.delete(id) : next.add(id); return next; });
  return (
    <Card
      title={tx(lang, "多尺度净影响分析", "Multi-scale net-impact analysis")}
      desc={tx(lang, "选择官方变量并运行完整的数据对齐、VMD、格兰杰检验和贡献估计。没有成功计算时不会显示替代图。", "Select official variables and run alignment, VMD, Granger tests and contribution estimation. No substitute chart is shown when computation fails.")}
      action={<span className="data-badge">{result ? tx(lang, `真实计算 · ${result.asOf}`, `Verified run · ${result.asOf}`) : tx(lang, "等待运行", "Awaiting run")}</span>}
    >
      <div className="lab-layout">
        <aside>
          <h3>
            <Settings2 />
            {tx(lang, "分析参数", "Analysis settings")}
          </h3>
          <label className="field"><span>{tx(lang, "目标油价", "Target price")}</span><div><select value={target} onChange={(e) => setTarget(e.target.value)}><option value="EIA-BRENT">Brent</option><option value="FRED-DCOILWTICO">WTI</option></select></div></label>
          <Field label={tx(lang, "分量数量", "Component count")} value={imf} suffix={tx(lang, "个", "components")} min={3} max={8} onChange={setImf} />
          <Field
            label={tx(lang, "滚动窗口", "Rolling window")}
            value={window}
            suffix={tx(lang, "月", "months")}
            min={24}
            max={180}
            onChange={setWindow}
          />
          <Field label={tx(lang, "最大格兰杰滞后", "Maximum Granger lag")} value={maxLag} suffix={tx(lang, "阶", "lags")} min={1} max={6} onChange={setMaxLag} />
          <Field label={tx(lang, "FEVD预测期", "FEVD horizon")} value={fevdHorizon} suffix={tx(lang, "期", "steps")} min={2} max={36} onChange={setFevdHorizon} />
          <Field label={tx(lang, "显著性阈值", "Significance level")} value={alpha} suffix="α" step={.01} min={.01} max={.2} onChange={setAlpha} />
          <DateField lang={lang} label={tx(lang, "估计开始", "Estimation start")} value={start} onChange={setStart} />
          <DateField lang={lang} label={tx(lang, "估计结束", "Estimation end")} value={end} onChange={setEnd} />
          <button className="primary compact" disabled={running || factors.size === 0} onClick={() => void run()}>{running ? tx(lang, "正在获取并计算…", "Fetching and calculating…") : tx(lang, "运行完整分析", "Run full analysis")}</button>
        </aside>
        <div>
          <div className="factor-head"><b>{tx(lang, `解释变量（已选 ${factors.size}）`, `Explanatory variables (${factors.size} selected)`)}</b><div><button onClick={() => setFactors(new Set(eligible.map((item) => item.id)))}>{tx(lang, "全选", "Select all")}</button><button onClick={() => setFactors(new Set())}>{tx(lang, "清空", "Clear")}</button></div></div>
          <div className="factor-grid">{eligible.map((item) => <label key={item.id} className={factors.has(item.id) ? "active" : ""}><input type="checkbox" checked={factors.has(item.id)} onChange={() => toggleFactor(item.id)} /><span><b>{seriesText(item, lang).name}</b><small>{item.source} · {item.id}</small></span></label>)}</div>
          {error && <StatusPanel error text={tx(lang, `分析未完成：${error}`, `Analysis did not complete: ${error}`)} />}
          {!result && !error && <StatusPanel text={tx(lang, "设置参数后运行；结果区只接受真实接口返回。", "Configure and run the model. The result area accepts verified API output only.")} />}
          {result && <>
            <div className="metric-table"><span><b>{tx(lang,"共同样本","Aligned observations")}</b>{result.observations}</span><span><b>R²</b>{result.rSquared.toFixed(3)}</span><span><b>{tx(lang,"数据截止","As of")}</b>{result.asOf}</span></div>
            <h3 className="result-title">A · {tx(lang,"最新一期因素贡献","Latest factor contributions")}</h3><DriverChart lang={lang} data={result.drivers} />
            <h3 className="result-title">B · VMD</h3><ScaleCard lang={lang} components={result.components} />
            <h3 className="result-title">C · {tx(lang,"格兰杰检验","Granger tests")}</h3><GrangerChart lang={lang} data={result.granger} alpha={alpha} />
            <div className="granger-table">{result.granger.map((row) => <div key={row.id}><b>{lang === "zh" ? row.nameZh : row.nameEn}</b><span>lag {row.lag}</span><span>F {row.fStatistic.toFixed(3)}</span><span>p {row.pValue.toFixed(4)}</span><em className={row.significant ? "yes" : ""}>{row.significant ? tx(lang,"通过","Pass") : tx(lang,"未通过","Not significant")}</em></div>)}</div>
            <h3 className="result-title">D · {tx(lang,"逐分量格兰杰检验","Granger tests by IMF")}</h3>
            <ScaleGrangerMatrix lang={lang} data={result.scaleGranger}/>
            <h3 className="result-title">E · {tx(lang,`广义FEVD（${result.fevdHorizon}期，VAR(${result.varLag})）`,`Generalized FEVD (${result.fevdHorizon} steps, VAR(${result.varLag}))`)}</h3><FevdChart lang={lang} data={result.fevd}/>
            <div className="metric-table"><span><b>{tx(lang,"油价自身冲击份额","Oil-price own-shock share")}</b>{result.fevdOwnShare.toFixed(2)}%</span><span><b>{tx(lang,"外部因素冲击份额","External-factor shock share")}</b>{(100-result.fevdOwnShare).toFixed(2)}%</span></div>
            <h3 className="result-title">F · {tx(lang,"滚动FEVD","Rolling FEVD")}</h3><RollingFevdChart lang={lang} data={result.rollingFevd}/>
            <h3 className="result-title">G · {tx(lang,"滚动样本拟合","Rolling-window fit")}</h3><RollingImpactChart lang={lang} data={result.rolling} />
            <h3 className="result-title">H · {tx(lang,"结构变化候选检验","Candidate structural-break test")}</h3><BreakChart lang={lang} data={result.breakTest.profile}/>
            <div className="metric-table"><span><b>{tx(lang,"最优候选日期","Best candidate date")}</b>{result.breakTest.bestDate}</span><span><b>{tx(lang,"分段RSS改善","Segmented RSS improvement")}</b>{result.breakTest.rssImprovementPercent.toFixed(2)}%</span><span><b>{tx(lang,"检验候选数","Candidates tested")}</b>{result.breakTest.candidateCount}</span></div>
            <div className="provenance"><Database/><span><b>{tx(lang,"本次数据血缘","Data provenance")}</b><small>{result.sources.map((s) => `${lang === "zh" ? s.nameZh : s.nameEn} [FRED:${s.providerId}]`).join(" · ")}</small></span></div>
          </>}
          <div className="method-steps">
            <span>{tx(lang, "01 数据对齐", "01 Data alignment")}</span>
            <span>{tx(lang, `02 分解 ${imf} 个分量`, `02 Decompose ${imf} components`)}</span>
            <span>{tx(lang, "03 BIC选择滞后与格兰杰检验", "03 BIC lag selection and Granger tests")}</span>
            <span>{tx(lang, "04 逐分量检验与尺度筛选", "04 IMF-level tests and scale selection")}</span>
            <span>{tx(lang, "05 广义FEVD与滚动冲击份额", "05 Generalized and rolling FEVD")}</span>
            <span>{tx(lang, "06 滚动拟合与结构变化检验", "06 Rolling fit and structural-break search")}</span>
          </div>
        </div>
      </div>
    </Card>
  );
}

function ForecastLab({ lang }: { lang: Lang }) {
  const [freq, setFreq] = useState<Frequency>("monthly");
  const [h, setH] = useState(12);
  const [training, setTraining] = useState(120);
  const [imf, setImf] = useState(5);
  const [target, setTarget] = useState("EIA-BRENT");
  const [liveData, setLiveData] = useState<PriceRow[]>([]);
  const [metrics, setMetrics] = useState<Record<string, number>>({});
  const [running, setRunning] = useState(false);
  const [error, setError] = useState("");
  const run = async () => {
    setRunning(true); setError(""); setLiveData([]); setMetrics({});
    try {
      const result = await requestLiveAnalysis<ForecastResult>("/api/models/forecast", { horizon: h, frequency: freq, training, imf, target });
      if (result) {
        setLiveData([
          ...result.history.map((row) => ({ date: row.Date, actual: row.Actual })),
          ...result.forecast.map((row) => ({ date: String(row.Date), forecast: Number(row.PointForecast), lo50: Number(row.Lower50), hi50: Number(row.Upper50), lo80: Number(row.Lower80), hi80: Number(row.Upper80), lo95: Number(row.Lower95), hi95: Number(row.Upper95) })),
        ]);
        setMetrics(result.metrics);
      }
    } catch (reason) { setError(reason instanceof Error ? reason.message : String(reason)); }
    finally { setRunning(false); }
  };
  return (
    <Card
      title={tx(lang, "价格预测实验", "Price forecasting lab")}
      desc={tx(lang, "可调整频率、预测期限与训练窗口，并查看三层概率区间。", "Adjust frequency, forecast horizon and training window, then inspect three probability ranges.")}
      action={
        <Segment
          value={freq}
          onChange={setFreq}
          options={[
            { v: "daily", l: tx(lang, "日度", "Daily") },
            { v: "monthly", l: tx(lang, "月度", "Monthly") },
          ]}
        />
      }
    >
      <div className="inline-fields">
        <label className="field"><span>{tx(lang,"目标油价","Target price")}</span><div><select value={target} onChange={(e) => setTarget(e.target.value)}><option value="EIA-BRENT">Brent</option><option value="FRED-DCOILWTICO">WTI</option></select></div></label>
        <Field
          label={tx(lang, "预测期限", "Forecast horizon")}
          value={h}
          suffix={freq === "daily" ? tx(lang, "天", "days") : tx(lang, "月", "months")}
          onChange={setH}
          min={1}
          max={60}
        />
        <Field label={tx(lang, "训练窗口", "Training window")} value={training} suffix={freq === "daily" ? tx(lang,"个观测","observations") : tx(lang,"月","months")} min={60} max={1500} onChange={setTraining} />
        <Field label={tx(lang,"VMD分量","VMD components")} value={imf} suffix={tx(lang,"个","components")} min={3} max={8} onChange={setImf}/>
        <label className="field">
          <span>{tx(lang, "模型组合", "Model ensemble")}</span>
          <div>
            <select defaultValue="ensemble">
              <option value="ensemble">{tx(lang, "多尺度组合", "Multi-scale ensemble")}</option>
              <option value="linear">{tx(lang, "线性基准", "Linear baseline")}</option>
              <option value="tree">{tx(lang, "树模型", "Tree model")}</option>
            </select>
          </div>
        </label>
      </div>
      <button className="primary compact" onClick={() => void run()}>{running ? tx(lang, "模型运行中…", "Model running…") : tx(lang, "用最新数据运行模型", "Run on latest data")}</button>
      {error && <StatusPanel error text={tx(lang,`预测未完成：${error}`,`Forecast did not complete: ${error}`)}/>} {!liveData.length && !error && <StatusPanel text={tx(lang,"运行后展示真实历史、预测与滚动验证结果。","Run the model to display verified history, forecasts and rolling validation.")}/>} {liveData.length > 0 && <ForecastChart data={liveData} lang={lang} />}
      {liveData.length > 0 && <div className="metric-table">
        <span>
          <b>MAE</b> {metrics.ValidationMAE?.toFixed?.(2)}
        </span>
        <span>
          <b>RMSE</b> {metrics.ValidationRMSE?.toFixed?.(2)}
        </span>
        <span>
          <b>{tx(lang, "方向准确率", "Directional accuracy")}</b> {metrics.DirectionalAccuracyPercent?.toFixed?.(1)}%
        </span>
        <span>
          <b>{tx(lang, "80%区间验证覆盖率", "80% validation coverage")}</b> {metrics.IntervalCoveragePercent?.toFixed?.(1)}%
        </span>
        <span><b>{tx(lang,"滚动验证起点","Rolling validation origins")}</b>{metrics.ValidationOrigins}</span>
      </div>}
    </Card>
  );
}

function RiskLab({ lang }: { lang: Lang }) {
  const [threshold, setThreshold] = useState(70);
  const [forward, setForward] = useState(20);
  const [target, setTarget] = useState("EIA-BRENT");
  const [liveRisk, setLiveRisk] = useState<RiskResult | null>(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState("");
  const run = async () => {
    setRunning(true); setError(""); setLiveRisk(null);
    try {
      const result = await requestLiveAnalysis<RiskResult>("/api/models/risk", { target, forward, threshold });
      if (result) setLiveRisk(result);
    } catch (reason) { setError(reason instanceof Error ? reason.message : String(reason)); }
    finally { setRunning(false); }
  };
  return (
    <Card
      title={tx(lang, "危机风险预警", "Crisis-risk warning")}
      desc={tx(lang, "预警用于排序与触发复核，不把风险概率解释成确定事件。", "Warnings rank risk and trigger review; they do not treat a probability as a certain event.")}
    >
      <div className="lab-layout">
        <aside>
          <h3>
            <Gauge />
            {tx(lang, "预警设置", "Warning settings")}
          </h3>
          <label className="field"><span>{tx(lang,"目标油价","Target price")}</span><div><select value={target} onChange={(e) => setTarget(e.target.value)}><option value="EIA-BRENT">Brent</option><option value="FRED-DCOILWTICO">WTI</option></select></div></label>
          <Field
            label={tx(lang, "高风险阈值", "High-risk threshold")}
            value={threshold}
            suffix={tx(lang, "分", "points")}
            min={1}
            max={99}
            onChange={setThreshold}
          />
          <button className="primary compact" onClick={() => void run()}>{running ? tx(lang, "模型运行中…", "Model running…") : tx(lang, "用最新数据运行预警", "Run latest warning")}</button>
          <Field
            label={tx(lang, "前瞻窗口", "Forward window")}
            value={forward}
            suffix={tx(lang, "交易日", "trading days")}
            min={5}
            max={60}
            onChange={setForward}
          />
          <label className="check">
            <input type="checkbox" defaultChecked />
            {tx(lang, "使用实时窗口分解", "Use live-window decomposition")}
          </label>
          <label className="check">
            <input type="checkbox" defaultChecked />
            {tx(lang, "保留数据时间戳", "Preserve data timestamps")}
          </label>
        </aside>
        <div>
          {error && <StatusPanel error text={tx(lang,`预警未完成：${error}`,`Warning run did not complete: ${error}`)}/>} {!liveRisk && !error && <StatusPanel text={tx(lang,"运行后展示基于真实价格序列计算的历史风险分位。","Run the model to display historical risk percentiles calculated from the official price series.")}/>} {liveRisk && <><RiskChart lang={lang} data={liveRisk.history} threshold={threshold} />
          <div className="metric-table">
            <span>
              <b>{tx(lang, "当前风险分位", "Current risk percentile")}</b> {liveRisk.riskScore.toFixed(1)}
            </span>
            <span>
              <b>{tx(lang, "距离用户阈值", "Distance to user threshold")}</b> {(liveRisk.riskScore-threshold).toFixed(1)}
            </span>
            <span><b>{tx(lang,"历史90%触发阈值","Historical 90% trigger")}</b>{liveRisk.alertThreshold.toFixed(1)}</span>
            <span><b>{tx(lang,"数据截止","As of")}</b>{liveRisk.latestDate}</span>
          </div></>}
        </div>
      </div>
    </Card>
  );
}

function DataLab({ lang }: { lang: Lang }) {
  const [q, setQ] = useState("");
  const [liveCatalog, setLiveCatalog] = useState<DataSeries[]>([]);
  const [sources, setSources] = useState(() => new Set<string>());
  const [selected, setSelected] = useState("");
  const [frequency, setFrequency] = useState<Frequency>("monthly");
  const [liveSeries, setLiveSeries] = useState<Array<{ date: string; value: number }>>([]);
  const [seriesLive, setSeriesLive] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  useEffect(() => {
    let active = true;
    void fetchCatalog()
      .then((items) => {
        if (!active || !items.length) return;
        const next = items as unknown as DataSeries[];
        setLiveCatalog(next);
        setSources(new Set(next.map((item) => item.source)));
        setSelected((current) => next.some((item) => item.id === current) ? current : next[0].id);
      })
      .catch((reason) => setError(reason instanceof Error ? reason.message : String(reason)))
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, []);
  useEffect(() => {
    if (q.trim().length < 2) return;
    const timer = window.setTimeout(() => {
      void fetchCatalog(q).then((items) => {
        const discovered = items as unknown as DataSeries[];
        setLiveCatalog((current) => [...current, ...discovered.filter((item) => !current.some((existing) => existing.id === item.id))]);
        setSources((current) => new Set([...current, ...discovered.map((item) => item.source)]));
      }).catch(() => {});
    }, 350);
    return () => window.clearTimeout(timer);
  }, [q]);
  useEffect(() => {
    if (!selected) return;
    let active = true;
    setLoading(true); setError(""); setLiveSeries([]); setSeriesLive(false);
    void fetchSeries(selected, frequency)
      .then((result) => {
        if (!active) return;
        setLiveSeries(result.points);
        setSeriesLive(true);
      })
      .catch((reason) => {
        if (!active) return;
        setLiveSeries([]);
        setSeriesLive(false);
        setError(reason instanceof Error ? reason.message : String(reason));
      })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [selected, frequency]);
  const found = liveCatalog.filter(
    (x) =>
      sources.has(x.source) &&
      (seriesText(x, lang).name.toLowerCase().includes(q.toLowerCase()) ||
        x.id.toLowerCase().includes(q.toLowerCase())),
  );
  const toggle = (s: string) =>
    setSources((p) => {
      const n = new Set(p);
      n.has(s) ? n.delete(s) : n.add(s);
      return n;
    });
  const save = () => {
    const item = liveCatalog.find((candidate) => candidate.id === selected)!;
    saveLocalRecord({
      id: selected,
      kind: "series",
      label: seriesText(item, lang).name,
      payload: { source: item.source, unit: item.unit, frequency: item.frequency, name: item.name, nameEn: item.nameEn || item.name, color: item.color },
    });
  };
  const download = () => {
    if (!liveSeries.length) return;
    const csv =
      "date,value\n" + liveSeries.map((x) => `${x.date},${x.value}`).join("\n");
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob([csv], { type: "text/csv" }));
    a.download = `${selected}.csv`;
    a.click();
    URL.revokeObjectURL(a.href);
  };
  return (
    <Card
      title={tx(lang, "搜索并连接数据", "Search and connect data")}
      desc={tx(lang, "官方来源默认全选；选择序列后预览、下载或保存到研究库。", "All official sources are selected by default. Preview, download or save any series to the research library.")}
      action={<span className="data-badge">{loading ? tx(lang, "正在连接…", "Connecting…") : tx(lang, `${liveCatalog.length} 个官方序列`, `${liveCatalog.length} official series`)}</span>}
    >
      <div className="source-row">
        {[...new Set(liveCatalog.map((x) => x.source))].map((s) => (
          <button
            key={s}
            className={sources.has(s) ? "active" : ""}
            onClick={() => toggle(s)}
          >
            {s}
          </button>
        ))}
      </div>
      <div className="search">
        <Search />
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder={tx(lang, "输入 Brent、库存、美元、利率……", "Search Brent, inventories, dollar, rates…")}
        />
      </div>
      <div className="data-layout">
        <div className="series-list">
          {found.map((x) => (
            <button
              key={x.id}
              className={selected === x.id ? "active" : ""}
              onClick={() => setSelected(x.id)}
            >
              <i style={{ background: x.color }} />
              <span>
                <b>{seriesText(x, lang).name}</b>
                <small>
                  {x.source} · {seriesText(x, lang).frequency} · {seriesText(x, lang).unit}
                </small>
              </span>
              <em>{x.updated}</em>
            </button>
          ))}
        </div>
        <div className="preview">
          <div className="preview-actions">
            <Segment
              value={frequency}
              onChange={setFrequency}
              options={[
                { v: "monthly", l: tx(lang, "月度", "Monthly") },
                { v: "daily", l: tx(lang, "日度", "Daily") },
              ]}
            />
            <button onClick={save} disabled={!seriesLive}>
              <Save />
              {tx(lang, "保存", "Save")}
            </button>
            <button onClick={download} disabled={!seriesLive}>
              <Download />
              Excel/CSV
            </button>
          </div>
          {error && <StatusPanel error text={tx(lang,`官方数据不可用：${error}`,`Official data unavailable: ${error}`)}/>} {!error && loading && <StatusPanel text={tx(lang,"正在读取官方序列…","Loading the official series…")}/>} {seriesLive && <ChartFrame label={tx(lang,"拖动底部范围条或缩放图表","Drag the range selector or zoom the chart")}><div className="chart small">
            <ResponsiveContainer>
              <LineChart data={liveSeries}>
                <CartesianGrid vertical={false} stroke="#e6e0dc" />
                <XAxis dataKey="date" minTickGap={30} tick={{ fontSize: 10 }} />
                <YAxis tick={{ fontSize: 10 }} />
                <Tooltip />
                <Line
                  dataKey="value"
                  stroke="#6f69a2"
                  strokeWidth={2.4}
                  dot={false}
                />
                <Brush dataKey="date" height={20} stroke="#6f69a2" />
              </LineChart>
            </ResponsiveContainer>
          </div></ChartFrame>}
          <div className="provenance">
            <Database />
            <span>
              <b>{liveCatalog.find((x) => x.id === selected)?.source}</b> ·{" "}
              {selected}
              <small>
                {seriesLive ? tx(lang, "来自官方数据接口；密钥仅保存在 Vercel 服务端。", "Official data feed; credentials remain on the Vercel server.") : tx(lang, "没有显示备用序列；请恢复官方接口后重试。", "No fallback series is displayed; restore the official feed and retry.")}
              </small>
            </span>
          </div>
        </div>
      </div>
    </Card>
  );
}

export default App;
