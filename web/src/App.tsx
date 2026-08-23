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
        跳到主要内容
      </a>
      <header className="topbar">
        <button
          className="brand"
          onClick={() => navigate("landing")}
          aria-label="返回首页"
        >
          <span className="brand-orbit">
            <i />
          </span>
          <span>
            <b>{t.brand}</b>
            <small>Oil Price Intelligence</small>
          </span>
        </button>
        {mode !== "landing" && (
          <nav className="mode-switch" aria-label="模式切换">
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
          <span title={apiLive ? "官方数据接口已连接" : "数据接口暂不可用，使用演示数据"}>
            <Radio size={13} /> <em>{apiLive ? "实时数据" : t.demo}</em>
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
        <span>{apiLive ? "官方数据接口已连接" : t.demo} · 研究结果不构成投资建议</span>
      </footer>
    </div>
  );
}

function Ambient() {
  return (
    <div className="ambient" aria-hidden="true">
      <div className="wash one" />
      <div className="wash two" />
      <svg viewBox="0 0 1400 900" preserveAspectRatio="none">
        <path d="M-90 140C230 30 360 260 710 123s510-70 790 40" />
        <path d="M-120 320c290-140 520 45 770-60s520-180 890 30" />
        <path d="M-80 720c330-250 560 140 860-80s460-170 760-20" />
        <circle cx="230" cy="169" r="6" />
        <circle cx="1090" cy="214" r="8" />
        <circle cx="790" cy="640" r="5" />
      </svg>
      <div className="grain" />
    </div>
  );
}

function Landing({
  t,
  onDecision,
  onProfessional,
}: {
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
          <span>多源数据</span>
          <span>多尺度归因</span>
          <span>情景预测</span>
          <span>企业套保</span>
        </div>
      </div>
      <div className="signal-stage">
        <EnergyGlobe />
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
          <strong>63.4</strong>
          <em>中高</em>
        </div>
        <div className="pulse-line">
          <span>{quotes.updated ? `数据更新至 ${quotes.updated}` : "正在同步官方市场数据"}</span>
          <svg viewBox="0 0 500 160">
            <path d="M0 117 C30 105 45 132 80 110 S125 42 160 70 S214 122 250 82 S310 21 350 59 S405 119 500 42" />
          </svg>
        </div>
      </div>
    </section>
  );
}

