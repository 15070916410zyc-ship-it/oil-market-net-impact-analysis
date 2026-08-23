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
  Radio,
  Save,
  Search,
  Settings2,
  ShieldCheck,
  Sparkles,
  TrendingUp,
  X,
} from "lucide-react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
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
  catalog,
  drivers,
  makeForecast,
  makeForecastFromHistory,
  riskRows,
  seriesPreview,
  type DataSeries,
  type Frequency,
} from "./data";
import { checkApiHealth, fetchCatalog, fetchSeries, requestLiveAnalysis, saveLocalRecord } from "./storage";

type Lang = "zh" | "en";
type Mode = "landing" | "decision" | "professional";
type ProTab = "impact" | "forecast" | "risk" | "data";
const tx = (lang: Lang, zh: string, en: string) => (lang === "zh" ? zh : en);

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
  name: lang === "en" ? seriesNamesEn[item.id] || item.name : item.name,
  frequency: lang === "en" ? ({ 日度: "Daily", 周度: "Weekly", 月度: "Monthly", 年度: "Annual" }[item.frequency] || item.frequency) : item.frequency,
  unit: lang === "en" ? ({ "美元/桶": "USD/bbl", 千桶: "thousand bbl", 指数: "index", 年度: "annual" }[item.unit] || item.unit) : item.unit,
});

const copy = {
  zh: {
    brand: "油价智析",
    decision: "决策模式",
    professional: "专业模式",
    demo: "演示数据",
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
    demo: "Demo data",
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
          <span title={apiLive ? tx(lang, "官方数据接口已连接", "Official data feed connected") : tx(lang, "数据接口暂不可用，使用演示数据", "Data feed unavailable; using demonstration data")}>
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
  const [quotes, setQuotes] = useState({
    brent: 94.39,
    brentMove: 1.8,
    wti: 90.77,
    wtiMove: 1.4,
    updated: "",
  });
  const [riskScore, setRiskScore] = useState(63.4);

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
          brent: brent?.value ?? current.brent,
          brentMove: brent?.move ?? current.brentMove,
          wti: wti?.value ?? current.wti,
          wtiMove: wti?.move ?? current.wtiMove,
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
          <strong>${quotes.brent.toFixed(2)}</strong>
          <em>{quotes.brentMove >= 0 ? "+" : ""}{quotes.brentMove.toFixed(1)}%</em>
        </div>
        <div className="metric-float mf-two">
          <small>WTI</small>
          <strong>${quotes.wti.toFixed(2)}</strong>
          <em>{quotes.wtiMove >= 0 ? "+" : ""}{quotes.wtiMove.toFixed(1)}%</em>
        </div>
        <div className="metric-float mf-three">
          <small>MARKET RISK</small>
          <strong>{riskScore.toFixed(1)}</strong>
          <em>{riskScore >= 60 ? tx(lang, "中高", "Elevated") : tx(lang, "较低", "Low")}</em>
        </div>
        <div className="pulse-line">
          <span>{quotes.updated ? tx(lang, `数据更新至 ${quotes.updated}`, `Data updated ${quotes.updated}`) : tx(lang, "正在同步官方市场数据", "Syncing official market data")}</span>
          <svg viewBox="0 0 500 160">
            <path d="M0 117 C30 105 45 132 80 110 S125 42 160 70 S214 122 250 82 S310 21 350 59 S405 119 500 42" />
          </svg>
        </div>
      </div>
    </section>
  );
}

