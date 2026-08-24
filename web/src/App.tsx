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
  Upload,
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
import { checkApiHealth, fetchCatalog, fetchInstruments, fetchSeries, readLocalRecords, requestLiveAnalysis, saveLocalRecord } from "./storage";

type Lang = "zh" | "en";
type Mode = "landing" | "decision" | "professional" | "data";
type ProTab = "impact" | "forecast" | "risk";
const tx = (lang: Lang, zh: string, en: string) => (lang === "zh" ? zh : en);

type DriverResult = { id: string; nameZh: string; nameEn: string; impact: number; coefficient: number };
type ComponentResult = { imf: string; channelZh: string; channelEn: string; centerFrequency: number; volatilityShare: number; points: Array<{ date: string; value: number }> };
type GrangerResult = { id: string; nameZh: string; nameEn: string; lag: number; fStatistic: number; pValue: number; significant: boolean };
type ScaleGrangerResult = GrangerResult & { imf: string };
type NetImpactResult = { mode: string; method: string; asOf: string; observations: number; estimationWindow:{start:string;end:string}; eventWindow:{start:string;end:string}; rSquared: number; drivers: DriverResult[]; granger: GrangerResult[]; scaleGranger: ScaleGrangerResult[]; selectedScaleGranger?: ScaleGrangerResult[]; selectedScales: Array<{id:string;nameZh:string;nameEn:string;imf:string;pValue:number}>; components: ComponentResult[]; hht:Array<{date:string;frequency:number;period:number}>; scaleEffect:{selectedScale:string;minimumDate:string;minimumValue:number;maximumDate:string;maximumValue:number;tradingDayInterval:number;calendarDayInterval:number;netEffect:number;originalResponse:number;shareInOriginalResponse:number}; fevd: Array<{id:string;nameZh:string;nameEn:string;share:number;externalWeight:number;absoluteImpact:number}>; fevdOwnShare:number; fevdHorizon:number; varLag:number; rolling: Array<{ date: string; observed: number; fitted: number }>; rollingFevd:Array<{date:string;externalShare:number;ownShare:number;lag:number}>; breakTest:{fixed:{breakDate:string;fStatistic:number;pValue:number;preSlope:number;postSlope:number;slopeChange:number;levelShift:number;significant:boolean};optimal:{candidateCount:number;bestDate:string;rssImprovementPercent:number;profile:Array<{date:string;rss:number;improvementPercent:number}>}}; sources: Array<{ id: string; providerId: string; nameZh: string; nameEn: string }> };
type RiskResult = { mode: string; method: string; latestDate: string; riskScore: number; alertThreshold: number; alert: boolean; history: Array<{ date: string; score: number }> };
type ForecastResult = { mode: string; method: string; asOf: string; latestPrice: number; history: Array<{ Date: string; Actual: number }>; forecast: Array<Record<string, number | string>>; metrics: Record<string, number>; components: Array<{ imf: string; channelZh: string; channelEn: string; centerFrequency: number; latestForecast: number }> };
type InstrumentProduct = { id:string; benchmark:string; exchange:string; kind:"future"|"option"; code:string; name:string; nameZh?:string; size:number; priceScale?:number; contractUnit?:string; currency?:string; settlement:string; source?:string; role?:string; url:string; contracts:number|null; coveredBarrels:number|null; roundingError:number|null; verification:string; quote?:{last:number;bid:number|null;ask:number|null;time:string;date:string;name:string;provider:string}|null };
type InstrumentResponse = { asOf:string; benchmark:string; products:InstrumentProduct[]; quoteWarning?:string|null; quoteMethod?:string; broker:{connected:boolean;name:string;message:string}; executionEnabled:boolean; disclaimer:string };

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
  "GPRD": "Geopolitical Risk Index (traditional daily GPR)",
  "WB-GDP": "World economic growth",
  "IMF-CPI": "Global inflation indicator",
  "OECD-CLI": "OECD composite leading indicator",
};

const representativeDecisionFactors = [
  "GPRD", "FRED-USEPUINDXD",
  "FRED-PETINV", "FRED-HENRYHUB",
  "FRED-DTWEXBGS", "FRED-DGS10", "FRED-STLFSI4",
  "FRED-VIXCLS", "FRED-SP500", "FRED-NASDAQXAU",
  "FRED-CPIAUCSL", "FRED-INDPRO",
];

const seriesText = (item: DataSeries, lang: Lang) => ({
  name: lang === "en" ? item.nameEn || seriesNamesEn[item.id] || item.name : item.name,
  frequency: lang === "en" ? ({ 日度: "Daily", 周度: "Weekly", 月度: "Monthly", 年度: "Annual" }[item.frequency] || item.frequency) : item.frequency,
  unit: lang === "en" ? ({
    "美元/桶": "USD/bbl",
    "美元/MMBtu": "USD/MMBtu",
    "美元/加仑": "USD/gal",
    "百万元": "USD millions",
    千桶: "thousand bbl",
    千人: "thousand persons",
    指数: "index",
    年度: "annual",
    "参见序列元数据": "See series metadata",
  }[item.unit] || item.unit) : item.unit,
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
    risk: "未来风险分位",
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
    risk: "Forward risk percentile",
    hedge: "Procurement & hedge plan",
    advice: "Recommended actions",
    source: "Data workspace",
    brandTag: "Research & decision system",
  },
} as const;