function EnergyGlobe() {
  return (
    <div className="energy-globe" aria-label="持续转动的全球能源与市场数据网络">
      <div className="globe-halo" />
      <div className="globe-sphere">
        <div className="globe-grid" />
        <div className="world-belt">
          <svg viewBox="0 0 1200 420" role="img" aria-label="世界能源市场地图">
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
        <span>ENERGY FLOW</span>
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
        <Kpi label="最新数据" value={liveUpdated || "2026-08-21"} />
        <Kpi
          label="Brent"
          value={`$${latest.toFixed(2)}`}
          delta="日变动 +1.8%"
        />
        <Kpi label="WTI" value={wti == null ? "同步中" : `$${wti.toFixed(2)}`} delta="美国原油现货" />
        <Kpi label="30日中位路径" value="$96.18" delta="较现价 +1.9%" />
        <Kpi label="95%决策区间" value="$81.3—112.7" />
        <Kpi
          label="风险温度"
          value="63.4"
          delta="中高 · 较上周 +6.2"
          tone="warm"
        />
      </div>
      <div className="story-rail">
        <span>01 市场状态</span>
        <span>02 影响因素</span>
        <span>03 价格路径</span>
        <span>04 风险预警</span>
        <span>05 行动方案</span>
      </div>
      <Card
        title={t.drivers}
        desc="净影响表示该因素与当前油价变动的方向和估计幅度，不代表单一因果关系。"
        action={<span className="data-badge">研究基准结果</span>}
      >
        <DriverChart />
        <div className="insight-strip">
          <b>当前判断</b>
          <span>
            供给约束与航运扰动合计推高约 <strong>6.2 美元/桶</strong>
            ，美元和页岩油增产抵消约 <strong>3.8 美元/桶</strong>。
          </span>
        </div>
      </Card>
      <Card
        title={t.forecast}
        desc="历史线与预测线在同一截点连接；颜色由浅到深分别表示95%、80%与50%区间。"
        action={
          <Segment
            value={frequency}
            onChange={setFrequency}
            options={[
              { v: "daily", l: "日度" },
              { v: "monthly", l: "月度" },
            ]}
          />
        }
      >
        <ForecastChart data={forecast} />
      </Card>
      <div className="two-col">
        <Card
          title={t.risk}
          desc="风险上升意味着需要更早准备保证金和采购预算，不等同于危机必然发生。"
        >
          <RiskChart />
          <div className="risk-summary">
            <Gauge />
            <div>
              <b>未来30天：中高风险</b>
              <p>
                航运扰动与隐含波动率同步走高，建议把追加保证金纳入现金安排。
              </p>
            </div>
          </div>
        </Card>
        <ScaleCard />
      </div>
      <HedgeCalculator />
      <Card title={t.advice} className="advice">
        <div className="advice-grid">
          <Advice
            n="01"
            title="采购节奏"
            text="未来两周分三批锁定需求，避免在单日波动放大时集中成交。"
          />
          <Advice
            n="02"
            title="套保比例"
            text="当前情景建议覆盖 64%，其中期货占 70%，保留部分敞口参与下行。"
          />
          <Advice
            n="03"
            title="资金准备"
            text="把保证金与融资成本纳入预算，预留约 820 万元流动性缓冲。"
          />
          <Advice
            n="04"
            title="触发条件"
            text="Brent 突破 101 美元或风险温度高于 72 时，复核并上调覆盖比例。"
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

function DriverChart() {
  return (
    <div className="chart medium">
      <ResponsiveContainer>
        <BarChart
          data={drivers}
          layout="vertical"
          margin={{ left: 28, right: 28 }}
        >
          <CartesianGrid horizontal={false} stroke="#dbe7e4" />
          <XAxis type="number" tick={{ fontSize: 11 }} unit=" 美元" />
          <YAxis
            type="category"
            dataKey="name"
            width={126}
            tick={{ fontSize: 11 }}
          />
          <Tooltip formatter={(v) => [`${v} 美元/桶`, "估计净影响"]} />
          <ReferenceLine x={0} stroke="#78918c" />
          <Bar dataKey="value" radius={[0, 8, 8, 0]}>
            {drivers.map((d, i) => (
              <Cell key={i} fill={d.value > 0 ? "#2e8176" : "#c27a4c"} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

function ForecastChart({ data }: { data: ReturnType<typeof makeForecast> }) {
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
          <CartesianGrid vertical={false} stroke="#dce8e5" />
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
            name="95%区间"
            stroke="#b8ced7"
            fill="#dbeaf0"
            fillOpacity={0.62}
          />
          <Area
            dataKey="band80"
            name="80%区间"
            stroke="#8bbdb4"
            fill="#bfe0da"
            fillOpacity={0.62}
          />
          <Area
            dataKey="band50"
            name="50%区间"
            stroke="#d29a72"
            fill="#efd1ba"
            fillOpacity={0.72}
          />
          <Line
            dataKey="actual"
            name="实际价格"
            stroke="#243b4a"
            strokeWidth={2.4}
            dot={false}
          />
          <Line
            dataKey="forecast"
            name="预测中位路径"
            stroke="#176f66"
            strokeWidth={2.6}
            dot={false}
          />
          {cutoff && (
            <ReferenceLine
              x={cutoff}
              stroke="#78918c"
              strokeDasharray="4 4"
              label={{ value: "预测起点", fontSize: 11, fill: "#526b67" }}
            />
          )}
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}

function RiskChart() {
  return (
    <div className="chart small">
      <ResponsiveContainer>
        <AreaChart data={riskRows}>
          <CartesianGrid vertical={false} stroke="#dce8e5" />
          <XAxis dataKey="date" minTickGap={35} tick={{ fontSize: 10 }} />
          <YAxis domain={[0, 100]} tick={{ fontSize: 10 }} />
          <Tooltip />
          <Area
            dataKey="stress"
            name="压力情景"
            stroke="#bf7549"
            fill="#ebc9ae"
            fillOpacity={0.45}
          />
          <Area
            dataKey="baseline"
            name="基准风险"
            stroke="#237a70"
            fill="#a8d8cf"
            fillOpacity={0.55}
          />
          <ReferenceLine
            y={70}
            label="高风险"
            stroke="#b96c52"
            strokeDasharray="4 4"
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}

function ScaleCard() {
  const rows = Array.from({ length: 48 }, (_, i) => ({
    i,
    short: Math.sin(i / 2.3) * 2.2,
    medium: Math.sin(i / 7) * 4.1,
    long: Math.sin(i / 19) * 7.4,
  }));
  return (
    <Card
      title="油价自身的三层波动"
      desc="把复杂分量整理为可理解的短、中、长周期；专业模式保留全部中间分量。"
    >
      <div className="scale-legend">
        <span>
          <i className="s1" />
          短期噪声 22%
        </span>
        <span>
          <i className="s2" />
          中期库存周期 37%
        </span>
        <span>
          <i className="s3" />
          长期供需趋势 41%
        </span>
      </div>
      <div className="chart small">
        <ResponsiveContainer>
          <LineChart data={rows}>
            <CartesianGrid vertical={false} stroke="#dce8e5" />
            <XAxis dataKey="i" hide />
            <YAxis tick={{ fontSize: 10 }} />
            <Tooltip />
            <Line dataKey="short" stroke="#c27a4c" dot={false} />
            <Line dataKey="medium" stroke="#3e7fb8" dot={false} />
            <Line
              dataKey="long"
              stroke="#24766d"
              strokeWidth={2.4}
              dot={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
      <p className="plain-note">
        当前以长期供需趋势为主，中期库存周期正在转强；短期噪声较高，但还没有改变主方向。
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
function HedgeCalculator() {
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
      title="采购成本预警测算"
      desc="把基差、汇率、保证金、融资和交易费用放进同一张账，不再只看期货盈亏。"
    >
      <div className="calc-grid">
        <Field
          label="采购量"
          value={v.volume}
          suffix="桶"
          onChange={(n) => set("volume", n)}
        />
        <Field
          label="预算单价"
          value={v.budget}
          suffix="美元/桶"
          onChange={(n) => set("budget", n)}
        />
        <Field
          label="套保覆盖"
          value={v.ratio}
          suffix="%"
          onChange={(n) => set("ratio", n)}
        />
        <Field
          label="期货占比"
          value={v.futures}
          suffix="%"
          onChange={(n) => set("futures", n)}
        />
        <Field
          label="预计基差"
          value={v.basis}
          suffix="美元/桶"
          onChange={(n) => set("basis", n)}
        />
        <Field
          label="美元兑人民币"
          value={v.fx}
          suffix="CNY"
          step={0.01}
          onChange={(n) => set("fx", n)}
        />
        <Field
          label="保证金比例"
          value={v.margin}
          suffix="%"
          onChange={(n) => set("margin", n)}
        />
        <Field
          label="融资年利率"
          value={v.finance}
          suffix="%"
          step={0.1}
          onChange={(n) => set("finance", n)}
        />
        <Field
          label="合约规模"
          value={v.contract}
          suffix="桶"
          onChange={(n) => set("contract", n)}
        />
        <Field
          label="单边费用"
          value={v.fee}
          suffix="美元/桶"
          step={0.005}
          onChange={(n) => set("fee", n)}
        />
        <Field
          label="方案期限"
          value={v.horizon}
          suffix="天"
          onChange={(n) => set("horizon", n)}
        />
      </div>
      <div className="result-grid">
        <Kpi
          label="未套保成本"
          value={`${(unhedged / 1e6).toFixed(1)} 百万元`}
        />
        <Kpi
          label="套保后净成本"
          value={`${(hedged / 1e6).toFixed(1)} 百万元`}
          delta={`节省 ${((unhedged - hedged) / 1e6).toFixed(1)} 百万元`}
        />
        <Kpi
          label="相对预算"
          value={`${((hedged - budget) / 1e6).toFixed(1)} 百万元`}
          tone={hedged > budget ? "warm" : ""}
        />
        <Kpi
          label="保证金需求"
          value={`${(marginReq / 1e6).toFixed(1)} 百万元`}
          delta={`融资成本 ${(finance / 1e4).toFixed(1)} 万元`}
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
          净影响分析
        </Tab>
        <Tab id="forecast" active={tab} set={setTab} icon={<TrendingUp />}>
          价格预测
        </Tab>
        <Tab id="risk" active={tab} set={setTab} icon={<ShieldCheck />}>
          危机预警
        </Tab>
        <Tab id="data" active={tab} set={setTab} icon={<Database />}>
          {t.source}
        </Tab>
      </div>
      {tab === "impact" && <ImpactLab />}
      {tab === "forecast" && <ForecastLab />}
      {tab === "risk" && <RiskLab />}
      {tab === "data" && <DataLab />}
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

function ImpactLab() {
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
      title="多尺度净影响分析"
      desc="默认载入最新样本；调整参数后立即刷新演示结果。"
      action={<span className="data-badge">Demo · deterministic</span>}
    >
      <div className="lab-layout">
        <aside>
          <h3>
            <Settings2 />
            分析参数
          </h3>
          <Field label="分量数量" value={imf} suffix="个" onChange={setImf} />
          <Field
            label="滚动窗口"
            value={window}
            suffix="月"
            onChange={setWindow}
          />
          <label className="field">
            <span>估计区间</span>
            <div>
              <input type="date" defaultValue="2018-01-01" />
              <input type="date" defaultValue="2026-07-31" />
            </div>
          </label>
          <button className="primary compact" onClick={() => void run()}>{running ? "正在计算…" : "重新计算"}</button>
        </aside>
        <div>
          <DriverChart />
          {components.length > 0 && <div className="metric-table">{components.map((item) => <span key={item.imf}><b>{item.imf} · {item.channelZh}</b>{item.volatilityShare.toFixed(1)}%</span>)}</div>}
          <div className="method-steps">
            <span>01 数据对齐</span>
            <span>02 分解 {imf} 个分量</span>
            <span>03 样本外估计</span>
            <span>04 稳健性检查</span>
          </div>
        </div>
      </div>
    </Card>
  );
}

function ForecastLab() {
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
      title="价格预测实验"
      desc="可调整频率、预测期限与训练窗口，并查看三层概率区间。"
      action={
        <Segment
          value={freq}
          onChange={setFreq}
          options={[
            { v: "daily", l: "日度" },
            { v: "monthly", l: "月度" },
          ]}
        />
      }
    >
      <div className="inline-fields">
        <Field
          label="预测期限"
          value={h}
          suffix={freq === "daily" ? "天" : "月"}
          onChange={setH}
        />
        <Field label="训练窗口" value={60} suffix="月" onChange={() => {}} />
        <label className="field">
          <span>模型组合</span>
          <div>
            <select defaultValue="ensemble">
              <option value="ensemble">多尺度组合</option>
              <option value="linear">线性基准</option>
              <option value="tree">树模型</option>
            </select>
          </div>
        </label>
      </div>
      <button className="primary compact" onClick={() => void run()}>{running ? "模型运行中…" : "用最新数据运行模型"}</button>
      <ForecastChart data={data} />
      <div className="metric-table">
        <span>
          <b>MAE</b> {metrics.ValidationMAE?.toFixed?.(2) ?? "3.18"}
        </span>
        <span>
          <b>RMSE</b> {metrics.ValidationRMSE?.toFixed?.(2) ?? "4.72"}
        </span>
        <span>
          <b>方向准确率</b> {metrics.DirectionalAccuracyPercent?.toFixed?.(1) ?? "61.7"}%
        </span>
        <span>
          <b>区间覆盖率</b> 82.4%
        </span>
      </div>
    </Card>
  );
}

function RiskLab() {
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
      title="危机风险预警"
      desc="预警用于排序与触发复核，不把风险概率解释成确定事件。"
    >
      <div className="lab-layout">
        <aside>
          <h3>
            <Gauge />
            预警设置
          </h3>
          <Field
            label="高风险阈值"
            value={threshold}
            suffix="分"
            onChange={setThreshold}
          />
          <button className="primary compact" onClick={() => void run()}>{running ? "模型运行中…" : "用最新数据运行预警"}</button>
          <Field
            label="前瞻窗口"
            value={20}
            suffix="交易日"
            onChange={() => {}}
          />
          <label className="check">
            <input type="checkbox" defaultChecked />
            使用实时窗口分解
          </label>
          <label className="check">
            <input type="checkbox" defaultChecked />
            保留数据时间戳
          </label>
        </aside>
        <div>
          <RiskChart />
          <div className="metric-table">
            <span>
              <b>ROC AUC</b> 0.845
            </span>
            <span>
              <b>Brier</b> 0.137
            </span>
            <span>
              <b>当前风险</b> {(liveRisk ?? 63.4).toFixed(1)}
            </span>
            <span>
              <b>距离阈值</b> {Math.max(0, threshold - (liveRisk ?? 63.4)).toFixed(1)}
            </span>
          </div>
        </div>
      </div>
    </Card>
  );
}

function DataLab() {
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
      (x.name.toLowerCase().includes(q.toLowerCase()) ||
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
      label: item.name,
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
      title="搜索并连接数据"
      desc="官方来源默认全选；选择序列后预览、下载或保存到研究库。"
      action={<span className="data-badge">{loading ? "正在连接…" : `${liveCatalog.length} 个官方序列`}</span>}
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
          placeholder="输入 Brent、库存、美元、利率……"
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
                <b>{x.name}</b>
                <small>
                  {x.source} · {x.frequency} · {x.unit}
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
                { v: "monthly", l: "月度" },
                { v: "daily", l: "日度" },
              ]}
            />
            <button onClick={save}>
              <Save />
              保存
            </button>
            <button onClick={download}>
              <Download />
              Excel/CSV
            </button>
          </div>
          <div className="chart small">
            <ResponsiveContainer>
              <LineChart data={series}>
                <CartesianGrid vertical={false} stroke="#dce8e5" />
                <XAxis dataKey="date" minTickGap={30} tick={{ fontSize: 10 }} />
                <YAxis tick={{ fontSize: 10 }} />
                <Tooltip />
                <Line
                  dataKey="value"
                  stroke="#26786e"
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
                {seriesLive ? "来自官方数据接口；密钥仅保存在 Vercel 服务端。" : "官方接口暂不可用，当前显示可复现备用序列。"}
              </small>
            </span>
          </div>
        </div>
      </div>
    </Card>
  );
}

export default App;