function EnergyGlobe({ riskScore, lang }: { riskScore: number; lang: Lang }) {
  const riskTone = riskScore >= 60 ? "risk-high" : "risk-low";
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
        <span>{riskScore >= 60 ? "RISK PULSE" : "ENERGY FLOW"}</span>
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
  const [livePoints, setLivePoints] = useState<Array<{ date: string; value: number }>>([]);
  const [liveUpdated, setLiveUpdated] = useState("");
  const [wti, setWti] = useState<number | null>(null);
  useEffect(() => {
    let active = true;
    void Promise.allSettled([
      fetchSeries("EIA-BRENT", frequency),
      fetchSeries("FRED-DCOILWTICO", frequency),
    ]).then(([brentResult, wtiResult]) => {
        const result = brentResult.status === "fulfilled" ? brentResult.value : null;
        if (!active) return;
        setLivePoints(result?.points || []);
        setLiveUpdated(result?.updated || "");
        setWti(
          wtiResult.status === "fulfilled"
            ? wtiResult.value.points.at(-1)?.value ?? null
            : null,
        );
      });
    return () => { active = false; };
  }, [frequency]);
  const forecast = useMemo(
    () => livePoints.length ? makeForecastFromHistory(livePoints, frequency) : makeForecast(frequency),
    [frequency, livePoints],
  );
  const latest =
    forecast.filter((r) => r.actual != null).at(-1)?.actual ?? 94.39;
  return (
    <div className="page">
      <PageIntro
        eyebrow={`Decision intelligence · ${liveUpdated || "2026-08-21"}`}
        title={lang === "zh" ? "今天需要关注什么" : "What matters today"}
        desc={
          lang === "zh"
            ? "先看市场状态，再顺着影响因素、价格路径和风险信号，落到采购与套保动作。"
            : "A connected path from market state to drivers, forecast, risk and action."
        }
      />
      <div className="kpi-grid">
        <Kpi label={tx(lang, "最新数据", "Latest observation")} value={liveUpdated || "2026-08-21"} />
        <Kpi
          label="Brent"
          value={`$${latest.toFixed(2)}`}
          delta={tx(lang, "日变动 +1.8%", "Daily move +1.8%")}
        />
        <Kpi label="WTI" value={wti == null ? tx(lang, "同步中", "Syncing") : `$${wti.toFixed(2)}`} delta={tx(lang, "美国原油现货", "US crude spot")}/>
        <Kpi label={tx(lang, "30日中位路径", "30-day median path")} value="$96.18" delta={tx(lang, "较现价 +1.9%", "+1.9% vs spot")} />
        <Kpi label={tx(lang, "95%决策区间", "95% decision range")} value="$81.3—112.7" />
        <Kpi
          label={tx(lang, "风险温度", "Risk temperature")}
          value="63.4"
          delta={tx(lang, "中高 · 较上周 +6.2", "Elevated · +6.2 WoW")}
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
        action={<span className="data-badge">{tx(lang, "研究基准结果", "Research baseline")}</span>}
      >
        <DriverChart lang={lang} />
        <div className="insight-strip">
          <b>{tx(lang, "当前判断", "Current reading")}</b>
          <span>
            {tx(lang, "供给约束与航运扰动合计推高约", "Supply constraints and shipping disruption add about")} <strong>{tx(lang, "6.2 美元/桶", "$6.2/bbl")}</strong>
            {tx(lang, "，美元和页岩油增产抵消约", ", while the dollar and shale growth offset about")} <strong>{tx(lang, "3.8 美元/桶", "$3.8/bbl")}</strong>{tx(lang, "。", ".")}
          </span>
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
          <RiskChart lang={lang} />
          <div className="risk-summary">
            <Gauge />
            <div>
              <b>{tx(lang, "未来30天：中高风险", "Next 30 days: elevated risk")}</b>
              <p>
                {tx(lang, "航运扰动与隐含波动率同步走高，建议把追加保证金纳入现金安排。", "Shipping disruption and implied volatility are rising together; include potential margin calls in cash planning.")}
              </p>
            </div>
          </div>
        </Card>
        <ScaleCard lang={lang} />
      </div>
      <HedgeCalculator lang={lang} />
      <Card title={t.advice} className="advice">
        <div className="advice-grid">
          <Advice
            n="01"
            title={tx(lang, "采购节奏", "Procurement cadence")}
            text={tx(lang, "未来两周分三批锁定需求，避免在单日波动放大时集中成交。", "Lock demand in three tranches over the next two weeks instead of concentrating execution on a volatile day.")}
          />
          <Advice
            n="02"
            title={tx(lang, "套保比例", "Hedge ratio")}
            text={tx(lang, "当前情景建议覆盖 64%，其中期货占 70%，保留部分敞口参与下行。", "Cover 64% under the current scenario, with futures at 70% of the hedge and some exposure left for downside participation.")}
          />
          <Advice
            n="03"
            title={tx(lang, "资金准备", "Liquidity planning")}
            text={tx(lang, "把保证金与融资成本纳入预算，预留约 820 万元流动性缓冲。", "Budget for margin and financing costs and retain an RMB 8.2 million liquidity buffer.")}
          />
          <Advice
            n="04"
            title={tx(lang, "触发条件", "Review triggers")}
            text={tx(lang, "Brent 突破 101 美元或风险温度高于 72 时，复核并上调覆盖比例。", "Review and raise coverage if Brent crosses $101 or the risk temperature exceeds 72.")}
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

function DriverChart({ lang }: { lang: Lang }) {
  const localizedDrivers = drivers.map((driver) => ({
    ...driver,
    name: lang === "en" ? driverNamesEn[driver.name] || driver.name : driver.name,
  }));
  return (
    <div className="chart medium">
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
    </div>
  );
}

function ForecastChart({ data, lang }: { data: ReturnType<typeof makeForecast>; lang: Lang }) {
  const rows = data.map((r) => ({
    ...r,
    band95: r.lo95 == null ? undefined : [r.lo95, r.hi95],
    band80: r.lo80 == null ? undefined : [r.lo80, r.hi80],
    band50: r.lo50 == null ? undefined : [r.lo50, r.hi50],
  }));
  const cutoff = data.filter((r) => r.actual != null).at(-1)?.date;
  return (
    <div className="chart large">
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
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}

function RiskChart({ lang }: { lang: Lang }) {
  return (
    <div className="chart small">
      <ResponsiveContainer>
        <AreaChart data={riskRows}>
          <CartesianGrid vertical={false} stroke="#e6e0dc" />
          <XAxis dataKey="date" minTickGap={35} tick={{ fontSize: 10 }} />
          <YAxis domain={[0, 100]} tick={{ fontSize: 10 }} />
          <Tooltip />
          <Area
            dataKey="stress"
            name={tx(lang, "压力情景", "Stress scenario")}
            stroke="#c47752"
            fill="#edd0bd"
            fillOpacity={0.45}
          />
          <Area
            dataKey="baseline"
            name={tx(lang, "基准风险", "Baseline risk")}
            stroke="#7771a7"
            fill="#d6d2e7"
            fillOpacity={0.55}
          />
          <ReferenceLine
            y={70}
            label={tx(lang, "高风险", "High risk")}
            stroke="#ab5e59"
            strokeDasharray="4 4"
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}

function ScaleCard({ lang }: { lang: Lang }) {
  const rows = Array.from({ length: 48 }, (_, i) => ({
    i,
    short: Math.sin(i / 2.3) * 2.2,
    medium: Math.sin(i / 7) * 4.1,
    long: Math.sin(i / 19) * 7.4,
  }));
  return (
    <Card
      title={tx(lang, "油价自身的三层波动", "Three layers of oil-price movement")}
      desc={tx(lang, "把复杂分量整理为可理解的短、中、长周期；专业模式保留全部中间分量。", "Complex components are grouped into intuitive short-, medium- and long-horizon movements; research mode keeps every component.")}
    >
      <div className="scale-legend">
        <span>
          <i className="s1" />
          {tx(lang, "短期噪声 22%", "Short-term noise 22%")}
        </span>
        <span>
          <i className="s2" />
          {tx(lang, "中期库存周期 37%", "Inventory cycle 37%")}
        </span>
        <span>
          <i className="s3" />
          {tx(lang, "长期供需趋势 41%", "Long-run supply-demand trend 41%")}
        </span>
      </div>
      <div className="chart small">
        <ResponsiveContainer>
          <LineChart data={rows}>
            <CartesianGrid vertical={false} stroke="#e6e0dc" />
            <XAxis dataKey="i" hide />
            <YAxis tick={{ fontSize: 10 }} />
            <Tooltip />
            <Line dataKey="short" stroke="#c47d59" dot={false} />
            <Line dataKey="medium" stroke="#587a9a" dot={false} />
            <Line
              dataKey="long"
              stroke="#756fa5"
              strokeWidth={2.4}
              dot={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
      <p className="plain-note">
        {tx(lang, "当前以长期供需趋势为主，中期库存周期正在转强；短期噪声较高，但还没有改变主方向。", "The long-run supply-demand trend remains dominant. The inventory cycle is strengthening, while short-term noise has not changed the main direction.")}
      </p>
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
function HedgeCalculator({ lang }: { lang: Lang }) {
  const [v, setV] = useState<Hedge>({
    volume: 300000,
    budget: 94.39,
    ratio: 64,
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
  const market = 101.2;
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
}: {
  label: string;
  value: number;
  suffix: string;
  onChange: (n: number) => void;
  step?: number;
}) {
  return (
    <label className="field">
      <span>{label}</span>
      <div>
        <input
          type="number"
          value={value}
          step={step}
          onChange={(e) => onChange(Number(e.target.value))}
        />
        <em>{suffix}</em>
      </div>
    </label>
  );
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
  const [components, setComponents] = useState<Array<{ imf: string; channelZh: string; volatilityShare: number }>>([]);
  const [running, setRunning] = useState(false);
  const run = async () => {
    setRunning(true);
    try {
      const result = await requestLiveAnalysis<{ components: typeof components }>("/api/models/decomposition", { imf });
      if (result) setComponents(result.components);
    } finally { setRunning(false); }
  };
  return (
    <Card
      title={tx(lang, "多尺度净影响分析", "Multi-scale net-impact analysis")}
      desc={tx(lang, "默认载入最新样本；调整参数后立即刷新演示结果。", "The latest sample loads by default; adjust parameters and rerun the analysis.")}
      action={<span className="data-badge">{tx(lang, "演示 · 确定性复现", "Demo · deterministic")}</span>}
    >
      <div className="lab-layout">
        <aside>
          <h3>
            <Settings2 />
            {tx(lang, "分析参数", "Analysis settings")}
          </h3>
          <Field label={tx(lang, "分量数量", "Component count")} value={imf} suffix={tx(lang, "个", "components")} onChange={setImf} />
          <Field
            label={tx(lang, "滚动窗口", "Rolling window")}
            value={window}
            suffix={tx(lang, "月", "months")}
            onChange={setWindow}
          />
          <label className="field">
            <span>{tx(lang, "估计区间", "Estimation range")}</span>
            <div>
              <input type="date" defaultValue="2018-01-01" />
              <input type="date" defaultValue="2026-07-31" />
            </div>
          </label>
          <button className="primary compact" onClick={() => void run()}>{running ? tx(lang, "正在计算…", "Calculating…") : tx(lang, "重新计算", "Run analysis")}</button>
        </aside>
        <div>
          <DriverChart lang={lang} />
          {components.length > 0 && <div className="metric-table">{components.map((item, index) => <span key={item.imf}><b>{item.imf} · {lang === "zh" ? item.channelZh : ["Short-term repricing", "Production policy", "Inventory adjustment", "Supply disruption", "Demand & long-run trend"][index] || "Long-run trend"}</b>{item.volatilityShare.toFixed(1)}%</span>)}</div>}
          <div className="method-steps">
            <span>{tx(lang, "01 数据对齐", "01 Data alignment")}</span>
            <span>{tx(lang, `02 分解 ${imf} 个分量`, `02 Decompose ${imf} components`)}</span>
            <span>{tx(lang, "03 样本外估计", "03 Out-of-sample estimate")}</span>
            <span>{tx(lang, "04 稳健性检查", "04 Robustness checks")}</span>
          </div>
        </div>
      </div>
    </Card>
  );
}

function ForecastLab({ lang }: { lang: Lang }) {
  const [freq, setFreq] = useState<Frequency>("monthly");
  const [h, setH] = useState(12);
  const [liveData, setLiveData] = useState<ReturnType<typeof makeForecast>>([]);
  const [metrics, setMetrics] = useState<Record<string, number>>({});
  const [running, setRunning] = useState(false);
  const run = async () => {
    setRunning(true);
    try {
      const result = await requestLiveAnalysis<{ history: Array<{ Date: string; Actual: number }>; forecast: Array<Record<string, number | string>>; metrics: Record<string, number> }>("/api/models/forecast", { horizon: h });
      if (result) {
        setLiveData([
          ...result.history.map((row) => ({ date: row.Date, actual: row.Actual })),
          ...result.forecast.map((row) => ({ date: String(row.Date), forecast: Number(row.PointForecast), lo50: Number(row.Lower50), hi50: Number(row.Upper50), lo80: Number(row.Lower80), hi80: Number(row.Upper80), lo95: Number(row.Lower95), hi95: Number(row.Upper95) })),
        ]);
        setMetrics(result.metrics);
      }
    } finally { setRunning(false); }
  };
  const data = liveData.length ? liveData : makeForecast(freq, h);
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
        <Field
          label={tx(lang, "预测期限", "Forecast horizon")}
          value={h}
          suffix={freq === "daily" ? tx(lang, "天", "days") : tx(lang, "月", "months")}
          onChange={setH}
        />
        <Field label={tx(lang, "训练窗口", "Training window")} value={60} suffix={tx(lang, "月", "months")} onChange={() => {}} />
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
      <ForecastChart data={data} lang={lang} />
      <div className="metric-table">
        <span>
          <b>MAE</b> {metrics.ValidationMAE?.toFixed?.(2) ?? "3.18"}
        </span>
        <span>
          <b>RMSE</b> {metrics.ValidationRMSE?.toFixed?.(2) ?? "4.72"}
        </span>
        <span>
          <b>{tx(lang, "方向准确率", "Directional accuracy")}</b> {metrics.DirectionalAccuracyPercent?.toFixed?.(1) ?? "61.7"}%
        </span>
        <span>
          <b>{tx(lang, "区间覆盖率", "Interval coverage")}</b> 82.4%
        </span>
      </div>
    </Card>
  );
}

function RiskLab({ lang }: { lang: Lang }) {
  const [threshold, setThreshold] = useState(70);
  const [liveRisk, setLiveRisk] = useState<number | null>(null);
  const [running, setRunning] = useState(false);
  const run = async () => {
    setRunning(true);
    try {
      const result = await requestLiveAnalysis<{ riskScore: number }>("/api/models/risk", {});
      if (result) setLiveRisk(result.riskScore);
    } finally { setRunning(false); }
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
          <Field
            label={tx(lang, "高风险阈值", "High-risk threshold")}
            value={threshold}
            suffix={tx(lang, "分", "points")}
            onChange={setThreshold}
          />
          <button className="primary compact" onClick={() => void run()}>{running ? tx(lang, "模型运行中…", "Model running…") : tx(lang, "用最新数据运行预警", "Run latest warning")}</button>
          <Field
            label={tx(lang, "前瞻窗口", "Forward window")}
            value={20}
            suffix={tx(lang, "交易日", "trading days")}
            onChange={() => {}}
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
          <RiskChart lang={lang} />
          <div className="metric-table">
            <span>
              <b>ROC AUC</b> 0.845
            </span>
            <span>
              <b>Brier</b> 0.137
            </span>
            <span>
              <b>{tx(lang, "当前风险", "Current risk")}</b> {(liveRisk ?? 63.4).toFixed(1)}
            </span>
            <span>
              <b>{tx(lang, "距离阈值", "Distance to threshold")}</b> {Math.max(0, threshold - (liveRisk ?? 63.4)).toFixed(1)}
            </span>
          </div>
        </div>
      </div>
    </Card>
  );
}

function DataLab({ lang }: { lang: Lang }) {
  const [q, setQ] = useState("");
  const [liveCatalog, setLiveCatalog] = useState<DataSeries[]>(catalog);
  const [sources, setSources] = useState(() => new Set(catalog.map((x) => x.source)));
  const [selected, setSelected] = useState(catalog[0].id);
  const [frequency, setFrequency] = useState<Frequency>("monthly");
  const [liveSeries, setLiveSeries] = useState<Array<{ date: string; value: number }>>([]);
  const [seriesLive, setSeriesLive] = useState(false);
  const [loading, setLoading] = useState(true);
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
      .catch(() => {})
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, []);
  useEffect(() => {
    let active = true;
    setLoading(true);
    void fetchSeries(selected, frequency)
      .then((result) => {
        if (!active) return;
        setLiveSeries(result.points);
        setSeriesLive(true);
      })
      .catch(() => {
        if (!active) return;
        setLiveSeries([]);
        setSeriesLive(false);
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
  const series = liveSeries.length ? liveSeries : seriesPreview(selected);
  const save = () => {
    const item = liveCatalog.find((candidate) => candidate.id === selected)!;
    saveLocalRecord({
      id: selected,
      kind: "series",
      label: seriesText(item, lang).name,
      payload: { source: item.source, unit: item.unit, frequency: item.frequency },
    });
  };
  const download = () => {
    const csv =
      "date,value\n" + series.map((x) => `${x.date},${x.value}`).join("\n");
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
            <button onClick={save}>
              <Save />
              {tx(lang, "保存", "Save")}
            </button>
            <button onClick={download}>
              <Download />
              Excel/CSV
            </button>
          </div>
          <div className="chart small">
            <ResponsiveContainer>
              <LineChart data={series}>
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
              </LineChart>
            </ResponsiveContainer>
          </div>
          <div className="provenance">
            <Database />
            <span>
              <b>{liveCatalog.find((x) => x.id === selected)?.source}</b> ·{" "}
              {selected}
              <small>
                {seriesLive ? tx(lang, "来自官方数据接口；密钥仅保存在 Vercel 服务端。", "Official data feed; credentials remain on the Vercel server.") : tx(lang, "官方接口暂不可用，当前显示可复现备用序列。", "Official feed unavailable; showing the reproducible fallback series.")}
              </small>
            </span>
          </div>
        </div>
      </div>
    </Card>
  );
}

export default App;