function routeFromPath(): Mode {
  if (location.pathname.startsWith("/data")) return "data";
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
            <button className={mode === "data" ? "active" : ""} onClick={() => navigate("data")}>
              {t.source}
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
            <button onClick={() => navigate("data")}>{t.source}</button>
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
              onData={() => navigate("data")}
            />
          )}
          {mode === "decision" && <Decision lang={lang} t={t} />}
          {mode === "professional" && <Professional lang={lang} t={t} />}
          {mode === "data" && <DataCenter lang={lang} />}
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
  onData,
}: {
  lang: Lang;
  t: typeof copy.zh | typeof copy.en;
  onDecision: () => void;
  onProfessional: () => void;
  onData: () => void;
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
          <button className="text-action" onClick={onData}>
            {t.source}
            <Database size={16} />
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
          <strong>{quotes.brent == null ? "—" : `$${quotes.brent.toFixed(3)}`}</strong>
          <em>{quotes.brentMove == null ? tx(lang,"等待官方数据","Awaiting official data") : `${quotes.brentMove >= 0 ? "+" : ""}${quotes.brentMove.toFixed(3)}%`}</em>
        </div>
        <div className="metric-float mf-two">
          <small>WTI</small>
          <strong>{quotes.wti == null ? "—" : `$${quotes.wti.toFixed(3)}`}</strong>
          <em>{quotes.wtiMove == null ? tx(lang,"等待官方数据","Awaiting official data") : `${quotes.wtiMove >= 0 ? "+" : ""}${quotes.wtiMove.toFixed(3)}%`}</em>
        </div>
        <div className="metric-float mf-three">
          <small>MARKET RISK</small>
          <strong>{riskScore == null ? "—" : riskScore.toFixed(3)}</strong>
          <em>{riskScore == null ? tx(lang,"等待模型","Awaiting model") : riskScore >= 60 ? tx(lang, "中高", "Elevated") : tx(lang, "较低", "Low")}</em>
        </div>
        <div className="pulse-line">
          <span>{quotes.updated ? tx(lang, `官方数据更新至 ${quotes.updated}`, `Official data updated ${quotes.updated}`) : tx(lang, "正在同步官方市场数据；此处不显示替代曲线", "Syncing official market data; no substitute curve is displayed")}</span>
          <div className="source-seal"><Database/><b>FRED · EIA · GPRD</b><small>{tx(lang,"可追溯官方序列","Traceable official series")}</small></div>
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
  const today = new Date().toISOString().slice(0,10);
  const defaultHedgeEnd = new Date(Date.now()+90*86400000).toISOString().slice(0,10);
  const savedDecisionDefaults = useMemo(
    () => readLocalRecords().find((record) => record.kind === "preference" && record.id === "decision-defaults"),
    [],
  );
  const defaultSettings = { target:"EIA-BRENT", horizon:30, training:60, imf:5, window:120, maxLag:5, alpha:.1, estimationStart:"2018-11-07", eventStart:"2020-01-01", eventEnd:today, hedgeStart:today, hedgeEnd:defaultHedgeEnd };
  const storedSettings = savedDecisionDefaults?.payload.settings && typeof savedDecisionDefaults.payload.settings === "object"
    ? savedDecisionDefaults.payload.settings as Partial<typeof defaultSettings>
    : {};
  const initialEventEndMode = savedDecisionDefaults?.payload.eventEndMode === "fixed" ? "fixed" : "latest";
  const [frequency, setFrequency] = useState<Frequency>("daily");
  const [settings, setSettings] = useState({ ...defaultSettings, ...storedSettings, eventEnd:initialEventEndMode === "latest" ? today : String(storedSettings.eventEnd || today) });
  const [eventEndMode, setEventEndMode] = useState<"latest"|"fixed">(initialEventEndMode);
  const [defaultNotice, setDefaultNotice] = useState("");
  const [available, setAvailable] = useState<DataSeries[]>([]);
  const [factors, setFactors] = useState<Set<string>>(new Set());
  const [advanced, setAdvanced] = useState(false);
  const [runVersion, setRunVersion] = useState(0);
  const [forecast, setForecast] = useState<PriceRow[]>([]);
  const [forecastResult, setForecastResult] = useState<ForecastResult | null>(null);
  const [impact, setImpact] = useState<NetImpactResult | null>(null);
  const [risk, setRisk] = useState<RiskResult | null>(null);
  const [instruments, setInstruments] = useState<InstrumentResponse | null>(null);
  const [wti, setWti] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  useEffect(()=>{ void fetchCatalog().then((items)=>{const base=items as unknown as DataSeries[];const saved=readLocalRecords().filter((r)=>r.kind==="series").map((record)=>({id:record.id,name:String(record.payload.name||record.label),nameEn:String(record.payload.nameEn||record.label),category:String(record.payload.category||"Saved variable"),source:String(record.payload.source||"Saved variable"),unit:String(record.payload.unit||""),frequency:String(record.payload.frequency||""),updated:record.savedAt.slice(0,10),color:String(record.payload.color||"#587a9a")}));const rows=[...saved,...base.filter((item)=>!saved.some((row)=>row.id===item.id))];setAvailable(rows);const storedFactors=Array.isArray(savedDecisionDefaults?.payload.factorIds)?savedDecisionDefaults.payload.factorIds.map(String):null;const validIds=new Set(rows.map((item)=>item.id));setFactors(new Set((storedFactors||representativeDecisionFactors).filter((id)=>validIds.has(id)&&id!==settings.target)));}).catch(()=>{});},[]);
  useEffect(() => {
    let active = true; setLoading(true); setError("");
    const records=readLocalRecords().filter((record)=>record.kind==="series"&&factors.has(record.id)&&Array.isArray(record.payload.points));
    const customSeries=records.map((record)=>({id:record.id,nameZh:String(record.payload.name||record.label),nameEn:String(record.payload.nameEn||record.label),points:record.payload.points}));
    const benchmark=settings.target.includes("WTI")?"WTI":"Brent";
    void Promise.all([
      requestLiveAnalysis<ForecastResult>("/api/models/forecast", { target:settings.target,horizon:frequency==="daily"?settings.horizon:Math.max(3,Math.round(settings.horizon/2)),frequency,training:settings.training,imf:settings.imf }),
      requestLiveAnalysis<NetImpactResult>("/api/models/net-impact", { target:settings.target,imf:settings.imf,window:settings.window,maxLag:settings.maxLag,alpha:settings.alpha,estimationStart:settings.estimationStart,eventStart:settings.eventStart,eventEnd:settings.eventEnd,factors:[...factors],customSeries }),
      requestLiveAnalysis<RiskResult>("/api/models/risk", { target:settings.target }),
      fetchSeries("FRED-DCOILWTICO", frequency),
      fetchInstruments({ benchmark,volume:300000,coverage:60,futuresShare:70,includeCrossAsset:1,directory:1 }) as Promise<InstrumentResponse>,
    ]).then(([forecastPayload, impactPayload, riskPayload, wtiPayload, instrumentPayload]) => {
      if (!active || !forecastPayload || !impactPayload || !riskPayload) return;
      setForecastResult(forecastPayload); setImpact(impactPayload); setRisk(riskPayload); setInstruments(instrumentPayload);
      if (eventEndMode === "latest" && impactPayload.asOf) setSettings((current)=>current.eventEnd === impactPayload.asOf ? current : {...current,eventEnd:impactPayload.asOf});
      setForecast([...forecastPayload.history.map((row)=>({date:row.Date,actual:row.Actual})),...forecastPayload.forecast.map((row)=>({date:String(row.Date),forecast:Number(row.PointForecast),lo50:Number(row.Lower50),hi50:Number(row.Upper50),lo80:Number(row.Lower80),hi80:Number(row.Upper80),lo95:Number(row.Lower95),hi95:Number(row.Upper95)}))]);
      setWti(wtiPayload.points.at(-1)?.value??null);
    }).catch((reason)=>{if(active)setError(reason instanceof Error?reason.message:String(reason));}).finally(()=>{if(active)setLoading(false);});
    return()=>{active=false;};
  }, [frequency, runVersion]);
  if (loading) return <div className="page"><StatusPanel text={tx(lang, "正在从官方来源更新数据并运行模型…", "Updating official data and running verified models…")} /></div>;
  if (error || !forecastResult || !impact || !risk) return <div className="page"><StatusPanel error text={tx(lang, `无法生成可靠结果：${error}`, `Verified results are unavailable: ${error}`)} /></div>;
  const latest = forecastResult.latestPrice;
  const median = forecastResult.forecast.at(-1)?.PointForecast as number;
  const low = Math.min(...forecastResult.forecast.map((r) => Number(r.Lower95)));
  const high = Math.max(...forecastResult.forecast.map((r) => Number(r.Upper95)));
  const suggestedRatio = Math.round(Math.min(85, Math.max(35, 35 + risk.riskScore * .45)));
  const saveDecisionDefaults = () => {
    saveLocalRecord({
      id:"decision-defaults",
      kind:"preference",
      label:"Decision mode defaults",
      payload:{ settings, factorIds:[...factors], eventEndMode },
    });
    setDefaultNotice(tx(lang,"已保存为决策模式默认设置","Saved as Decision mode defaults"));
  };
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
          value={`$${latest.toFixed(3)}`}
          delta={tx(lang, "官方现货序列", "Official spot series")}
        />
        <Kpi label="WTI" value={wti == null ? tx(lang, "同步中", "Syncing") : `$${wti.toFixed(3)}`} delta={tx(lang, "美国原油现货", "US crude spot")}/>
        <Kpi label={tx(lang, "预测期末中位路径", "End-of-horizon median")} value={`$${Number(median).toFixed(3)}`} delta={`${((Number(median) / latest - 1) * 100).toFixed(3)}%`} />
        <Kpi label={tx(lang, "95%决策区间", "95% decision range")} value={`$${low.toFixed(3)}—${high.toFixed(3)}`} compact />
        <Kpi
          label={tx(lang, "历史风险分位", "Historical risk percentile")}
          value={risk.riskScore.toFixed(3)}
          delta={risk.alert ? tx(lang, `高于约 ${risk.riskScore.toFixed(3)}% 的历史观察值，已超过复核阈值`, `Above roughly ${risk.riskScore.toFixed(3)}% of historical observations and above the review threshold`) : tx(lang, `高于约 ${risk.riskScore.toFixed(3)}% 的历史观察值，尚未超过复核阈值`, `Above roughly ${risk.riskScore.toFixed(3)}% of historical observations and below the review threshold`)}
          tone={risk.alert?"warm":"calm"}
        />
      </div>
      <div className="story-rail">
        <span>{tx(lang, "01 市场状态", "01 Market state")}</span>
        <span>{tx(lang, "02 影响因素", "02 Drivers")}</span>
        <span>{tx(lang, "03 价格路径", "03 Price path")}</span>
        <span>{tx(lang, "04 风险预警", "04 Risk alert")}</span>
        <span>{tx(lang, "05 行动方案", "05 Action plan")}</span>
      </div>
      <Card title={tx(lang,"高级设置","Advanced settings")} desc={tx(lang,"调整时间范围、模型窗口和参与计算的变量；在数据中心加入变量池的新序列会自动出现在这里。","Adjust time ranges, model windows and variables. Series added to the variable pool in Data workspace appear here automatically.")} action={<button className="soft-button" onClick={()=>setAdvanced((value)=>!value)}><Settings2/>{advanced?tx(lang,"收起","Collapse"):tx(lang,"展开","Open")}</button>}>
        {advanced&&<div className="decision-settings">
          <div className="inline-fields">
            <label className="field"><span>{tx(lang,"目标油价","Target price")}</span><div><select value={settings.target} onChange={(e)=>setSettings((s)=>({...s,target:e.target.value}))}><option value="EIA-BRENT">Brent</option><option value="FRED-DCOILWTICO">WTI</option></select></div></label>
            <Field label={tx(lang,"预测长度","Forecast horizon")} value={settings.horizon} suffix={tx(lang,"期","periods")} min={5} max={120} onChange={(horizon)=>setSettings((s)=>({...s,horizon}))}/>
            <Field label={tx(lang,"训练窗口","Training window")} value={settings.training} suffix={tx(lang,"月","months")} min={24} max={180} onChange={(training)=>setSettings((s)=>({...s,training}))}/>
            <Field label={tx(lang,"分量数量","Components")} value={settings.imf} suffix="IMF" min={3} max={8} onChange={(imf)=>setSettings((s)=>({...s,imf}))}/>
            <Field label={tx(lang,"滚动窗口","Rolling window")} value={settings.window} suffix={tx(lang,"交易日","days")} min={48} max={500} onChange={(window)=>setSettings((s)=>({...s,window}))}/>
            <Field label={tx(lang,"最大滞后","Maximum lag")} value={settings.maxLag} suffix={tx(lang,"阶","lags")} min={1} max={6} onChange={(maxLag)=>setSettings((s)=>({...s,maxLag}))}/>
            <Field label={tx(lang,"显著性阈值","Significance level")} value={settings.alpha} suffix="α" step={.01} min={.01} max={.2} onChange={(alpha)=>setSettings((s)=>({...s,alpha:Number(alpha.toFixed(2))}))}/>
          </div>
          <div className="event-end-policy">
            <div><b>{tx(lang,"默认事件结束日","Default event end")}</b><small>{eventEndMode==="latest"?tx(lang,"每次打开时自动使用最新可用数据日","Always advances to the latest available observation"):tx(lang,"固定使用下方选择的日期","Keeps the user-selected date below")}</small></div>
            <Segment value={eventEndMode} onChange={(mode)=>{setEventEndMode(mode);if(mode==="latest")setSettings((current)=>({...current,eventEnd:today}));}} options={[{v:"latest",l:tx(lang,"最新可用日期","Latest available")},{v:"fixed",l:tx(lang,"用户选择日期","Selected date")}]} />
          </div>
          <div className="inline-fields">
            <DateField lang={lang} label={tx(lang,"估计期开始","Estimation start")} value={settings.estimationStart} onChange={(estimationStart)=>setSettings((s)=>({...s,estimationStart}))}/>
            <DateField lang={lang} label={tx(lang,"事件期开始","Event start")} value={settings.eventStart} onChange={(eventStart)=>setSettings((s)=>({...s,eventStart}))}/>
            <DateField lang={lang} label={tx(lang,"事件期结束","Event end")} value={settings.eventEnd} onChange={(eventEnd)=>{setEventEndMode("fixed");setSettings((s)=>({...s,eventEnd}));}}/>
            <DateField lang={lang} label={tx(lang,"套保需求开始","Hedge need starts")} value={settings.hedgeStart} onChange={(hedgeStart)=>setSettings((s)=>({...s,hedgeStart}))}/>
            <DateField lang={lang} label={tx(lang,"套保需求结束","Hedge need ends")} value={settings.hedgeEnd} onChange={(hedgeEnd)=>setSettings((s)=>({...s,hedgeEnd}))}/>
          </div>
          <div className="factor-head"><b>{tx(lang,`考虑变量（${factors.size}）`,`Included variables (${factors.size})`)}</b><div><button onClick={()=>setFactors(new Set(available.filter((item)=>item.id!==settings.target).map((item)=>item.id)))}>{tx(lang,"全选","Select all")}</button><button onClick={()=>setFactors(new Set())}>{tx(lang,"清空","Clear")}</button></div></div>
          <div className="factor-grid compact-factors">{available.filter((item)=>item.id!==settings.target).map((item)=><label key={item.id} className={factors.has(item.id)?"active":""}><input type="checkbox" checked={factors.has(item.id)} onChange={()=>setFactors((current)=>{const next=new Set(current);next.has(item.id)?next.delete(item.id):next.add(item.id);return next;})}/><span><b>{seriesText(item,lang).name}</b><small>{item.source} · {item.id}</small></span></label>)}</div>
          <div className="decision-default-actions">
            <button className="soft-button" onClick={saveDecisionDefaults}><Save/>{tx(lang,"保存并设为默认","Save as defaults")}</button>
            <button className="primary compact" onClick={()=>setRunVersion((value)=>value+1)}>{tx(lang,"按以上设置重新计算","Rerun with these settings")}</button>
            {defaultNotice&&<span role="status">{defaultNotice}</span>}
          </div>
        </div>}
      </Card>
      <Card
        title={t.drivers}
        desc={tx(lang, "净影响表示该因素与当前油价变动的方向和估计幅度，不代表单一因果关系。", "Net impact estimates direction and magnitude; it does not claim a single causal relationship.")}
        action={<span className="data-badge">{tx(lang, `计算至 ${impact.asOf}`, `Calculated through ${impact.asOf}`)}</span>}
      >
        <DriverChart lang={lang} data={impact.drivers} />
        <DecisionGrangerSummary lang={lang} granger={impact.selectedScaleGranger ?? impact.scaleGranger.filter((row)=>row.imf===impact.scaleEffect.selectedScale)} drivers={impact.drivers} alpha={settings.alpha} selectedScale={impact.scaleEffect.selectedScale}/>
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
              <b>{tx(lang, `当前历史风险分位：${risk.riskScore.toFixed(3)}`, `Current historical risk percentile: ${risk.riskScore.toFixed(3)}`)}</b>
              <p>
                {tx(lang, `复核阈值为 ${risk.alertThreshold.toFixed(3)}；该指标用于排序和触发复核，并非危机发生概率。`, `The review threshold is ${risk.alertThreshold.toFixed(3)}. This is a ranking signal, not a crisis probability.`)}
              </p>
            </div>
          </div>
        </Card>
        <ScaleCard lang={lang} components={impact.components} />
      </div>
      <HedgeCalculator lang={lang} market={latest} suggestedRatio={suggestedRatio} forecast={forecastResult} instruments={instruments} drivers={impact.drivers} hedgeStart={settings.hedgeStart} hedgeEnd={settings.hedgeEnd} onHedgeWindowChange={(key,value)=>setSettings((current)=>({...current,[key]:value}))}/>
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
            text={tx(lang, `风险分位超过 ${risk.alertThreshold.toFixed(3)} 或价格超出95%区间时立即复核，不使用固定人为阈值。`, `Review immediately if risk exceeds ${risk.alertThreshold.toFixed(3)} or price leaves the 95% interval; no arbitrary fixed trigger is used.`)}
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
  compact,
}: {
  label: string;
  value: string;
  delta?: string;
  tone?: string;
  compact?: boolean;
}) {
  return (
    <div className={`kpi ${tone || ""} ${compact?"compact-value":""}`}>
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
          <Tooltip formatter={(v) => [tx(lang, `${Number(v).toFixed(3)} 美元/桶`, `$${Number(v).toFixed(3)}/bbl`), tx(lang, "估计净影响", "Estimated net impact")]} />
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
  const cutoffIndex = data.map((r) => r.actual != null).lastIndexOf(true);
  const rows = data.map((r, index) => ({
    ...r,
    forecast: index === cutoffIndex && r.actual != null ? r.actual : r.forecast,
    lo95: index === cutoffIndex && r.actual != null ? r.actual : r.lo95,
    hi95: index === cutoffIndex && r.actual != null ? r.actual : r.hi95,
    lo80: index === cutoffIndex && r.actual != null ? r.actual : r.lo80,
    hi80: index === cutoffIndex && r.actual != null ? r.actual : r.hi80,
    lo50: index === cutoffIndex && r.actual != null ? r.actual : r.lo50,
    hi50: index === cutoffIndex && r.actual != null ? r.actual : r.hi50,
  })).map((r) => ({
    ...r,
    band95: r.lo95 == null ? undefined : [r.lo95, r.hi95],
    band80: r.lo80 == null ? undefined : [r.lo80, r.hi80],
    band50: r.lo50 == null ? undefined : [r.lo50, r.hi50],
  }));
  const cutoff = data.filter((r) => r.actual != null).at(-1)?.date;
  const scalarValues = rows.flatMap((row) => [row.actual,row.forecast,row.lo50,row.hi50,row.lo80,row.hi80,row.lo95,row.hi95]).filter((value): value is number => Number.isFinite(value));
  const minimum = Math.min(...scalarValues); const maximum = Math.max(...scalarValues); const padding = Math.max((maximum-minimum)*.06, 1);
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
            domain={[minimum-padding, maximum+padding]}
            tick={{ fontSize: 11 }}
            tickFormatter={(value) => `$${Number(value).toFixed(3)}`}
          />
          <Tooltip formatter={(value)=>Array.isArray(value) ? value.map((item)=>Number(item).toFixed(3)).join(" — ") : Number(value).toFixed(3)} />
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
          <Tooltip formatter={(value)=>Number(value).toFixed(3)} />
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
      <div className="scale-legend">{components.map((component, index) => <span key={component.imf}><i style={{background:["#c47d59","#587a9a","#756fa5","#4f8b7d","#b49958","#8b6e78","#527f91","#9a7454"][index]}} />{component.imf} · {(lang === "zh" ? component.channelZh : component.channelEn)} · {component.volatilityShare.toFixed(3)}%</span>)}</div>
      <ChartFrame label={tx(lang, "缩放并左右浏览分量", "Zoom and scroll through components")}><div className="chart small">
        <ResponsiveContainer>
          <LineChart data={rows}>
            <CartesianGrid vertical={false} stroke="#e6e0dc" />
            <XAxis dataKey="date" minTickGap={35} tick={{fontSize:10}} />
            <YAxis tick={{ fontSize: 10 }} />
            <Tooltip formatter={(value)=>Number(value).toFixed(3)} />
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
  entry: number;
  ratio: number;
  futures: number;
  purchaseBasis: number;
  budgetBasis: number;
  fx: number;
  budgetFx: number;
  margin: number;
  finance: number;
  contract: number;
  fee: number;
  crossFeeBps: number;
  premium: number;
  strike: number;
  strikeGap: number;
  horizon: number;
};
function HedgeCalculator({ lang, market, suggestedRatio, forecast, instruments, drivers, hedgeStart, hedgeEnd, onHedgeWindowChange }: { lang: Lang; market: number; suggestedRatio: number; forecast: ForecastResult; instruments: InstrumentResponse | null; drivers: DriverResult[]; hedgeStart:string; hedgeEnd:string; onHedgeWindowChange:(key:"hedgeStart"|"hedgeEnd",value:string)=>void }) {
  const terminalForecast=forecast.forecast.at(-1);
  const forecastImpliedAtmPremium=Math.max(.001,(Number(terminalForecast?.Upper95??market)-Number(terminalForecast?.Lower95??market))/(2*1.96)*.3989423);
  const validStart=/^\d{4}-\d{2}-\d{2}$/.test(hedgeStart)?new Date(`${hedgeStart}T00:00:00Z`):new Date();
  const parsedEnd=/^\d{4}-\d{2}-\d{2}$/.test(hedgeEnd)?new Date(`${hedgeEnd}T00:00:00Z`):new Date(validStart.getTime()+90*86400000);
  const hedgeRangeValid=parsedEnd.getTime()>=validStart.getTime();
  const validEnd=hedgeRangeValid?parsedEnd:new Date(validStart.getTime()+86400000);
  const hedgeWindowDays=Math.max(1,Math.ceil((validEnd.getTime()-validStart.getTime())/86400000));
  const [v, setV] = useState<Hedge>({
    volume: 300000,
    budget: market,
    entry: instruments?.products.find((product)=>product.kind==="future")?.quote?.ask || market,
    ratio: suggestedRatio,
    futures: 70,
    purchaseBasis: 1.2,
    budgetBasis: 1.2,
    fx: 7.18,
    budgetFx: 7.18,
    margin: 12,
    finance: 3.4,
    contract: 1000,
    fee: 0.035,
    crossFeeBps: 1.5,
    premium: forecastImpliedAtmPremium,
    strike: market * 1.03,
    strikeGap: Math.max(2, market * 0.05),
    horizon: hedgeWindowDays,
  });
  const [openPlans,setOpenPlans]=useState<Set<string>>(()=>new Set());
  useEffect(()=>setV((current)=>current.horizon===hedgeWindowDays?current:{...current,horizon:hedgeWindowDays}),[hedgeWindowDays]);
  const set = (k: keyof Hedge, n: number) => setV((s) => ({ ...s, [k]: n }));
  const endings=forecast.forecast; const pick=(key:string,fallback:number)=>Number(endings.at(-1)?.[key]??fallback);
  const scenarioPrices=[{scenario:tx(lang,"95%下界","95% lower"),price:pick("Lower95",market*.8)},{scenario:tx(lang,"80%下界","80% lower"),price:pick("Lower80",market*.9)},{scenario:tx(lang,"中位路径","Median path"),price:pick("PointForecast",market)},{scenario:tx(lang,"80%上界","80% upper"),price:pick("Upper80",market*1.1)},{scenario:tx(lang,"95%上界","95% upper"),price:pick("Upper95",market*1.2)}];
  const calculate=(price:number,coverage=v.ratio,futuresShare=v.futures)=>{const protectedBarrels=v.volume*coverage/100;const targetFutures=protectedBarrels*futuresShare/100;const contracts=Math.round(targetFutures/Math.max(v.contract,1));const futuresBarrels=contracts*v.contract;const optionBarrels=Math.max(0,protectedBarrels-futuresBarrels);const physical=v.volume*(price+v.purchaseBasis)*v.fx;const futuresPnl=futuresBarrels*(price-v.entry)*v.fx;const optionPnl=optionBarrels*Math.max(price-v.strike,0)*v.fx;const premium=optionBarrels*v.premium*v.budgetFx;const marginReq=futuresBarrels*v.entry*v.budgetFx*v.margin/100;const funding=marginReq*v.finance/100*v.horizon/365;const fees=(futuresBarrels+optionBarrels)*v.fee*v.budgetFx*2;const hedged=physical-futuresPnl-optionPnl+premium+funding+fees;return{physical,hedged,saving:physical-hedged,marginReq,funding,fees,futuresBarrels,optionBarrels,contracts};};
  const scenarioRows=scenarioPrices.map((row)=>{const result=calculate(row.price);return{...row,...result,unhedged:result.physical};});
  const base=scenarioRows[2]; const budget=v.volume*(v.budget+v.budgetBasis)*v.budgetFx; const delta=base.physical-base.hedged;
  type ExpiryKey="near"|"target"|"deferred";
  type LegTemplate={id:string;kind:"future"|"option";side:1|-1;weight:number;expiry:ExpiryKey;right?:"call"|"put";strikeOffset?:number;purposeZh:string;purposeEn:string;futureVenue?:"delivery"|"financial"};
  const planDefinitions:Array<{id:string;name:string;structure:string;desc:string;coverage:number;educationUrl:string;legs:LegTemplate[]}>= [
    {id:"ladder",name:tx(lang,"三期限期货阶梯","Three-expiry futures ladder"),structure:"40% / 35% / 25%",desc:tx(lang,"把覆盖量分散到近月、采购目标月和递延月，降低一次换月和单一到期日的集中风险。","Distributes the hedge across near, target and deferred expiries to reduce roll and expiry concentration."),coverage:Math.min(90,v.ratio+10),educationUrl:"https://www.cmegroup.com/education/courses/understanding-futures-spreads/futures-spread-overview",legs:[
      {id:"near-future",kind:"future",side:1,weight:.40,expiry:"near",purposeZh:"近月先锁定首批采购",purposeEn:"Lock the first procurement tranche",futureVenue:"delivery"},
      {id:"target-future",kind:"future",side:1,weight:.35,expiry:"target",purposeZh:"覆盖主要采购月份",purposeEn:"Cover the main procurement month",futureVenue:"delivery"},
      {id:"deferred-future",kind:"future",side:1,weight:.25,expiry:"deferred",purposeZh:"为延期采购保留覆盖",purposeEn:"Carry protection into delayed procurement",futureVenue:"delivery"},
    ]},
    {id:"bull-call",name:tx(lang,"双期限牛市看涨价差","Two-expiry bull call spreads"),structure:"+C(K) / −C(K+Δ)",desc:tx(lang,"在目标月与递延月各建立一组牛市看涨价差，用卖出高执行价看涨期权抵减权利金；保护收益有上限。","Builds a bull call spread in both target and deferred expiries. Short higher-strike calls reduce premium, while upside protection is capped."),coverage:v.ratio,educationUrl:"https://www.cmegroup.com/education/courses/option-strategies/bull-spread",legs:[
      {id:"target-long-call",kind:"option",side:1,weight:.65,expiry:"target",right:"call",strikeOffset:0,purposeZh:"目标月买入较低执行价看涨",purposeEn:"Buy the lower-strike target-month call"},
      {id:"target-short-call",kind:"option",side:-1,weight:.65,expiry:"target",right:"call",strikeOffset:1,purposeZh:"卖出较高执行价看涨抵减成本",purposeEn:"Sell the higher-strike call to reduce cost"},
      {id:"deferred-long-call",kind:"option",side:1,weight:.35,expiry:"deferred",right:"call",strikeOffset:.5,purposeZh:"递延月保留第二层上涨保护",purposeEn:"Add a second layer of deferred protection"},
      {id:"deferred-short-call",kind:"option",side:-1,weight:.35,expiry:"deferred",right:"call",strikeOffset:1.5,purposeZh:"递延月卖出上翼回收权利金",purposeEn:"Sell the deferred upper wing"},
    ]},
    {id:"collar",name:tx(lang,"期货领口组合","Futures collar"),structure:"+F / +P(K−Δ) / −C(K+Δ)",desc:tx(lang,"买入目标月期货，同时买入看跌、卖出看涨，把期货套保的价格结果限制在一个区间；上方收益被封顶。","Combines a long target-month future with a long put and short call, constraining the futures hedge to a price band."),coverage:v.ratio,educationUrl:"https://www.cmegroup.com/education/courses/option-strategies/collars",legs:[
      {id:"collar-future",kind:"future",side:1,weight:1,expiry:"target",purposeZh:"目标月期货锁定采购基准",purposeEn:"Lock the target-month benchmark",futureVenue:"financial"},
      {id:"collar-put",kind:"option",side:1,weight:1,expiry:"target",right:"put",strikeOffset:-1,purposeZh:"买入看跌保护期货下跌损失",purposeEn:"Buy a put to protect the long future"},
      {id:"collar-call",kind:"option",side:-1,weight:1,expiry:"target",right:"call",strikeOffset:1,purposeZh:"卖出看涨补贴看跌权利金",purposeEn:"Sell a call to finance the put"},
    ]},
    {id:"calendar",name:tx(lang,"期权日历价差与期货底仓","Call calendar with futures core"),structure:"−C(近月,K) / +C(递延,K) / +F",desc:tx(lang,"卖出近月看涨、买入同执行价递延月看涨，并配置目标月期货底仓，适合采购风险向后延伸的情形。","Sells a near-month call, buys the same-strike deferred call and keeps a target-month futures core for risk that extends over time."),coverage:Math.max(0,v.ratio-10),educationUrl:"https://www.cmegroup.com/education/lessons/option-calendar-spreads",legs:[
      {id:"calendar-short",kind:"option",side:-1,weight:.65,expiry:"near",right:"call",strikeOffset:0,purposeZh:"卖出近月时间价值",purposeEn:"Sell near-month time value"},
      {id:"calendar-long",kind:"option",side:1,weight:.65,expiry:"deferred",right:"call",strikeOffset:0,purposeZh:"买入递延月上涨保护",purposeEn:"Buy deferred upside protection"},
      {id:"calendar-core",kind:"future",side:1,weight:.35,expiry:"target",purposeZh:"期货底仓覆盖核心采购",purposeEn:"Futures core covers the central procurement tranche",futureVenue:"financial"},
    ]},
    {id:"butterfly",name:tx(lang,"期货底仓与看涨蝶式价差","Futures core plus call butterfly"),structure:"+F(45%) + C(K−Δ) − 2C(K) + C(K+Δ)",desc:tx(lang,"45%期货底仓负责极端上涨保护；其余部分叠加1:−2:1看涨蝶式，针对价格落在中间执行价附近的情景。","A 45% futures core protects the tail, while a 1:-2:1 call butterfly targets a finish near the middle strike."),coverage:Math.max(0,v.ratio-5),educationUrl:"https://www.cmegroup.com/education/courses/option-strategies/option-butterfly",legs:[
      {id:"fly-core",kind:"future",side:1,weight:.45,expiry:"target",purposeZh:"期货底仓保留极端上涨保护",purposeEn:"Futures core retains tail protection",futureVenue:"financial"},
      {id:"fly-low",kind:"option",side:1,weight:.55,expiry:"target",right:"call",strikeOffset:-1,purposeZh:"买入蝶式下翼",purposeEn:"Buy the lower butterfly wing"},
      {id:"fly-body",kind:"option",side:-1,weight:1.10,expiry:"target",right:"call",strikeOffset:0,purposeZh:"卖出两倍中间执行价看涨",purposeEn:"Sell twice the middle-strike call"},
      {id:"fly-high",kind:"option",side:1,weight:.55,expiry:"target",right:"call",strikeOffset:1,purposeZh:"买入蝶式上翼限制风险",purposeEn:"Buy the upper wing to limit risk"},
    ]},
    {id:"seagull",name:tx(lang,"采购方三腿海鸥组合","Buyer three-way seagull"),structure:"+F(25%) + C(K) − C(K+Δ) − P(K−Δ)",desc:tx(lang,"用少量期货作底仓，买入看涨并卖出高执行价看涨与低执行价看跌来降低净权利金；低价区间存在履约义务。","Uses a small futures core, buys a call and sells an upper call plus lower put to reduce net premium; the short put creates a downside obligation."),coverage:Math.max(0,v.ratio-15),educationUrl:"https://www.cmegroup.com/articles/brochures-and-handbooks/25-proven-strategies.html",legs:[
      {id:"seagull-core",kind:"future",side:1,weight:.25,expiry:"near",purposeZh:"近月期货底仓",purposeEn:"Near-month futures core",futureVenue:"financial"},
      {id:"seagull-long-call",kind:"option",side:1,weight:.75,expiry:"target",right:"call",strikeOffset:0,purposeZh:"买入主要上涨保护",purposeEn:"Buy primary upside protection"},
      {id:"seagull-short-call",kind:"option",side:-1,weight:.75,expiry:"target",right:"call",strikeOffset:1,purposeZh:"卖出上方看涨降低权利金",purposeEn:"Sell the upper call to reduce premium"},
      {id:"seagull-short-put",kind:"option",side:-1,weight:.75,expiry:"target",right:"put",strikeOffset:-1,purposeZh:"卖出低执行价看跌承担低价履约义务",purposeEn:"Sell a lower-strike put and accept downside assignment risk"},
    ]},
    {id:"rolling-collar",name:tx(lang,"双期限滚动领口","Two-expiry rolling collar"),structure:"½(+F+P−C)近月 + ½(+F+P−C)目标月",desc:tx(lang,"把期货领口拆成近月与目标月两批执行，分别管理首批采购和主采购窗口，降低单一到期日与集中换月风险。","Splits a futures collar across near and target expiries, separately covering the first and main procurement windows while reducing expiry concentration."),coverage:Math.min(95,v.ratio+5),educationUrl:"https://www.cmegroup.com/education/courses/option-strategies/collars",legs:[
      {id:"roll-near-future",kind:"future",side:1,weight:.50,expiry:"near",purposeZh:"近月期货覆盖首批采购",purposeEn:"Near-month future covers the first tranche",futureVenue:"financial"},
      {id:"roll-near-put",kind:"option",side:1,weight:.50,expiry:"near",right:"put",strikeOffset:-1,purposeZh:"近月看跌限制期货下跌损失",purposeEn:"Near-month put limits downside on the long future"},
      {id:"roll-near-call",kind:"option",side:-1,weight:.50,expiry:"near",right:"call",strikeOffset:1,purposeZh:"近月卖出看涨补贴保护成本",purposeEn:"Near-month short call finances protection"},
      {id:"roll-target-future",kind:"future",side:1,weight:.50,expiry:"target",purposeZh:"目标月期货覆盖主采购窗口",purposeEn:"Target-month future covers the main window",futureVenue:"financial"},
      {id:"roll-target-put",kind:"option",side:1,weight:.50,expiry:"target",right:"put",strikeOffset:-1,purposeZh:"目标月看跌限制期货下跌损失",purposeEn:"Target-month put limits downside on the long future"},
      {id:"roll-target-call",kind:"option",side:-1,weight:.50,expiry:"target",right:"call",strikeOffset:1,purposeZh:"目标月卖出看涨补贴保护成本",purposeEn:"Target-month short call finances protection"},
    ]},
    {id:"condor",name:tx(lang,"期货底仓与看涨鹰式价差","Futures core plus call condor"),structure:"+F(40%) + C(K−2Δ) − C(K−Δ) − C(K+Δ) + C(K+2Δ)",desc:tx(lang,"40%期货底仓负责尾部上涨，其余覆盖叠加1:−1:−1:1看涨鹰式价差，把有效保护区间做得比蝶式更宽，同时保持期权最大损失有限。","A 40% futures core covers the upside tail; a 1:-1:-1:1 call condor widens the targeted protection zone beyond a butterfly while keeping option loss bounded."),coverage:Math.max(55,v.ratio),educationUrl:"https://www.cmegroup.com/articles/brochures-and-handbooks/25-proven-strategies.html",legs:[
      {id:"condor-core",kind:"future",side:1,weight:.40,expiry:"target",purposeZh:"期货底仓承担极端上涨保护",purposeEn:"Futures core covers the extreme upside tail",futureVenue:"financial"},
      {id:"condor-low",kind:"option",side:1,weight:.60,expiry:"target",right:"call",strikeOffset:-2,purposeZh:"买入鹰式最下方看涨",purposeEn:"Buy the lowest-strike condor call"},
      {id:"condor-mid-low",kind:"option",side:-1,weight:.60,expiry:"target",right:"call",strikeOffset:-1,purposeZh:"卖出下方中间执行价看涨",purposeEn:"Sell the lower-middle call"},
      {id:"condor-mid-high",kind:"option",side:-1,weight:.60,expiry:"target",right:"call",strikeOffset:1,purposeZh:"卖出上方中间执行价看涨",purposeEn:"Sell the upper-middle call"},
      {id:"condor-high",kind:"option",side:1,weight:.60,expiry:"target",right:"call",strikeOffset:2,purposeZh:"买入最上方看涨封闭风险",purposeEn:"Buy the highest-strike call to cap risk"},
    ]},
    {id:"diagonal",name:tx(lang,"对角看涨价差与期货底仓","Diagonal call spread with futures core"),structure:"+F(30%) − C(近月,K+Δ) + C(递延,K)",desc:tx(lang,"卖出近月较高执行价看涨、买入递延月较低执行价看涨，并保留30%目标月期货底仓；兼顾期限与执行价两维，但需要持续管理近月短腿。","Sells a higher-strike near call, buys a lower-strike deferred call and retains a 30% target-month futures core; it spans both time and strike dimensions and requires active management of the near short leg."),coverage:Math.max(0,v.ratio-5),educationUrl:"https://www.cmegroup.com/education/lessons/option-calendar-spreads",legs:[
      {id:"diagonal-core",kind:"future",side:1,weight:.30,expiry:"target",purposeZh:"目标月期货底仓提供连续保护",purposeEn:"Target-month futures core provides continuous protection",futureVenue:"financial"},
      {id:"diagonal-short",kind:"option",side:-1,weight:.70,expiry:"near",right:"call",strikeOffset:1,purposeZh:"卖出近月高执行价时间价值",purposeEn:"Sell near-month higher-strike time value"},
      {id:"diagonal-long",kind:"option",side:1,weight:.70,expiry:"deferred",right:"call",strikeOffset:0,purposeZh:"买入递延月较低执行价上涨保护",purposeEn:"Buy deferred lower-strike upside protection"},
    ]},
    {id:"staged-vertical",name:tx(lang,"三批跨期看涨价差","Three-tranche vertical call spreads"),structure:"Σ[+Cₜ(K) − Cₜ(K+Δ)]，t=近月/目标月/递延月",desc:tx(lang,"在近月、目标月和递延月分别建立牛市看涨价差，按30%/45%/25%覆盖采购批次，使权利金、到期日和上涨保护分散。","Builds bull call spreads in near, target and deferred expiries at 30%/45%/25%, distributing premium, expiry and upside protection across procurement tranches."),coverage:v.ratio,educationUrl:"https://www.cmegroup.com/education/courses/option-strategies/bull-spread",legs:[
      {id:"stage-near-long",kind:"option",side:1,weight:.30,expiry:"near",right:"call",strikeOffset:0,purposeZh:"近月买入看涨覆盖首批采购",purposeEn:"Near-month long call covers the first tranche"},
      {id:"stage-near-short",kind:"option",side:-1,weight:.30,expiry:"near",right:"call",strikeOffset:1,purposeZh:"近月卖出上翼抵减权利金",purposeEn:"Near-month short upper wing reduces premium"},
      {id:"stage-target-long",kind:"option",side:1,weight:.45,expiry:"target",right:"call",strikeOffset:0,purposeZh:"目标月买入看涨覆盖主采购",purposeEn:"Target-month long call covers the main tranche"},
      {id:"stage-target-short",kind:"option",side:-1,weight:.45,expiry:"target",right:"call",strikeOffset:1,purposeZh:"目标月卖出上翼抵减权利金",purposeEn:"Target-month short upper wing reduces premium"},
      {id:"stage-deferred-long",kind:"option",side:1,weight:.25,expiry:"deferred",right:"call",strikeOffset:.5,purposeZh:"递延月买入看涨覆盖延期采购",purposeEn:"Deferred long call covers delayed procurement"},
      {id:"stage-deferred-short",kind:"option",side:-1,weight:.25,expiry:"deferred",right:"call",strikeOffset:1.5,purposeZh:"递延月卖出上翼抵减权利金",purposeEn:"Deferred short upper wing reduces premium"},
    ]},
  ];
  const selectedProducts=instruments?.products||[];
  const overlayMap:Record<string,string[]>={
    "FRED-NASDAQXAU":["COMEX-GC","COMEX-SI"],"FRED-GOLDAMGBD228NLBM":["COMEX-GC","COMEX-SI"],
    "FRED-DTWEXBGS":["ICE-DX","COMEX-GC"],"FRED-DEXCHUS":["ICE-DX"],
    "FRED-DGS10":["CME-ZN","CME-ZB"],"FRED-DGS2":["CME-ZT","CME-ZN"],"FRED-T10YIE":["CME-ZN","COMEX-GC"],"FRED-DFF":["CME-ZT","CME-ZN"],
    "FRED-VIXCLS":["CBOE-VX","COMEX-GC"],"FRED-OVXCLS":["CBOE-VX"],"FRED-STLFSI4":["CBOE-VX","CME-ZN","COMEX-GC"],
    "FRED-SP500":["CME-ES","CME-NQ"],"FRED-NASDAQCOM":["CME-NQ","CME-ES"],
    "FRED-HENRYHUB":["NYMEX-NG"],"FRED-DHHNGSP":["NYMEX-NG"],"FRED-PETINV":["NYMEX-NG","NYMEX-RB","NYMEX-HO"],
    "FRED-GASOLINE":["NYMEX-RB"],"FRED-INDPRO":["COMEX-HG","CME-ES"],"FRED-CPIAUCSL":["COMEX-GC","COMEX-SI","CME-ZN"],
    "FRED-UNRATE":["CME-ES","CME-ZN","CBOE-VX"],"FRED-USEPUINDXD":["COMEX-GC","CBOE-VX","CME-ZN"],
    "GPRD":["COMEX-GC","CBOE-VX","ICE-DX"],
  };
  const proxySignMap:Record<string,Record<string,1|-1>>={
    "FRED-DGS10":{"CME-ZN":-1,"CME-ZB":-1},"FRED-DGS2":{"CME-ZT":-1,"CME-ZN":-1},"FRED-DFF":{"CME-ZT":-1,"CME-ZN":-1},
    "FRED-T10YIE":{"CME-ZN":-1,"COMEX-GC":1},"FRED-CPIAUCSL":{"CME-ZN":-1,"COMEX-GC":1,"COMEX-SI":1},
    "FRED-DTWEXBGS":{"ICE-DX":1,"COMEX-GC":-1},"FRED-DEXCHUS":{"ICE-DX":1},
    "FRED-UNRATE":{"CME-ES":-1,"CME-ZN":1,"CBOE-VX":1},"FRED-PETINV":{"NYMEX-NG":-1,"NYMEX-RB":-1,"NYMEX-HO":-1},
    "FRED-USEPUINDXD":{"COMEX-GC":1,"CBOE-VX":1,"CME-ZN":1},"FRED-STLFSI4":{"CBOE-VX":1,"CME-ZN":1,"COMEX-GC":1},
    "GPRD":{"COMEX-GC":1,"CBOE-VX":1,"ICE-DX":1},
  };
  const overlayCandidates=[...new Map(drivers.flatMap((driver)=>(overlayMap[driver.id]||[]).map((productId)=>({driver,product:selectedProducts.find((product)=>product.id===productId),proxySign:proxySignMap[driver.id]?.[productId]||1}))).filter((row)=>row.product).sort((a,b)=>Math.abs(b.driver.impact)-Math.abs(a.driver.impact)).map((row)=>[row.product!.id,row])).values()].slice(0,12);
  const overlayTotal=overlayCandidates.reduce((sum,row)=>sum+Math.abs(row.driver.impact),0)||1;
  const executableOverlayCandidates=overlayCandidates.filter((row)=>Number(row.product?.quote?.last)>0).slice(0,5);
  const midpointDate=new Date(validStart.getTime()+(validEnd.getTime()-validStart.getTime())/2);
  const expiryDates:Record<ExpiryKey,Date>={near:validStart,target:midpointDate,deferred:validEnd};
  const expiryLabel=(key:ExpiryKey)=>expiryDates[key].toISOString().slice(0,7);
  const daysToExpiry=(key:ExpiryKey)=>Math.max(7,Math.ceil((expiryDates[key].getTime()-Date.now())/86400000));
  const normalCdf=(x:number)=>{const t=1/(1+.2316419*Math.abs(x)),d=.3989423*Math.exp(-x*x/2),p=1-d*t*(.3193815+t*(-.3565638+t*(1.781478+t*(-1.821256+t*1.330274))));return x>=0?p:1-p;};
  const optionModelPremium=(strike:number,right:"call"|"put",days:number)=>{const time=Math.max(days,7)/365;const lower=Math.max(scenarioPrices[0].price,.01),upper=Math.max(scenarioPrices[4].price,lower+.01);const sigma=Math.min(.80,Math.max(.12,Math.log(upper/lower)/(2*1.96*Math.sqrt(Math.max(v.horizon,7)/365))));const rate=Math.max(0,v.finance/100),forward=Math.max(v.entry,.01);const black=(k:number,kind:"call"|"put")=>{const vol=sigma*Math.sqrt(time),d1=(Math.log(forward/Math.max(k,.01))+.5*sigma*sigma*time)/vol,d2=d1-vol,discount=Math.exp(-rate*time);return kind==="call"?discount*(forward*normalCdf(d1)-k*normalCdf(d2)):discount*(k*normalCdf(-d2)-forward*normalCdf(-d1));};const atm=Math.max(black(forward,"call"),.01),scale=Math.max(v.premium,.01)/atm;return Math.max(.001,black(strike,right)*scale);};
  const pickProduct=(kind:"future"|"option",venue?:"delivery"|"financial")=>{const rows=selectedProducts.filter((product)=>product.kind===kind&&product.size>=1000&&product.role!=="cross-asset"&&product.role!=="directory"&&(!instruments?.benchmark||product.benchmark===instruments.benchmark));if(kind==="future"&&venue==="financial")return rows.find((product)=>product.id==="CME-BZ")||rows[0];if(kind==="future"&&venue==="delivery")return rows.find((product)=>product.id==="ICE-B"||product.id==="CME-CL")||rows[0];return rows[0]||selectedProducts.find((product)=>product.kind===kind&&product.role!=="cross-asset"&&product.role!=="directory");};
  const oilPlans=planDefinitions.map((plan)=>{
    const targetBarrels=v.volume*plan.coverage/100;
    const orders=plan.legs.flatMap((leg)=>{const product=pickProduct(leg.kind,leg.futureVenue);if(!product)return[];const contracts=Math.max(1,Math.round(targetBarrels*leg.weight/product.size));const barrels=contracts*product.size;const strike=leg.kind==="option"?Math.max(.01,v.strike+(leg.strikeOffset||0)*v.strikeGap):null;const expiry=expiryLabel(leg.expiry);const days=daysToExpiry(leg.expiry);const premiumPerBbl=leg.kind==="option"&&leg.right&&strike!=null?optionModelPremium(strike,leg.right,days):0;const entry=v.entry;const notional=barrels*entry*v.budgetFx;const premium=leg.side*premiumPerBbl*barrels*v.budgetFx;const margin=leg.kind==="future"||leg.side<0?notional*v.margin/100:0;const fees=barrels*v.fee*v.budgetFx*2;const funding=margin*v.finance/100*days/365;return[{...leg,assetClass:"oil" as const,driver:null,proxySign:1 as const,factorWeight:0,riskBudget:0,allocationError:0,units:barrels,product,contracts,barrels,strike,expiry,days,premiumPerBbl,entry,notional,margin,premium,fees,funding}];});
    const totals=orders.reduce((sum,row)=>({grossBarrels:sum.grossBarrels+row.barrels,notional:sum.notional+row.notional,margin:sum.margin+row.margin,premium:sum.premium+row.premium,fees:sum.fees+row.fees,funding:sum.funding+row.funding}),{grossBarrels:0,notional:0,margin:0,premium:0,fees:0,funding:0});
    const initialCash=Math.max(0,totals.margin+totals.premium+totals.fees);
    const scenarios=scenarioPrices.map((scenario)=>{const physical=v.volume*(scenario.price+v.purchaseBasis)*v.fx;const derivativePnl=orders.reduce((sum,row)=>{const legPrice=Math.max(.01,market*Math.pow(Math.max(scenario.price,.01)/Math.max(market,.01),row.days/Math.max(v.horizon,1)));if(row.kind==="future")return sum+row.side*row.barrels*(legPrice-row.entry)*v.fx;const intrinsic=row.right==="call"?Math.max(legPrice-Number(row.strike),0):Math.max(Number(row.strike)-legPrice,0);return sum+row.side*row.barrels*intrinsic*v.fx;},0);const hedged=physical-derivativePnl+totals.premium+totals.funding+totals.fees;return{...scenario,physical,oilDerivativePnl:derivativePnl,crossAssetPnl:0,derivativePnl,hedged,saving:physical-hedged};});
    return{...plan,isMixed:false,orders,totals:{...totals,initialCash},targetBarrels,lower:scenarios[0],mid:scenarios[2],upper:scenarios[4],scenarios};
  });
  const mixedDefinitions=[
    {id:"multi-asset-balanced",baseId:"ladder",name:tx(lang,"原油、贵金属与宏观平衡组合","Oil, metals and macro balanced hedge"),structure:"原油期限梯 + 显著因子跨资产腿",desc:tx(lang,"保留分期原油期货底仓，再把通过主模态筛选且具有实时行情的贵金属、天然气、利率、美元、股指或波动率合约按净影响权重加入组合。","Retains the staged crude futures core, then adds live-quoted metals, gas, rates, dollar, equity or volatility contracts that pass the selected-scale screen."),riskBudgetPct:12,limit:5},
    {id:"multi-asset-collar",baseId:"collar",name:tx(lang,"原油领口与跨资产防御组合","Oil collar with cross-asset defence"),structure:"原油领口 + 避险/宏观期货",desc:tx(lang,"用原油期货与期权领口控制采购价格，同时配置本次显著因素对应的非原油合约，分散单一原油曲线的基差与流动性风险。","Combines an oil futures-options collar with non-oil contracts mapped to significant drivers, reducing dependence on a single crude curve."),riskBudgetPct:9,limit:4},
    {id:"multi-asset-staged",baseId:"rolling-collar",name:tx(lang,"分期原油与多资产动态组合","Staged oil and multi-asset dynamic hedge"),structure:"双期限领口 + 多资产压力对冲",desc:tx(lang,"把原油领口分成两个期限，并加入多个可验证的跨资产期货腿，适合覆盖时间较长且宏观驱动较分散的采购计划。","Splits the oil collar across two maturities and adds several verified cross-asset futures legs for longer procurement windows with dispersed macro drivers."),riskBudgetPct:15,limit:5},
    {id:"multi-asset-options",baseId:"bull-call",name:tx(lang,"原油看涨价差与跨市场组合","Oil call spreads with cross-market overlay"),structure:"双期限原油看涨价差 + 跨市场期货",desc:tx(lang,"原油上涨风险由双期限看涨价差承担，跨资产腿则根据通过检验的外部因素补充方向性保护，并单独显示其压力贡献。","Uses two-expiry oil call spreads for crude upside risk and adds factor-screened cross-market futures with separately disclosed stress contributions."),riskBudgetPct:7,limit:3},
  ];
  const pricedOverlayTotal=executableOverlayCandidates.reduce((sum,row)=>sum+Math.abs(row.driver.impact),0)||1;
  const mixedPlans=mixedDefinitions.flatMap((definition)=>{
    const basePlan=oilPlans.find((plan)=>plan.id===definition.baseId);
    if(!basePlan||!executableOverlayCandidates.length)return[];
    const crossOrders=executableOverlayCandidates.slice(0,definition.limit).map(({driver,product,proxySign},index)=>{
      const factorWeight=Math.abs(driver.impact)/pricedOverlayTotal;
      const riskBudget=v.volume*v.entry*v.budgetFx*definition.riskBudgetPct/100*factorWeight;
      const entry=Number(product!.quote!.last);
      const unitNotional=Math.max(.01,entry*product!.size*(product!.priceScale||1)*v.budgetFx);
      const contracts=Math.max(1,Math.round(riskBudget/unitNotional));
      const notional=contracts*unitNotional;
      const margin=notional*v.margin/100;
      const fees=notional*v.crossFeeBps/10000*2;
      const days=daysToExpiry(index%2===0?"target":"deferred");
      const funding=margin*v.finance/100*days/365;
      const side:1|-1=driver.impact*proxySign>=0?1:-1;
      return{id:`cross-${product!.id}`,kind:"future" as const,side,weight:0,expiry:index%2===0?expiryLabel("target"):expiryLabel("deferred"),right:undefined,strike:null,strikeOffset:undefined,futureVenue:"financial" as const,assetClass:"cross" as const,driver,proxySign,factorWeight,riskBudget,allocationError:notional-riskBudget,units:contracts*product!.size,purposeZh:`${driver.nameZh}通过主模态筛选；以${product!.nameZh||product!.name}作为跨资产压力对冲腿，方向已计入因素与合约价格的${proxySign>0?"同向":"反向"}关系。`,purposeEn:`${driver.nameEn} passed the selected-scale screen; ${product!.name} is used as a cross-asset stress-hedge leg with the ${proxySign>0?"same-direction":"inverse"} factor-to-contract price mapping applied.`,product:product!,contracts,barrels:0,days,premiumPerBbl:0,entry,notional,margin,premium:0,fees,funding};
    });
    const crossTotals=crossOrders.reduce((sum,row)=>({notional:sum.notional+row.notional,margin:sum.margin+row.margin,fees:sum.fees+row.fees,funding:sum.funding+row.funding}),{notional:0,margin:0,fees:0,funding:0});
    const totals={grossBarrels:basePlan.totals.grossBarrels,notional:basePlan.totals.notional+crossTotals.notional,margin:basePlan.totals.margin+crossTotals.margin,premium:basePlan.totals.premium,fees:basePlan.totals.fees+crossTotals.fees,funding:basePlan.totals.funding+crossTotals.funding};
    const initialCash=Math.max(0,totals.margin+totals.premium+totals.fees);
    const scenarios=basePlan.scenarios.map((scenario)=>{
      const oilShock=scenario.price/Math.max(market,.01)-1;
      const crossAssetPnl=crossOrders.reduce((sum,row)=>{const proxyReturn=Math.max(-.35,Math.min(.35,row.proxySign*Math.sign(row.driver.impact)*oilShock*row.factorWeight));return sum+row.side*row.notional*(v.fx/Math.max(v.budgetFx,.01))*proxyReturn;},0);
      const derivativePnl=scenario.oilDerivativePnl+crossAssetPnl;
      const hedged=scenario.physical-derivativePnl+totals.premium+totals.funding+totals.fees;
      return{...scenario,crossAssetPnl,derivativePnl,hedged,saving:scenario.physical-hedged};
    });
    return[{...basePlan,...definition,isMixed:true,educationUrl:"https://www.cmegroup.com/education/featured-reports/hedging-portfolio-with-commodity-currencies",orders:[...basePlan.orders,...crossOrders],totals:{...totals,initialCash},lower:scenarios[0],mid:scenarios[2],upper:scenarios[4],scenarios}];
  });
  const executablePlans=[...oilPlans,...mixedPlans];
  const planActions:Record<string,string>={
    ladder:tx(lang,"近月、目标月和递延月分别买入期货，按40% / 35% / 25%分批锁定采购价。","Buy futures in the near, target and deferred months, locking procurement prices in 40% / 35% / 25% tranches."),
    "bull-call":tx(lang,"在目标月和递延月分别买入较低执行价看涨期权，同时卖出同数量的较高执行价看涨期权。","In both target and deferred months, buy lower-strike calls and sell the same number of higher-strike calls."),
    collar:tx(lang,"买入目标月期货和保护性看跌期权，同时卖出同月较高执行价看涨期权抵减成本。","Buy target-month futures and protective puts, while selling higher-strike calls in the same month to offset cost."),
    calendar:tx(lang,"卖出近月看涨、买入递延月同执行价看涨，并用目标月期货覆盖核心采购量。","Sell near-month calls, buy deferred calls at the same strike, and cover the core procurement volume with target-month futures."),
    butterfly:tx(lang,"先用45%目标月期货覆盖尾部上涨，再买入低执行价看涨1份、卖出中间执行价2份、买入高执行价1份。","Cover the upside tail with a 45% target-month futures core, then buy one lower call, sell two middle calls and buy one upper call."),
    seagull:tx(lang,"买入少量近月期货和目标月看涨，同时卖出更高执行价看涨与较低执行价看跌。","Buy a small near-month futures core and target-month calls, while selling higher calls and lower puts."),
    "rolling-collar":tx(lang,"把采购量分成两批，在近月和目标月分别建立“买期货、买看跌、卖看涨”的领口。","Split procurement into two tranches and build a long-future, long-put, short-call collar in both near and target months."),
    condor:tx(lang,"用40%目标月期货打底，其余覆盖量在四个执行价上建立买低、卖中间两档、买高的看涨鹰式。","Use a 40% target-month futures core, then buy the outer calls and sell the two inner calls across four strikes."),
    diagonal:tx(lang,"买入目标月期货底仓，卖出近月高执行价看涨，同时买入递延月较低执行价看涨。","Buy a target-month futures core, sell a higher-strike near call and buy a lower-strike deferred call."),
    "staged-vertical":tx(lang,"按30% / 45% / 25%在近月、目标月和递延月分别建立“买低执行价、卖高执行价”的看涨价差。","Build lower-strike-long, higher-strike-short call spreads in near, target and deferred months at 30% / 45% / 25%."),
    "multi-asset-balanced":tx(lang,"建立三期限原油期货底仓，并按显著净影响权重加入最多五个具有实时行情的跨资产期货。","Build the three-expiry oil futures core and add up to five live-quoted cross-asset futures weighted by significant net impacts."),
    "multi-asset-collar":tx(lang,"建立目标月原油领口，并加入最多四个贵金属、能源替代品、利率、美元、股指或波动率期货腿。","Build the target-month oil collar and add up to four metals, alternative-energy, rates, dollar, equity or volatility futures legs."),
    "multi-asset-staged":tx(lang,"分两期建立原油领口，再按本次筛选结果配置最多五个跨资产压力对冲腿。","Stage oil collars across two maturities, then add up to five cross-asset stress-hedge legs selected by this run."),
    "multi-asset-options":tx(lang,"用双期限原油看涨价差保护采购上行风险，并以最多三个跨市场期货补充分散化。","Protect crude upside with two-expiry call spreads and add up to three cross-market futures for diversification."),
  };
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
          min={1}
          onChange={(n) => set("volume", n)}
        />
        <Field
          label={tx(lang, "预算单价", "Budget price")}
          value={v.budget}
          suffix={tx(lang, "美元/桶", "USD/bbl")}
          min={0}
          onChange={(n) => set("budget", n)}
        />
        <Field label={tx(lang,"期货限价参考","Futures limit reference")} value={v.entry} suffix={tx(lang,"美元/桶","USD/bbl")} step={.01} min={0} onChange={(n)=>set("entry",n)}/>
        <Field
          label={tx(lang, "套保覆盖", "Hedge coverage")}
          value={v.ratio}
          suffix="%"
          min={0}
          max={100}
          onChange={(n) => set("ratio", n)}
        />
        <Field
          label={tx(lang, "期货占比", "Futures share")}
          value={v.futures}
          suffix="%"
          min={0}
          max={100}
          onChange={(n) => set("futures", n)}
        />
        <Field
          label={tx(lang, "预计采购基差", "Expected purchase basis")}
          value={v.purchaseBasis}
          suffix={tx(lang, "美元/桶", "USD/bbl")}
          step={.1}
          onChange={(n) => set("purchaseBasis", n)}
        />
        <Field
          label={tx(lang, "预算基差", "Budget basis")}
          value={v.budgetBasis}
          suffix={tx(lang, "美元/桶", "USD/bbl")}
          step={.1}
          onChange={(n) => set("budgetBasis", n)}
        />
        <Field
          label={tx(lang, "美元兑人民币", "USD/CNY")}
          value={v.fx}
          suffix="CNY"
          step={0.01}
          onChange={(n) => set("fx", n)}
        />
        <Field label={tx(lang,"预算汇率","Budget FX rate")} value={v.budgetFx} suffix="CNY" step={.01} onChange={(n)=>set("budgetFx",n)}/>
        <Field
          label={tx(lang, "保证金比例", "Margin rate")}
          value={v.margin}
          suffix="%"
          min={0}
          max={100}
          onChange={(n) => set("margin", n)}
        />
        <Field
          label={tx(lang, "融资年利率", "Annual funding rate")}
          value={v.finance}
          suffix="%"
          step={0.1}
          min={0}
          onChange={(n) => set("finance", n)}
        />
        <Field
          label={tx(lang, "合约规模", "Contract size")}
          value={v.contract}
          suffix={tx(lang, "桶", "bbl")}
          min={1}
          onChange={(n) => set("contract", n)}
        />
        <Field
          label={tx(lang, "单边费用", "One-way fee")}
          value={v.fee}
          suffix={tx(lang, "美元/桶", "USD/bbl")}
          step={0.005}
          min={0}
          onChange={(n) => set("fee", n)}
        />
        <Field label={tx(lang,"跨资产单边费用","Cross-asset one-way fee")} value={v.crossFeeBps} suffix="bps" step={.1} min={0} onChange={(n)=>set("crossFeeBps",n)}/>
        <Field label={tx(lang,"ATM权利金（预测推导/可覆盖）","ATM premium (forecast-derived / override)")} value={v.premium} suffix={tx(lang,"美元/桶","USD/bbl")} step={.1} min={0} onChange={(n)=>set("premium",n)}/>
        <Field label={tx(lang,"中心执行价","Center strike")} value={v.strike} suffix={tx(lang,"美元/桶","USD/bbl")} step={.25} min={0} onChange={(n)=>set("strike",n)}/>
        <Field label={tx(lang,"执行价间距","Strike interval")} value={v.strikeGap} suffix={tx(lang,"美元/桶","USD/bbl")} step={.25} min={.25} onChange={(n)=>set("strikeGap",n)}/>
        <DateField lang={lang} label={tx(lang,"套保需求开始","Hedge need starts")} value={hedgeStart} onChange={(value)=>onHedgeWindowChange("hedgeStart",value)}/>
        <DateField lang={lang} label={tx(lang,"套保需求结束","Hedge need ends")} value={hedgeEnd} onChange={(value)=>onHedgeWindowChange("hedgeEnd",value)}/>
      </div>
      <div className={`hedge-window-summary ${hedgeRangeValid?"":"invalid"}`}><div><b>{tx(lang,"期限篮子","Maturity basket")}</b><span>{hedgeStart} → {hedgeEnd} · {hedgeWindowDays} {tx(lang,"天","days")}</span></div><ol><li><b>{expiryLabel("near")}</b><span>{tx(lang,"起始月保护","Start-month protection")}</span></li><li><b>{expiryLabel("target")}</b><span>{tx(lang,"区间中段保护","Mid-window protection")}</span></li><li><b>{expiryLabel("deferred")}</b><span>{tx(lang,"结束月保护","End-window protection")}</span></li></ol><small>{hedgeRangeValid?tx(lang,"组合中的近月、目标月和递延月交易腿均由该需求区间生成；具体到期日和可交易合约须在交易所或经纪商合约链中复核。","Near, target and deferred legs are generated from this requested interval. Confirm exact expiries and tradable contracts in the exchange or broker contract chain."):tx(lang,"结束日必须晚于或等于开始日；修正日期前，组合计算仅使用临时的一日窗口。","The end date must be on or after the start date. A temporary one-day window is used until the dates are corrected.")}</small></div>
      <div className="result-grid">
        <Kpi
          label={tx(lang, "未套保成本", "Unhedged cost")}
          value={tx(lang, `${(base.physical / 1e6).toFixed(3)} 百万元`, `RMB ${(base.physical / 1e6).toFixed(3)}m`)}
          delta={tx(lang,"模型中位价格与采购基差","Median model price plus purchase basis")}
        />
        <Kpi
          label={tx(lang, "套保后净成本", "Net hedged cost")}
          value={tx(lang, `${(base.hedged / 1e6).toFixed(3)} 百万元`, `RMB ${(base.hedged / 1e6).toFixed(3)}m`)}
          delta={delta>=0?tx(lang,`相对未套保节省 ${(delta/1e6).toFixed(3)} 百万元`,`Saving vs unhedged RMB ${(delta/1e6).toFixed(3)}m`):tx(lang,`保险与机会成本 ${(-delta/1e6).toFixed(3)} 百万元`,`Insurance/opportunity cost RMB ${(-delta/1e6).toFixed(3)}m`)}
        />
        <Kpi
          label={tx(lang, "相对预算", "Versus budget")}
          value={tx(lang, `${((base.hedged-budget)/1e6).toFixed(3)} 百万元`, `RMB ${((base.hedged-budget)/1e6).toFixed(3)}m`)}
          tone={base.hedged>budget?"warm":""}
        />
        <Kpi
          label={tx(lang, "保证金需求", "Margin requirement")}
          value={tx(lang, `${(base.marginReq/1e6).toFixed(3)} 百万元`, `RMB ${(base.marginReq/1e6).toFixed(3)}m`)}
          delta={tx(lang, `融资 ${(base.funding/1e4).toFixed(3)} 万元 · 双边费用 ${(base.fees/1e4).toFixed(3)} 万元`, `Funding RMB ${(base.funding/1e3).toFixed(3)}k · round-trip fees RMB ${(base.fees/1e3).toFixed(3)}k`)}
        />
      </div>
      <div className="formula-note"><b>{tx(lang,"口径已校正","Corrected accounting")}</b><span>{tx(lang,"现货成本 =（基准价格 + 采购基差）× 汇率；期货盈亏只比较结算价与入场价。基差不再被错误地从期货盈亏中重复扣除。","Physical cost = (benchmark + purchase basis) × FX. Futures P&L compares settlement with entry price only; basis is no longer double-counted in futures P&L.")}</span></div>
      <h3 className="result-title">{tx(lang,"不同价格情景下的总采购成本","Total procurement cost across price scenarios")}</h3>
      <ChartFrame label={tx(lang,"缩放查看未套保与套保成本","Zoom to compare unhedged and hedged cost")}><div className="chart medium"><ResponsiveContainer><ComposedChart data={scenarioRows} margin={{top:8,right:20,bottom:4,left:20}}><CartesianGrid vertical={false}/><XAxis dataKey="scenario"/><YAxis yAxisId="cost" width={72} tickMargin={8} tickFormatter={(value)=>`${(Number(value)/1e6).toFixed(3)}m`}/><YAxis yAxisId="improvement" orientation="right" width={72} tickMargin={8} tickFormatter={(value)=>`${(Number(value)/1e6).toFixed(3)}m`}/><Tooltip formatter={(value)=>tx(lang,`${(Number(value)/1e6).toFixed(3)} 百万元`,`RMB ${(Number(value)/1e6).toFixed(3)}m`)}/><Legend/><Bar yAxisId="cost" dataKey="unhedged" name={tx(lang,"未套保成本","Unhedged cost")} fill="#7d8792" radius={[8,8,0,0]}/><Bar yAxisId="cost" dataKey="hedged" name={tx(lang,"套保后成本","Hedged cost")} fill="#5f7895" radius={[8,8,0,0]}/><Line yAxisId="improvement" dataKey="saving" name={tx(lang,"相对成本改善（右轴）","Cost improvement (right axis)")} stroke="#c47d59" strokeWidth={2.4}/></ComposedChart></ResponsiveContainer></div></ChartFrame>
      <h3 className="result-title">{tx(lang,`原油与跨资产组合方案（${executablePlans.length}套）`,`Oil and cross-asset portfolios (${executablePlans.length})`)}</h3>
      <p className="plain-note">{tx(lang,"前十套保留原油期限梯、价差、领口、蝶式、鹰式和海鸥式等结构；后续组合把本次主模态筛选出的贵金属、天然气、利率、美元、股指或波动率合约正式纳入订单、费用和压力损益计算。只有同时具备可核验规格与实时行情的跨资产合约才会进入正式组合。","The first ten plans retain crude ladders, spreads, collars, butterflies, condors and seagulls. Additional plans formally incorporate selected-scale metals, gas, rates, dollar, equity or volatility contracts into orders, costs and stress P&L. A cross-asset contract enters a formal plan only when both its specification and live quote are available.")}</p>
      <div className="portfolio-grid">{executablePlans.map((plan)=><details className={`portfolio-card ${plan.isMixed?"mixed-asset":""}`} key={plan.id} onToggle={(event)=>{const isOpen=event.currentTarget.open;setOpenPlans((previous)=>{const next=new Set(previous);if(isOpen)next.add(plan.id);else next.delete(plan.id);return next;});}}><summary><div><span>{plan.name}{plan.isMixed&&<em className="asset-badge">{tx(lang,"多资产","MULTI-ASSET")}</em>}</span><b>{plan.coverage.toFixed(3)}% · {plan.orders.length} {tx(lang,"条腿","legs")}</b></div><div className="strategy-action"><span>{tx(lang,"交易安排","Trade plan")}</span><strong>{planActions[plan.id]}</strong></div><div className="strategy-structure"><span>{tx(lang,"结构公式","Structure")}</span><code>{plan.structure}</code></div><p>{plan.desc}</p><dl><div><dt>{tx(lang,"95%上界改善","95% upper improvement")}</dt><dd className={plan.upper.saving>=0?"positive":"negative"}>{(plan.upper.saving/1e6).toFixed(3)}m</dd></div><div><dt>{tx(lang,"首期资金","Initial cash")}</dt><dd>{(plan.totals.initialCash/1e6).toFixed(3)}m</dd></div><div><dt>{tx(lang,"保证金 / 净权利金","Margin / net premium")}</dt><dd>{(plan.totals.margin/1e6).toFixed(3)}m / {(plan.totals.premium/1e6).toFixed(3)}m</dd></div><div><dt>{tx(lang,"打开多腿执行清单","Open multi-leg ticket")}</dt><dd><ChevronRight/></dd></div></dl></summary><div className="portfolio-detail">
        <div className="strategy-banner"><div><span>{tx(lang,"组合结构","Structure")}</span><b>{plan.structure}</b></div><a href={plan.educationUrl} target="_blank" rel="noreferrer">{tx(lang,"查看交易所策略说明","Exchange strategy reference")} <ArrowRight/></a></div>
        <div className="order-summary"><span><b>{plan.targetBarrels.toLocaleString()}</b>{tx(lang,"目标覆盖桶数","target bbl")}</span><span><b>{plan.totals.grossBarrels.toLocaleString()}</b>{tx(lang,"全部交易腿名义桶数","gross leg bbl")}</span><span><b>RMB {(plan.totals.initialCash/1e6).toFixed(3)}m</b>{tx(lang,"首期资金","initial cash")}</span><span><b>RMB {((plan.totals.fees+plan.totals.funding)/1e4).toFixed(3)}万</b>{tx(lang,"双边费用与融资","fees + funding")}</span></div>
        <div className="order-lines">{plan.orders.map((order)=><article className={order.assetClass==="cross"?"cross-order":""} key={`${plan.id}-${order.id}`}><header><span>{order.product.exchange}{order.assetClass==="cross"&&<em className="asset-badge">{tx(lang,"跨资产","CROSS-ASSET")}</em>}</span><b className={order.side>0?"buy-side":"sell-side"}>{order.side>0?tx(lang,"买入","BUY / LONG"):tx(lang,"卖出","SELL / SHORT")} {order.contracts} × {order.product.code} · {order.expiry}</b></header><h4>{lang==="zh"?order.product.nameZh||order.product.name:order.product.name}</h4><p>{lang==="zh"?order.purposeZh:order.purposeEn}</p><dl><div><dt>{tx(lang,"到期月份 / 方向","Expiry / side")}</dt><dd>{order.expiry} · {order.side>0?tx(lang,"买入","BUY"):tx(lang,"卖出","SELL")}</dd></div>{order.kind==="option"&&<><div><dt>{tx(lang,"期权类型 / 行权价","Option / strike")}</dt><dd>{order.right==="call"?tx(lang,"看涨","CALL"):tx(lang,"看跌","PUT")} · {Number(order.strike).toFixed(3)}</dd></div><div><dt>{tx(lang,"模型权利金 / 桶","Model premium / bbl")}</dt><dd>{order.premiumPerBbl.toFixed(3)} USD</dd></div></>}{order.assetClass==="cross"?<><div><dt>{tx(lang,"张数 / 合约单位","Contracts / contract units")}</dt><dd>{order.contracts} / {order.units.toLocaleString()} {order.product.contractUnit||tx(lang,"单位","units")}</dd></div><div><dt>{tx(lang,"对应因素 / 权重","Matched driver / weight")}</dt><dd>{lang==="zh"?order.driver?.nameZh:order.driver?.nameEn} · {(order.factorWeight*100).toFixed(3)}%</dd></div><div><dt>{tx(lang,"目标风险预算 / 取整偏差","Target risk budget / rounding")}</dt><dd>RMB {(order.riskBudget/1e6).toFixed(3)}m / {(order.allocationError/1e3).toFixed(3)}k</dd></div></>:<div><dt>{tx(lang,"张数 / 名义桶数","Contracts / notional bbl")}</dt><dd>{order.contracts} / {order.barrels.toLocaleString()}</dd></div>}<div><dt>{tx(lang,"期货参考限价","Futures reference")}</dt><dd>{order.kind==="future"?`${order.entry.toFixed(3)} ${order.product.currency||"USD"}`:"—"}</dd></div><div><dt>{tx(lang,"保证金估算","Margin estimate")}</dt><dd>RMB {(order.margin/1e6).toFixed(3)}m</dd></div><div><dt>{tx(lang,"权利金现金流","Premium cash flow")}</dt><dd className={order.premium<=0?"credit":"debit"}>RMB {(order.premium/1e6).toFixed(3)}m</dd></div><div><dt>{tx(lang,"双边费用 / 融资","Fees / funding")}</dt><dd>RMB {(order.fees/1e3).toFixed(3)}k / {(order.funding/1e3).toFixed(3)}k</dd></div></dl><a href={order.product.url} target="_blank" rel="noreferrer">{tx(lang,"核对交易所规格","Verify exchange specification")} <ArrowRight/></a></article>)}</div>
        <div className="strategy-scenarios">{plan.scenarios.map((row)=><div key={row.scenario}><span>{row.scenario}</span><b>RMB {(row.hedged/1e6).toFixed(3)}m</b><em className={row.saving>=0?"positive":"negative"}>{tx(lang,"较未套保","vs unhedged")} {(row.saving/1e6).toFixed(3)}m</em></div>)}</div>
        {openPlans.has(plan.id)&&<ChartFrame label={tx(lang,"悬停比较组合成本与衍生品损益","Hover to compare portfolio cost and derivative payoff")}><div className="chart strategy-payoff-chart"><ResponsiveContainer><ComposedChart data={plan.scenarios.map((row)=>({scenario:row.scenario,unhedged:row.physical/1e6,hedged:row.hedged/1e6,oilDerivative:row.oilDerivativePnl/1e6,crossAsset:row.crossAssetPnl/1e6}))} margin={{top:12,right:24,bottom:4,left:16}}><CartesianGrid vertical={false}/><XAxis dataKey="scenario" tick={{fontSize:10}}/><YAxis yAxisId="cost" width={62} tickFormatter={(value)=>Number(value).toFixed(3)} label={{value:tx(lang,"采购成本·百万元","Cost · RMB m"),angle:-90,position:"insideLeft",fontSize:10}}/><YAxis yAxisId="payoff" orientation="right" width={62} tickFormatter={(value)=>Number(value).toFixed(3)} label={{value:tx(lang,"衍生品损益·百万元","Payoff · RMB m"),angle:90,position:"insideRight",fontSize:10}}/><Tooltip formatter={(value,name)=>[`${Number(value).toFixed(3)}m`,String(name)]}/><Legend/><Bar yAxisId="payoff" stackId="payoff" dataKey="oilDerivative" name={tx(lang,"原油衍生品损益","Oil-derivative payoff")} fill="#8fa2b7" radius={plan.isMixed?[0,0,0,0]:[7,7,0,0]}/>{plan.isMixed&&<Bar yAxisId="payoff" stackId="payoff" dataKey="crossAsset" name={tx(lang,"跨资产压力损益","Cross-asset stress payoff")} fill="#c47d59" radius={[7,7,0,0]}/>}<Line yAxisId="cost" dataKey="unhedged" name={tx(lang,"未套保成本","Unhedged cost")} stroke="#7d8792" strokeWidth={2.1}/><Line yAxisId="cost" dataKey="hedged" name={tx(lang,"组合后净成本","Portfolio net cost")} stroke="#514b80" strokeWidth={2.8}/></ComposedChart></ResponsiveContainer></div></ChartFrame>}
        <p className="plain-note">{tx(lang,plan.isMixed?"原油腿按当前价格到预测终值的对数路径结算；跨资产腿按本次通过筛选的净影响权重做标准化压力映射。后者是透明的敏感性测试，不是跨资产价格预测、因果结论或预期收益承诺。":"多期限腿的情景结算价按“当前价格→预测终值”的对数路径映射到各自到期月；这是一致的路径压力测试，不是对远期曲线或成交价的承诺。",plan.isMixed?"Oil legs settle along a log path from current price to the forecast endpoint. Cross-asset legs use a normalized stress mapping based on significant net-impact weights. This is a transparent sensitivity test—not a cross-asset price forecast, causal claim or return promise.":"Multi-expiry settlement prices are mapped to each expiry along a log path from the current price to the forecast endpoint. This is a consistent path stress test, not a promise of the forward curve or execution price.")}</p>
        <ol className="execution-steps"><li>{tx(lang,"先在经纪商核对每条腿的准确到期日、期权行权价与可成交报价；页面月份是采购期限映射，不替代合约日历。","First confirm each exact expiry date, strike and executable quote with the broker. Displayed months map the procurement horizon and do not replace the contract calendar.")}</li><li>{tx(lang,"优先使用交易所组合单、策略单或RFQ一次性报出全部交易腿，避免逐腿成交造成方向裸露；若只能逐腿执行，先成交限制尾部风险的买入腿。","Prefer an exchange combination order, strategy order or RFQ for all legs to avoid legging risk. If legs must be entered separately, execute the long tail-protection legs first.")}</li><li>{tx(lang,"ATM权利金输入应使用同一时点的真实期权报价；其他执行价权利金由预测波动率曲面插值，仅用于测算，成交前必须替换为经纪商报价。","Enter a real, same-timestamp ATM option quote. Other-strike premiums are interpolated from the forecast-implied surface for planning only and must be replaced with broker quotes before execution.")}</li><li>{tx(lang,"短期权按配置的保证金比例进行保守估算；实际SPAN组合保证金、价差抵扣、佣金和流动性冲击以经纪商回报为准。采购完成时同步平仓或整体展期。","Short-option margin uses the configured rate as a conservative estimate. Actual SPAN offsets, commissions and liquidity impact must come from the broker. Close or roll the full structure with the physical purchase.")}</li></ol>
      </div></details>)}</div>
      <h3 className="result-title">{tx(lang,"由本次影响分析筛出的跨资产辅助工具","Cross-asset overlays selected from this analysis")}</h3>
      <p className="plain-note">{tx(lang,"候选范围来自完整金融产品目录，再按本次已计算的净影响因素匹配；研究权重只表示进入下一步滚动套保比率估计的优先级，不等于可直接下单的资金比例。","Candidates come from the full instrument directory and are matched to drivers calculated in this run. Research weights rank candidates for a subsequent rolling hedge-ratio estimate; they are not executable capital allocations.")}</p>
      <div className="overlay-grid">{overlayCandidates.map(({driver,product,proxySign})=>{const weight=Math.abs(driver.impact)/overlayTotal*100;const long=driver.impact*proxySign>=0;return <article key={product!.id}><header><span>{product!.exchange}</span><b>{product!.code}</b></header><h4>{lang==="zh"?product!.nameZh||product!.name:product!.name}</h4><p>{tx(lang,"触发因素：","Matched driver: ")} {lang==="zh"?driver.nameZh:driver.nameEn}</p><div className="overlay-direction"><strong className={long?"positive":"negative"}>{long?tx(lang,"候选方向：买入","Candidate side: LONG"):tx(lang,"候选方向：卖出","Candidate side: SHORT")}</strong><span>{tx(lang,"研究权重","Research weight")} {weight.toFixed(3)}%</span></div><div className="overlay-bar"><i style={{width:`${Math.max(3,weight)}%`}}/></div><small>{tx(lang,`估计净影响 ${driver.impact.toFixed(3)} 美元/桶 · 产品映射${proxySign>0?"同向":"反向"}`,`Estimated net impact $${driver.impact.toFixed(3)}/bbl · ${proxySign>0?"same-direction":"inverse"} product mapping`)}</small><a href={product!.url} target="_blank" rel="noreferrer">{tx(lang,"核对产品规格","Verify product specification")} <ArrowRight/></a></article>;})}</div>
      {!overlayCandidates.length&&<div className="empty-search">{tx(lang,"本次通过检验的因素暂未匹配到可靠的跨资产合约；系统不会用无关产品凑数。","No driver from this run matched a sufficiently documented cross-asset contract. The system will not pad the list with unrelated products.")}</div>}
      <div className="broker-note"><ShieldCheck/><div><b>{instruments?.broker.connected?tx(lang,"经纪商合约发现已配置","Broker contract discovery configured"):tx(lang,"当前为交易所产品匹配，不是下单接口","Exchange product matching, not an order interface")}</b><p>{tx(lang,"产品代码和合约规模来自交易所规格页；具体到期月份、实时买卖价、权利金与可成交性必须在已授权经纪商会话中复核。页面只展示模型情景损益，不承诺收益，也不会提交订单。","Product codes and sizes come from exchange specifications. Expiry, live bid/ask, premium and tradability require an authenticated broker session. Results are model scenarios, not promised returns, and no order is submitted.")}</p></div></div>
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

function DecisionGrangerSummary({ lang, granger, drivers, alpha, selectedScale }: { lang:Lang; granger:GrangerResult[]; drivers:DriverResult[]; alpha:number; selectedScale:string }) {
  const rows=[...granger].sort((a,b)=>Number(b.significant)-Number(a.significant)||a.pValue-b.pValue);
  if(!rows.length) return <div className="association-empty">{tx(lang,"当前有效共同样本不足以形成格兰杰领先关联检验，页面不会用演示结果补位。","The current aligned sample is insufficient for a Granger lead-association test; no demo result is substituted.")}</div>;
  return <section className="association-section" aria-label={tx(lang,"变量与油价的领先关联","Leading associations with oil prices")}>
    <div className="association-head"><div><span>{tx(lang,"主模态领先关联检验","MAIN-SCALE LEAD-ASSOCIATION CHECK")}</span><h3>{tx(lang,"哪些变量通过筛选并进入后续 FEVD","Which variables pass the gate into the subsequent FEVD")}</h3></div><small>{selectedScale} · {tx(lang,`判断线 p < ${alpha.toFixed(3)}`,`decision line p < ${alpha.toFixed(3)}`)}</small></div>
    <p className="association-note">{tx(lang,"这里检验的是变量过去值能否改善主模态油价预测，不是因果证明。只有通过当前显著性阈值的变量才进入 FEVD；未通过结果仅作为筛选审计展示。统计证据条只用于排序，也不是发生概率。","This tests whether past values improve prediction of the selected oil-price scale; it is not proof of causality. Only variables passing the current threshold enter FEVD. Non-passing results remain visible solely as a screening audit. The evidence bar is a ranking aid, not a probability.")}</p>
    <div className="association-grid">{rows.map((row)=>{const driver=drivers.find((item)=>item.id===row.id);const evidence=Math.min(100,Math.max(4,-Math.log10(Math.max(row.pValue,1e-12))/4*100));const direction=driver?driver.impact>=0?tx(lang,"同向","same direction"):tx(lang,"反向","opposite direction"):tx(lang,"方向待净影响估计","direction pending net-impact estimate");return <article key={row.id} className={row.significant?"linked":"muted"}>
      <header><b>{lang==="zh"?row.nameZh:row.nameEn}</b><em>{row.significant?tx(lang,"发现领先关联","Leading association found"):tx(lang,"暂未发现稳定关联","No stable association found")}</em></header>
      <p>{row.significant?tx(lang,`在当前样本与参数下，该变量通常提前 ${row.lag} 期提供额外信息，已进入 FEVD。`,`Under the current sample and settings, this variable adds information about ${row.lag} period${row.lag===1?"":"s"} ahead and enters FEVD.`):tx(lang,"在当前主模态与阈值下未通过检验，已从 FEVD 和核心净影响结论中排除。","It does not pass the selected-scale threshold and is excluded from FEVD and the core net-impact conclusion.")}</p>
      <div className="association-stats"><span>{tx(lang,"最优滞后","Best lag")} <strong>{row.lag}</strong></span><span>p <strong>{row.pValue.toFixed(3)}</strong></span><span>F <strong>{row.fStatistic.toFixed(3)}</strong></span></div>
      <div className="evidence-track"><i style={{width:`${evidence}%`}}/></div>
      <footer><span>{tx(lang,"估计方向","Estimated direction")}：{direction}</span>{driver&&<strong className={driver.impact>=0?"positive":"negative"}>{driver.impact>=0?"+":""}{driver.impact.toFixed(3)} USD/bbl</strong>}</footer>
    </article>})}</div>
  </section>;
}

function RollingImpactChart({ lang, data }: { lang: Lang; data: NetImpactResult["rolling"] }) {
  return <ChartFrame label={tx(lang,"拖动底部范围条查看滚动结果","Drag the range selector to inspect the rolling result")}><div className="chart medium"><ResponsiveContainer><LineChart data={data}><CartesianGrid vertical={false}/><XAxis dataKey="date" minTickGap={35} tick={{fontSize:10}}/><YAxis tick={{fontSize:10}}/><Tooltip formatter={(v)=>Number(v).toFixed(3)}/><Legend/><Line dataKey="observed" name={tx(lang,"实际变动","Observed change")} stroke="#30343d" dot={false}/><Line dataKey="fitted" name={tx(lang,"模型拟合","Model fit")} stroke="#6f69a2" dot={false}/><Brush dataKey="date" height={22} stroke="#6f69a2"/></LineChart></ResponsiveContainer></div></ChartFrame>;
}

function FevdChart({ lang, data }: { lang: Lang; data: NetImpactResult["fevd"] }) {
  const rows = data.map((row) => ({ name: lang === "zh" ? row.nameZh : row.nameEn, share: row.share }));
  return <ChartFrame label={tx(lang,"缩放查看各因素对油价预测误差的解释份额","Zoom to inspect factor shares of oil-price forecast error variance")}><div className="chart medium"><ResponsiveContainer><BarChart data={rows} layout="vertical" margin={{left:35,right:30}}><CartesianGrid horizontal={false}/><XAxis type="number" unit="%"/><YAxis type="category" dataKey="name" width={150} tick={{fontSize:10}}/><Tooltip formatter={(v)=>[`${Number(v).toFixed(3)}%`,tx(lang,"份额","Share")]}/><Bar dataKey="share" fill="#c47d59" radius={[0,8,8,0]}/></BarChart></ResponsiveContainer></div></ChartFrame>;
}

function RollingFevdChart({ lang, data }: { lang: Lang; data: NetImpactResult["rollingFevd"] }) {
  return <ChartFrame label={tx(lang,"拖动范围条查看冲击来源随时间的变化","Drag the range selector to inspect changing shock sources")}><div className="chart medium"><ResponsiveContainer><AreaChart data={data}><CartesianGrid vertical={false}/><XAxis dataKey="date" minTickGap={35} tick={{fontSize:10}}/><YAxis domain={[0,100]} unit="%"/><Tooltip formatter={(v)=>`${Number(v).toFixed(3)}%`}/><Legend/><Area dataKey="externalShare" name={tx(lang,"外部因素冲击","External-factor shocks")} stackId="1" stroke="#c47d59" fill="#ead0c1"/><Area dataKey="ownShare" name={tx(lang,"油价自身冲击","Oil-price own shocks")} stackId="1" stroke="#6f69a2" fill="#d9d5ea"/><Brush dataKey="date" height={22} stroke="#6f69a2"/></AreaChart></ResponsiveContainer></div></ChartFrame>;
}

function HhtChart({ lang, data }: { lang: Lang; data: NetImpactResult["hht"] }) {
  return <ChartFrame label={tx(lang,"拖动范围条查看主频率随时间的变化","Drag the range selector to inspect changing instantaneous frequency")}><div className="chart medium"><ResponsiveContainer><LineChart data={data}><CartesianGrid vertical={false}/><XAxis dataKey="date" minTickGap={35} tick={{fontSize:10}}/><YAxis tick={{fontSize:10}} domain={[0,"auto"]}/><Tooltip formatter={(v,name)=>[Number(v).toFixed(3),name === "frequency" ? tx(lang,"瞬时频率","HHT instantaneous frequency") : String(name)]}/><Line dataKey="frequency" name={tx(lang,"HHT瞬时频率","HHT instantaneous frequency")} stroke="#9b6d51" strokeWidth={2} dot={false}/><Brush dataKey="date" height={22} stroke="#756fa5"/></LineChart></ResponsiveContainer></div></ChartFrame>;
}

function BreakChart({ lang, data }: { lang: Lang; data: NetImpactResult["breakTest"]["optimal"]["profile"] }) {
  return <ChartFrame label={tx(lang,"拖动范围条检查候选结构变化日期","Drag the range selector to inspect candidate break dates")}><div className="chart medium"><ResponsiveContainer><LineChart data={data}><CartesianGrid vertical={false}/><XAxis dataKey="date" minTickGap={35} tick={{fontSize:10}}/><YAxis unit="%"/><Tooltip formatter={(v)=>[`${Number(v).toFixed(3)}%`,tx(lang,"分段拟合改善","Segmented-fit improvement")]}/><Line dataKey="improvementPercent" stroke="#587a9a" dot={false}/><Brush dataKey="date" height={22} stroke="#587a9a"/></LineChart></ResponsiveContainer></div></ChartFrame>;
}

function ScaleGrangerMatrix({ lang, data }: { lang: Lang; data: ScaleGrangerResult[] }) {
  const imfs = [...new Set(data.map((row) => row.imf))];
  const factors = [...new Map(data.map((row) => [row.id, { id: row.id, name: lang === "zh" ? row.nameZh : row.nameEn }])).values()];
  return <div className="scale-matrix" style={{"--imf-count":imfs.length} as React.CSSProperties}>
    <div className="matrix-head"><b>{tx(lang,"解释变量","Factor")}</b>{imfs.map((imf)=><b key={imf}>{imf}</b>)}</div>
    {factors.map((factor)=><div className="matrix-row" key={factor.id}><strong>{factor.name}</strong>{imfs.map((imf)=>{const row=data.find((item)=>item.id===factor.id&&item.imf===imf)!; const intensity=Math.min(1,Math.max(0,-Math.log10(Math.max(row.pValue,1e-12))/4)); return <span key={imf} className={row.significant?"significant":""} style={{"--strength":intensity} as React.CSSProperties} title={`${factor.name} · ${imf} · lag ${row.lag} · F ${row.fStatistic.toFixed(3)} · p ${row.pValue.toFixed(3)}`}>{row.pValue.toFixed(3)}</span>})}</div>)}
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
            ? "净影响、价格预测和危机预警彼此独立，参数与中间结果完整保留；数据中心已作为顶层工作区独立开放。"
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
      </div>
      {tab === "impact" && <ImpactLab lang={lang} />}
      {tab === "forecast" && <ForecastLab lang={lang} />}
      {tab === "risk" && <RiskLab lang={lang} />}
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
  const [window, setWindow] = useState(120);
  const [maxLag, setMaxLag] = useState(5);
  const [alpha, setAlpha] = useState(.1);
  const today = new Date().toISOString().slice(0,10);
  const [estimationStart, setEstimationStart] = useState("2018-11-07");
  const [eventStart, setEventStart] = useState("2020-01-01");
  const [eventEnd, setEventEnd] = useState(today);
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
      const defaults = rows.filter((item) => item.id !== target && (saved.has(item.id) || ["GPRD","FRED-PETINV","FRED-DTWEXBGS","FRED-DGS10","FRED-INDPRO","FRED-T10YIE","FRED-VIXCLS","FRED-HENRYHUB"].includes(item.id))).map((item) => item.id);
      setFactors(new Set(defaults));
    }).catch((reason) => setError(reason instanceof Error ? reason.message : String(reason)));
  }, [target]);
  const run = async () => {
    setRunning(true); setError(""); setResult(null);
    try {
      const records = readLocalRecords().filter((record)=>record.kind==="series" && factors.has(record.id) && Array.isArray(record.payload.points));
      const customSeries = records.map((record)=>({id:record.id,nameZh:String(record.payload.name||record.label),nameEn:String(record.payload.nameEn||record.label),points:record.payload.points}));
      const payload = await requestLiveAnalysis<NetImpactResult>("/api/models/net-impact", { imf, window, maxLag, alpha, estimationStart, eventStart, eventEnd, target, factors: [...factors], customSeries });
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
            suffix={tx(lang, "个交易日", "trading days")}
            min={48}
            max={500}
            onChange={setWindow}
          />
          <Field label={tx(lang, "最大格兰杰滞后", "Maximum Granger lag")} value={maxLag} suffix={tx(lang, "阶", "lags")} min={1} max={6} onChange={setMaxLag} />
          <Field label={tx(lang, "显著性阈值", "Significance level")} value={alpha} suffix="α" step={.01} min={.01} max={.2} onChange={setAlpha} />
          <DateField lang={lang} label={tx(lang, "事件期开始", "Event start")} value={eventStart} onChange={setEventStart} />
          <DateField lang={lang} label={tx(lang, "事件期结束", "Event end")} value={eventEnd} onChange={setEventEnd} />
          <DateField lang={lang} label={tx(lang, "估计期开始", "Estimation start")} value={estimationStart} onChange={setEstimationStart} />
          <p className="plain-note">{tx(lang,"估计期结束自动设为事件期开始前一个交易日。FEVD 的 h 自动取主模态最高点与最低点之间的交易日数。","The estimation period ends on the trading day before the event. FEVD h is determined automatically from the trading-day interval between the selected-scale extrema.")}</p>
          <button className="primary compact" disabled={running || factors.size === 0} onClick={() => void run()}>{running ? tx(lang, "正在获取并计算…", "Fetching and calculating…") : tx(lang, "运行完整分析", "Run full analysis")}</button>
        </aside>
        <div>
          <div className="factor-head"><b>{tx(lang, `解释变量（已选 ${factors.size}）`, `Explanatory variables (${factors.size} selected)`)}</b><div><button onClick={() => setFactors(new Set(eligible.map((item) => item.id)))}>{tx(lang, "全选", "Select all")}</button><button onClick={() => setFactors(new Set())}>{tx(lang, "清空", "Clear")}</button></div></div>
          <div className="factor-grid">{eligible.map((item) => <label key={item.id} className={factors.has(item.id) ? "active" : ""}><input type="checkbox" checked={factors.has(item.id)} onChange={() => toggleFactor(item.id)} /><span><b>{seriesText(item, lang).name}</b><small>{item.source} · {item.id}</small></span></label>)}</div>
          {error && <StatusPanel error text={tx(lang, `分析未完成：${error}`, `Analysis did not complete: ${error}`)} />}
          {!result && !error && <StatusPanel text={tx(lang, "设置参数后运行；结果区只接受真实接口返回。", "Configure and run the model. The result area accepts verified API output only.")} />}
          {result && <>
            <h3 className="result-title">A · {tx(lang,"方法、样本与事件窗口","Method, sample and event window")}</h3>
            <div className="metric-table"><span><b>{tx(lang,"共同样本","Aligned observations")}</b>{result.observations}</span><span><b>{tx(lang,"估计期","Estimation window")}</b>{result.estimationWindow.start} — {result.estimationWindow.end}</span><span><b>{tx(lang,"事件期","Event window")}</b>{result.eventWindow.start} — {result.eventWindow.end}</span><span><b>R²</b>{result.rSquared.toFixed(3)}</span><span><b>{tx(lang,"数据截止","As of")}</b>{result.asOf}</span></div>
            <p className="plain-note">{tx(lang,"估计期用于建立基准关系，事件期用于识别主模态极值和净影响；两者不会混用。","The estimation window establishes the baseline; the event window identifies selected-scale extrema and net impact. They are kept separate.")}</p>
            <h3 className="result-title">B · {tx(lang,"VMD 分解与 HHT 时频诊断","VMD decomposition and HHT time-frequency diagnostics")}</h3><ScaleCard lang={lang} components={result.components} /><HhtChart lang={lang} data={result.hht}/>
            <h3 className="result-title">C · {tx(lang,"主模态选择与事件期净影响","Selected-scale choice and event-window net impact")}</h3>
            <div className="metric-table"><span><b>{tx(lang,"主模态","Selected scale")}</b>{result.scaleEffect.selectedScale}</span><span><b>{tx(lang,"最低点","Minimum")}</b>{result.scaleEffect.minimumDate} · {result.scaleEffect.minimumValue.toFixed(3)}</span><span><b>{tx(lang,"最高点","Maximum")}</b>{result.scaleEffect.maximumDate} · {result.scaleEffect.maximumValue.toFixed(3)}</span><span><b>FEVD h</b>{result.scaleEffect.tradingDayInterval} {tx(lang,"个交易日","trading days")}</span><span><b>{tx(lang,"原始油价波幅","Original oil-price range")}</b>{result.scaleEffect.originalResponse.toFixed(3)} USD/bbl</span><span><b>{tx(lang,"净影响值","Net impact value")}</b>{result.scaleEffect.netEffect.toFixed(3)} USD/bbl</span><span><b>{tx(lang,"净影响占比","Net-impact share")}</b>{result.scaleEffect.shareInOriginalResponse.toFixed(3)}%</span></div>
            <h3 className="result-title">D · {tx(lang,"多分辨率格兰杰检验","Multiresolution Granger tests")}</h3>
            <ScaleGrangerMatrix lang={lang} data={result.scaleGranger}/>
            <details className="diagnostic"><summary>{tx(lang,"查看全样本格兰杰与当期 OLS 辅助诊断（不作为净影响主结果）","View full-sample Granger and current OLS diagnostics (not the net-impact result)")}</summary><GrangerChart lang={lang} data={result.granger} alpha={alpha} /><div className="granger-table">{result.granger.map((row) => <div key={row.id}><b>{lang === "zh" ? row.nameZh : row.nameEn}</b><span>lag {row.lag}</span><span>F {row.fStatistic.toFixed(3)}</span><span>p {row.pValue.toFixed(3)}</span><em className={row.significant ? "yes" : ""}>{row.significant ? tx(lang,"通过","Pass") : tx(lang,"未通过","Not significant")}</em></div>)}</div><DriverChart lang={lang} data={result.drivers}/></details>
            <h3 className="result-title">E · {tx(lang,`正交 VAR-FEVD 贡献与滚动冲击来源（自动 h=${result.fevdHorizon}）`,`Orthogonal VAR-FEVD contributions and rolling shock sources (automatic h=${result.fevdHorizon})`)}</h3><FevdChart lang={lang} data={result.fevd}/>
            <div className="metric-table"><span><b>{tx(lang,"油价自身冲击份额","Oil-price own-shock share")}</b>{result.fevdOwnShare.toFixed(3)}%</span><span><b>{tx(lang,"外部因素冲击份额","External-factor shock share")}</b>{(100-result.fevdOwnShare).toFixed(3)}%</span></div>
            <div className="impact-values">{result.fevd.map((row)=><span key={row.id}><b>{lang==="zh"?row.nameZh:row.nameEn}</b><em>{row.absoluteImpact>=0?"+":""}{row.absoluteImpact.toFixed(3)} USD/bbl</em><small>{row.externalWeight.toFixed(3)}% {tx(lang,"的外部净影响","of external net impact")}</small></span>)}</div>
            <RollingFevdChart lang={lang} data={result.rollingFevd}/>
            <h3 className="result-title">F · {tx(lang,"结构断点诊断：事件起点检验与最优断点复核","Structural-break diagnostics: event-start test and optimal-break review")}</h3><BreakChart lang={lang} data={result.breakTest.optimal.profile}/>
            <div className="metric-table"><span><b>{tx(lang,"指定断点","Specified break")}</b>{result.breakTest.fixed.breakDate}</span><span><b>F / p</b>{result.breakTest.fixed.fStatistic.toFixed(3)} / {result.breakTest.fixed.pValue.toFixed(3)}</span><span><b>{tx(lang,"水平突变","Level shift")}</b>{result.breakTest.fixed.levelShift.toFixed(3)}</span><span><b>{tx(lang,"趋势变化","Slope change")}</b>{result.breakTest.fixed.slopeChange.toFixed(3)}</span><span><b>{tx(lang,"最优候选断点","Best candidate break")}</b>{result.breakTest.optimal.bestDate}</span><span><b>{tx(lang,"分段RSS改善","Segmented RSS improvement")}</b>{result.breakTest.optimal.rssImprovementPercent.toFixed(3)}%</span></div>
            <div className="provenance"><Database/><span><b>{tx(lang,"本次数据血缘","Data provenance")}</b><small>{result.sources.map((s) => `${lang === "zh" ? s.nameZh : s.nameEn} [${s.id === "GPRD" ? "Caldara-Iacoviello:GPRD" : `FRED:${s.providerId}`}]`).join(" · ")}</small></span></div>
          </>}
          <div className="method-steps">
            <span>{tx(lang, "A 方法、样本与事件窗口", "A Method, sample and event window")}</span>
            <span>{tx(lang, `B VMD 与 HHT（${imf} 个分量）`, `B VMD and HHT (${imf} components)`)}</span>
            <span>{tx(lang, "C 主模态选择、极值与净影响", "C Selected scale, extrema and net impact")}</span>
            <span>{tx(lang, "D 多分辨率格兰杰检验", "D Multiresolution Granger tests")}</span>
            <span>{tx(lang, "E 正交 VAR-FEVD 贡献", "E Orthogonal VAR-FEVD contributions")}</span>
            <span>{tx(lang, "F 结构断点诊断", "F Structural-break diagnostics")}</span>
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
      </div>
      <button className="primary compact" onClick={() => void run()}>{running ? tx(lang, "模型运行中…", "Model running…") : tx(lang, "用最新数据运行模型", "Run on latest data")}</button>
      {error && <StatusPanel error text={tx(lang,`预测未完成：${error}`,`Forecast did not complete: ${error}`)}/>} {!liveData.length && !error && <StatusPanel text={tx(lang,"运行后展示真实历史、预测与滚动验证结果。","Run the model to display verified history, forecasts and rolling validation.")}/>} {liveData.length > 0 && <ForecastChart data={liveData} lang={lang} />}
      {liveData.length > 0 && <div className="metric-table">
        <span>
          <b>MAE</b> {metrics.ValidationMAE?.toFixed?.(3)}
        </span>
        <span>
          <b>RMSE</b> {metrics.ValidationRMSE?.toFixed?.(3)}
        </span>
        <span>
          <b>{tx(lang, "方向准确率", "Directional accuracy")}</b> {metrics.DirectionalAccuracyPercent?.toFixed?.(3)}%
        </span>
        <span>
          <b>{tx(lang, "80%区间验证覆盖率", "80% validation coverage")}</b> {metrics.IntervalCoveragePercent?.toFixed?.(3)}%
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
        </aside>
        <div>
          {error && <StatusPanel error text={tx(lang,`预警未完成：${error}`,`Warning run did not complete: ${error}`)}/>} {!liveRisk && !error && <StatusPanel text={tx(lang,"运行后展示基于真实价格序列计算的历史风险分位。","Run the model to display historical risk percentiles calculated from the official price series.")}/>} {liveRisk && <><RiskChart lang={lang} data={liveRisk.history} threshold={threshold} />
          <div className="metric-table">
            <span>
              <b>{tx(lang, "当前风险分位", "Current risk percentile")}</b> {liveRisk.riskScore.toFixed(3)}
            </span>
            <span>
              <b>{tx(lang, "距离用户阈值", "Distance to user threshold")}</b> {(liveRisk.riskScore-threshold).toFixed(3)}
            </span>
            <span><b>{tx(lang,"历史90%触发阈值","Historical 90% trigger")}</b>{liveRisk.alertThreshold.toFixed(3)}</span>
            <span><b>{tx(lang,"数据截止","As of")}</b>{liveRisk.latestDate}</span>
          </div></>}
        </div>
      </div>
    </Card>
  );
}

function parseUploadDate(value: unknown): string | null {
  if (value instanceof Date && !Number.isNaN(value.getTime())) return value.toISOString().slice(0,10);
  if (typeof value === "number") {
    const stamp = new Date(Date.UTC(1899,11,30) + Math.round(value)*86400000);
    return Number.isNaN(stamp.getTime()) ? null : stamp.toISOString().slice(0,10);
  }
  const stamp = new Date(String(value ?? "").trim());
  return Number.isNaN(stamp.getTime()) ? null : stamp.toISOString().slice(0,10);
}

function parseUploadNumber(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  const raw = String(value ?? "").trim(); if (!raw) return null;
  const percent = raw.endsWith("%"); const parsed = Number(raw.replace(/[%,$¥\s]/g,""));
  return Number.isFinite(parsed) ? (percent ? parsed/100 : parsed) : null;
}

async function readUploadedSeries(file: File) {
  let rows: unknown[][] = [];
  if (file.name.toLowerCase().endsWith(".csv")) {
    rows = (await file.text()).split(/\r?\n/).map((line)=>line.split(/,(?=(?:[^\"]*\"[^\"]*\")*[^\"]*$)/).map((cell)=>cell.replace(/^\"|\"$/g,"").replace(/\"\"/g,"\"")));
  } else {
    const { default: ExcelJS } = await import("exceljs");
    const workbook = new ExcelJS.Workbook();
    await workbook.xlsx.load(await file.arrayBuffer());
    const sheet = workbook.worksheets[0];
    if (!sheet) throw new Error(`${file.name}: workbook has no worksheet`);
    sheet.eachRow({includeEmpty:false},(row)=>rows.push([row.getCell(1).value,row.getCell(2).value]));
  }
  const points = rows.flatMap((row)=>{const dateValue=parseUploadDate(row[0]); const numberValue=parseUploadNumber(row[1]); return dateValue&&numberValue!=null?[{date:dateValue,value:numberValue}]:[]}).sort((a,b)=>a.date.localeCompare(b.date));
  if (points.length < 5) throw new Error(`${file.name}: fewer than five valid Date/Value rows`);
  const base=file.name.replace(/\.[^.]+$/,"").replace(/[^A-Za-z0-9_\u4e00-\u9fff]+/g,"_").replace(/^_+|_+$/g,"")||"UploadedSeries";
  return {id:`UPLOAD-${base}-${file.size}`,name:base,points};
}

function DataCenter({ lang }: { lang: Lang }) {
  const [tab, setTab] = useState<"factors" | "products">("factors");
  return <div className="page data-center-page">
    <PageIntro
      eyebrow={tx(lang,"Data intelligence","Data intelligence")}
      title={tx(lang,"把数据与交易工具放在同一个工作台","A workspace for data and market instruments")}
      desc={tx(lang,"变量因素查询连接 FRED、EIA 与官方 GPRD；金融产品查询连接交易所规格与 AKShare 所采用的新浪行情接口。","Factor search connects FRED, EIA and official GPRD. Product search combines exchange specifications with the Sina quote interface documented by AKShare.")}
    />
    <div className="pro-tabs data-tabs" role="tablist">
      <button role="tab" aria-selected={tab==="factors"} className={tab==="factors"?"active":""} onClick={()=>setTab("factors")}><Database/>{tx(lang,"变量因素查询","Factor & variable search")}</button>
      <button role="tab" aria-selected={tab==="products"} className={tab==="products"?"active":""} onClick={()=>setTab("products")}><CircleDollarSign/>{tx(lang,"金融产品查询","Financial product search")}</button>
    </div>
    {tab === "factors" ? <DataLab lang={lang}/> : <ProductLab lang={lang}/>}
  </div>;
}

function ProductLab({ lang }: { lang: Lang }) {
  const [q,setQ]=useState("");
  const [products,setProducts]=useState<InstrumentProduct[]>([]);
  const [response,setResponse]=useState<InstrumentResponse|null>(null);
  const [loading,setLoading]=useState(true);
  const [error,setError]=useState("");
  useEffect(()=>{let active=true;const timer=window.setTimeout(()=>{setLoading(true);setError("");void fetchInstruments(q.trim()?{q:q.trim(),directory:1}:{directory:1}).then((payload:InstrumentResponse)=>{if(active){setResponse(payload);setProducts(payload.products);}}).catch((reason)=>{if(active)setError(reason instanceof Error?reason.message:String(reason));}).finally(()=>{if(active)setLoading(false);});},q?280:0);return()=>{active=false;window.clearTimeout(timer);};},[q]);
  return <Card title={tx(lang,"金融产品查询","Financial product search")} desc={tx(lang,"可按代码、名称、资产类别或交易所检索原油、贵金属、天然气、利率、股票、波动率与全球商品目录。公开行情只作参考，具体合约月份、乘数与保证金须以交易所或经纪商为准。","Search crude oil, metals, natural gas, rates, equities, volatility and global commodities by code, name, asset class or exchange. Public quotes are indicative; confirm expiry, multiplier and margin with the exchange or broker.")} action={<span className="data-badge">{loading?tx(lang,"正在更新目录…","Refreshing directory…"):tx(lang,`${products.length} 个产品族`,`${products.length} product families`)}</span>}>
    <div className="search"><Search/><input value={q} onChange={(event)=>setQ(event.target.value)} placeholder={tx(lang,"输入黄金、铜、VIX、国债、天然气、GC……","Search gold, copper, VIX, Treasury, natural gas, GC…")}/></div>
    {error&&<StatusPanel error text={tx(lang,`金融产品接口不可用：${error}`,`Product feed unavailable: ${error}`)}/>}
    {!error&&<div className="instrument-directory">{products.map((product)=><article key={product.id}>
      <div className="instrument-code"><span>{product.exchange}</span><b>{product.code}</b></div>
      <h3>{lang==="zh"?product.nameZh||product.name:product.name}</h3>
      <p>{product.kind==="future"?tx(lang,"期货","Future"):tx(lang,"期权","Option")} · {product.benchmark} · {product.size.toLocaleString()} {product.contractUnit||"bbl"} · {product.settlement}</p>
      <dl><div><dt>{tx(lang,"最新参考价","Indicative last")}</dt><dd>{product.quote?`${product.quote.last.toFixed(3)} USD`:tx(lang,"需在经纪商复核","Broker check required")}</dd></div><div><dt>{tx(lang,"买一 / 卖一","Bid / ask")}</dt><dd>{product.quote?`${product.quote.bid?.toFixed(3)??"—"} / ${product.quote.ask?.toFixed(3)??"—"}`:"—"}</dd></div><div><dt>{tx(lang,"行情时间","Quote time")}</dt><dd>{product.quote?`${product.quote.date} ${product.quote.time}`:"—"}</dd></div></dl>
      <a href={product.url} target="_blank" rel="noreferrer">{tx(lang,"查看交易所规格","Open exchange specification")} <ArrowRight/></a>
    </article>)}</div>}
    {!loading&&!error&&!products.length&&<div className="empty-search">{tx(lang,"没有匹配产品。可尝试品种代码、英文基准或交易所名称。","No matched products. Try a product code, benchmark or exchange name.")}</div>}
    <div className="broker-note"><Radio/><div><b>{tx(lang,"行情与规格分层校验","Layered quote and specification checks")}</b><p>{response?.quoteMethod} {response?.quoteWarning?tx(lang,`当前行情提示：${response.quoteWarning}`,`Quote warning: ${response.quoteWarning}`):tx(lang,"公开行情接口已响应；正式下单仍需在经纪商中确认具体月份、权利金和保证金。","The public quote feed responded. Confirm expiry, option premium and margin in the broker ticket before trading.")}</p></div></div>
  </Card>;
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
  const [uploadStatus, setUploadStatus] = useState("");
  const [discovery, setDiscovery] = useState<"idle"|"searching"|"ready"|"error">("idle");
  const [discoveredIds, setDiscoveredIds] = useState<Set<string>>(new Set());
  const [savedIds, setSavedIds] = useState<Set<string>>(
    () => new Set(readLocalRecords().filter((record) => record.kind === "series").map((record) => record.id)),
  );
  useEffect(() => {
    let active = true;
    void fetchCatalog()
      .then((items) => {
        if (!active || !items.length) return;
        const base = items as unknown as DataSeries[];
        const saved = readLocalRecords().filter((record)=>record.kind==="series").map((record)=>({id:record.id,name:String(record.payload.name||record.label),nameEn:String(record.payload.nameEn||record.label),category:String(record.payload.category||""),source:String(record.payload.source||"Manual upload"),unit:String(record.payload.unit||""),frequency:String(record.payload.frequency||""),updated:String(record.payload.updated||record.savedAt.slice(0,10)),color:String(record.payload.color||"#756fa5")}));
        const next = [...saved,...base.filter((item)=>!saved.some((record)=>record.id===item.id))];
        setLiveCatalog(next);
        setSources(new Set(next.map((item) => item.source)));
        setSelected((current) => next.some((item) => item.id === current) ? current : next[0].id);
      })
      .catch((reason) => setError(reason instanceof Error ? reason.message : String(reason)))
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, []);
  useEffect(() => {
    if (q.trim().length < 2) { setDiscovery("idle"); setDiscoveredIds(new Set()); return; }
    const timer = window.setTimeout(() => {
      setDiscovery("searching");
      void fetchCatalog(q.trim()).then((items) => {
        const discovered = items as unknown as DataSeries[];
        setDiscoveredIds(new Set(discovered.map((item)=>item.id)));
        setLiveCatalog((current) => [...current, ...discovered.filter((item) => !current.some((existing) => existing.id === item.id))]);
        setSources((current) => new Set([...current, ...discovered.map((item) => item.source)]));
        setDiscovery("ready");
      }).catch(() => setDiscovery("error"));
    }, 350);
    return () => window.clearTimeout(timer);
  }, [q]);
  useEffect(() => {
    if (!selected) return;
    let active = true;
    setLoading(true); setError(""); setLiveSeries([]); setSeriesLive(false);
    const saved = readLocalRecords().find((record)=>record.id===selected && Array.isArray(record.payload.points));
    if (saved) {
      const points = saved.payload.points as Array<{date:string;value:number}>;
      setLiveSeries(frequency==="monthly" ? [...new Map(points.map((point)=>[point.date.slice(0,7),point])).values()] : points); setSeriesLive(true); setLoading(false);
      return () => { active=false; };
    }
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
    (x) => {
      const needle = q.trim().toLowerCase();
      const haystack = [x.name, x.nameEn, x.id, x.source, x.category, x.unit, x.frequency]
        .filter(Boolean)
        .join(" ")
        .toLowerCase();
      return sources.has(x.source) && (haystack.includes(needle) || discoveredIds.has(x.id));
    },
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
        payload: { source: item.source, category:item.category, unit: item.unit, frequency: item.frequency, name: item.name, nameEn: item.nameEn || item.name, color: item.color, points: liveSeries },
    });
    setSavedIds((current) => new Set([...current, selected]));
  };
  const uploadFiles = async (files: FileList | null) => {
    if (!files?.length) return; setUploadStatus(""); setError("");
    try {
      const parsed = await Promise.all([...files].map(readUploadedSeries));
      const added = parsed.map((item,index)=>({id:item.id,name:item.name,nameEn:item.name,category:tx(lang,"手动上传","Manual upload"),source:tx(lang,"手动上传","Manual upload"),unit:"",frequency:tx(lang,"用户提供","User supplied"),updated:item.points.at(-1)!.date,color:["#9b6d51","#5f7895","#756fa5"][index%3]}));
      parsed.forEach((item,index)=>saveLocalRecord({id:item.id,kind:"series",label:item.name,payload:{...added[index],points:item.points}}));
      setLiveCatalog((current)=>[...added,...current.filter((row)=>!added.some((item)=>item.id===row.id))]);
      setSources((current)=>new Set([...current,...added.map((item)=>item.source)])); setSelected(added[0].id); setLiveSeries(parsed[0].points); setSeriesLive(true);
      setUploadStatus(tx(lang,`已校验并加入研究库：${added.map((item)=>item.name).join("、")}`,`Validated and added to the research library: ${added.map((item)=>item.name).join(", ")}`));
    } catch (reason) { setError(reason instanceof Error?reason.message:String(reason)); }
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
  const chartValues=liveSeries.map((point)=>point.value).filter(Number.isFinite);
  const chartMinimum=chartValues.length?Math.min(...chartValues):0;
  const chartMaximum=chartValues.length?Math.max(...chartValues):1;
  const chartPadding=Math.max((chartMaximum-chartMinimum)*.08,Math.abs(chartMaximum)*.01,.001);
  return (
    <Card
      title={tx(lang, "变量因素查询", "Factor & variable search")}
      desc={tx(lang, "FRED、EIA 与 Caldara-Iacoviello GPRD 默认全选；选择序列后可预览、下载或加入变量池。", "FRED, EIA and Caldara-Iacoviello GPRD are enabled by default. Preview, download or add any series to the variable pool.")}
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
      <div className="upload-row"><label className="upload-button"><Upload/>{tx(lang,"上传 CSV / XLSX 变量","Upload CSV / XLSX variables")}<input type="file" accept=".csv,.xlsx" multiple onChange={(event)=>void uploadFiles(event.target.files)}/></label><span>{tx(lang,"前两列必须为日期和值；允许标题或备注行。上传后可直接加入净影响分析。","The first two columns must be Date and Value; title rows are allowed. Uploaded series can be used directly in net-impact analysis.")}</span></div>
      {uploadStatus && <div className="upload-success">{uploadStatus}</div>}
      <div className="search">
        <Search />
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder={tx(lang, "输入 Brent、库存、美元、利率……", "Search Brent, inventories, dollar, rates…")}
        />
      </div>
      {q.trim().length >= 2 && <div className="search-state">{discovery === "searching" ? tx(lang,"正在对 FRED 全文目录、EIA 分层目录与官方 GPRD 做模糊检索…","Fuzzy-searching the FRED catalog, EIA hierarchy and official GPRD…") : discovery === "error" ? tx(lang,"官方目录暂时没有响应，请稍后重试。","The official directories did not respond. Please retry shortly.") : discovery === "ready" ? tx(lang,`找到 ${found.length} 个可用序列；选中并加入变量池后，会出现在净影响分析和决策高级设置中。`,`${found.length} available series found. Add one to the variable pool to use it in net-impact analysis and Decision advanced settings.`) : ""}</div>}
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
          {!loading && found.length === 0 && <div className="empty-search">{tx(lang,"没有匹配项。可以换用英文缩写或更宽泛的关键词，例如 inventory、dollar、rate。","No matches. Try an English abbreviation or a broader term such as inventory, dollar or rate.")}</div>}
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
            <button className={savedIds.has(selected) ? "saved" : ""} onClick={save} disabled={!seriesLive || savedIds.has(selected)}>
              <Save />
              {savedIds.has(selected) ? tx(lang, "已加入变量池", "Added to variable pool") : tx(lang, "加入变量池", "Add to variable pool")}
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
                <YAxis domain={[chartMinimum-chartPadding,chartMaximum+chartPadding]} tick={{ fontSize: 10 }} tickFormatter={(value)=>Number(value).toFixed(3)} />
                <Tooltip formatter={(value)=>Number(value).toFixed(3)} />
                <Line
                  dataKey="value"
                  stroke="#6f69a2"
                  strokeWidth={2.4}
                  dot={false}
                  isAnimationActive={false}
                />
                <Brush dataKey="date" height={20} stroke="#6f69a2" />
              </LineChart>
            </ResponsiveContainer>
          </div></ChartFrame>}
          <div className="provenance">
            <Database />
            <span>
              <b>{liveCatalog.find((x) => x.id === selected)?.source}</b> ·{" "}
              <span className="series-identifier" title={selected}>{selected.length > 58 ? `${selected.slice(0, 34)}…${selected.slice(-14)}` : selected}</span>
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
