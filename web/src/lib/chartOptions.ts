import type { CustomSeriesOption, EChartsOption } from "echarts";

export type ForecastChartRow = {
  date: string;
  actual?: number | null;
  median?: number | null;
  low50?: number | null;
  high50?: number | null;
  low80?: number | null;
  high80?: number | null;
  low95?: number | null;
  high95?: number | null;
};

type NormalizedForecastRow = Required<ForecastChartRow>;

const finiteOrNull = (value: number | null | undefined) => Number.isFinite(value) ? Number(value) : null;

export function normalizeForecastRows(rows: ForecastChartRow[]): NormalizedForecastRow[] {
  const normalized = rows.map((row) => ({
    date: row.date,
    actual: finiteOrNull(row.actual),
    median: finiteOrNull(row.median),
    low50: finiteOrNull(row.low50),
    high50: finiteOrNull(row.high50),
    low80: finiteOrNull(row.low80),
    high80: finiteOrNull(row.high80),
    low95: finiteOrNull(row.low95),
    high95: finiteOrNull(row.high95),
  }));
  const firstForecast = normalized.findIndex((row) => row.median !== null);
  if (firstForecast > 0) {
    const bridge = normalized[firstForecast - 1];
    if (bridge.actual !== null) bridge.median = bridge.actual;
  }
  return normalized;
}

const values = (rows: NormalizedForecastRow[], key: keyof NormalizedForecastRow) =>
  rows.map((row) => key === "date" ? row.date : row[key] as number | null);

function intervalSeries(
  rows: NormalizedForecastRow[],
  lowKey: "low50" | "low80" | "low95",
  highKey: "high50" | "high80" | "high95",
  name: string,
  color: string,
): CustomSeriesOption {
  const segments: number[][] = [];
  for (let index = 0; index < rows.length - 1; index += 1) {
    const current = rows[index];
    const next = rows[index + 1];
    if (current[lowKey] === null || current[highKey] === null || next[lowKey] === null || next[highKey] === null) continue;
    segments.push([index, current[lowKey], current[highKey], index + 1, next[lowKey], next[highKey]]);
  }
  return {
    name,
    type: "custom",
    coordinateSystem: "cartesian2d",
    dimensions: ["x0", "low0", "high0", "x1", "low1", "high1"],
    encode: { x: [0, 3], y: [1, 2, 4, 5] },
    data: segments,
    itemStyle: { color, opacity: 0.24 },
    renderItem: (_params, api) => {
      const points = [
        api.coord([api.value(0), api.value(1)]),
        api.coord([api.value(0), api.value(2)]),
        api.coord([api.value(3), api.value(5)]),
        api.coord([api.value(3), api.value(4)]),
      ];
      return {
        type: "polygon",
        shape: { points },
        style: api.style({ fill: color, stroke: color, lineWidth: 1, opacity: 0.24 }),
        silent: true,
      };
    },
    tooltip: { show: false },
    silent: true,
    z: 1,
  };
}

export function buildForecastOption(input: ForecastChartRow[], lang: "zh" | "en"): EChartsOption {
  const rows = normalizeForecastRows(input);
  const label = (zh: string, en: string) => lang === "zh" ? zh : en;
  return {
    animationDuration: 550,
    color: ["#96abc0", "#7e76ad", "#d28a63", "#252932", "#655d98"],
    grid: { left: 62, right: 34, top: 48, bottom: 78, containLabel: true },
    legend: { top: 4, type: "scroll", selected: {
      [label("95%区间", "95% interval")]: true,
      [label("80%区间", "80% interval")]: true,
      [label("50%区间", "50% interval")]: true,
      [label("实际价格", "Observed price")]: true,
      [label("中位预测", "Median forecast")]: true,
    } },
    toolbox: {
      right: 8,
      feature: { dataZoom: {}, restore: {}, saveAsImage: { pixelRatio: 2 } },
    },
    tooltip: {
      trigger: "axis",
      formatter: (params: unknown) => {
        const items = Array.isArray(params) ? params : [params];
        const dataIndex = Number((items[0] as { dataIndex?: number } | undefined)?.dataIndex ?? 0);
        const row = rows[dataIndex];
        if (!row) return "";
        const parts = [`<b>${row.date}</b>`];
        if (row.actual !== null) parts.push(`${label("实际价格", "Observed price")}: ${row.actual.toFixed(3)}`);
        if (row.median !== null) parts.push(`${label("中位预测", "Median forecast")}: ${row.median.toFixed(3)}`);
        const addRange = (rangeLabel: string, low: number | null, high: number | null) => {
          if (low !== null && high !== null) parts.push(`${rangeLabel}: ${low.toFixed(3)} – ${high.toFixed(3)}`);
        };
        addRange(label("50%区间", "50% interval"), row.low50, row.high50);
        addRange(label("80%区间", "80% interval"), row.low80, row.high80);
        addRange(label("95%区间", "95% interval"), row.low95, row.high95);
        return parts.join("<br/>");
      },
    },
    xAxis: { type: "category", boundaryGap: false, data: rows.map((row) => row.date), axisLabel: { hideOverlap: true } },
    yAxis: {
      type: "value",
      scale: true,
      name: label("美元/桶", "USD/bbl"),
      axisLabel: { formatter: (value: number) => value.toFixed(3) },
      splitLine: { lineStyle: { color: "#e8e3df" } },
    },
    dataZoom: [
      { type: "inside", filterMode: "none", zoomOnMouseWheel: true, moveOnMouseMove: true },
      { type: "slider", filterMode: "none", height: 24, bottom: 18, borderColor: "#d9d3cf" },
    ],
    series: [
      intervalSeries(rows, "low95", "high95", label("95%区间", "95% interval"), "#9fb8cc"),
      intervalSeries(rows, "low80", "high80", label("80%区间", "80% interval"), "#8179ad"),
      intervalSeries(rows, "low50", "high50", label("50%区间", "50% interval"), "#d38a61"),
      { name: label("实际价格", "Observed price"), type: "line", data: values(rows, "actual"), showSymbol: false, connectNulls: false, lineStyle: { width: 2.4, color: "#252932" }, itemStyle: { color: "#252932" }, z: 5 },
      { name: label("中位预测", "Median forecast"), type: "line", data: values(rows, "median"), showSymbol: false, connectNulls: false, lineStyle: { width: 2.8, color: "#655d98" }, itemStyle: { color: "#655d98" }, z: 6 },
    ],
  };
}

export type TimeSeriesRow = { date: string; [key: string]: string | number | null | undefined };

export function buildTimeSeriesOption(input: {
  rows: TimeSeriesRow[];
  series: Array<{ key: string; name: string; color: string; area?: boolean; stack?: string }>;
  yName?: string;
  yMin?: number;
  yMax?: number;
  threshold?: { value: number; name: string; color?: string };
}): EChartsOption {
  return {
    animationDuration: 480,
    grid: { left: 56, right: 34, top: 48, bottom: 72, containLabel: true },
    legend: { top: 4, type: "scroll" },
    toolbox: { right: 8, feature: { dataZoom: {}, restore: {}, saveAsImage: { pixelRatio: 2 } } },
    tooltip: { trigger: "axis", valueFormatter: (value) => Number(value).toFixed(3) },
    xAxis: { type: "category", boundaryGap: true, data: input.rows.map((row) => row.date), axisLabel: { hideOverlap: true, showMinLabel: true, showMaxLabel: true } },
    yAxis: {
      type: "value",
      scale: input.yMin === undefined && input.yMax === undefined,
      min: input.yMin,
      max: input.yMax,
      name: input.yName,
      axisLabel: { formatter: (value: number) => Number(value).toFixed(3) },
      splitLine: { lineStyle: { color: "#e8e3df" } },
    },
    dataZoom: [
      { type: "inside", filterMode: "none" },
      { type: "slider", filterMode: "none", height: 22, bottom: 16, borderColor: "#d9d3cf" },
    ],
    series: input.series.map((series, index) => ({
      type: "line" as const,
      name: series.name,
      data: input.rows.map((row) => Number.isFinite(row[series.key]) ? Number(row[series.key]) : null),
      showSymbol: false,
      smooth: false,
      stack: series.stack,
      lineStyle: { width: index === 0 ? 2.5 : 2, color: series.color },
      areaStyle: series.area ? { color: series.color, opacity: .22 } : undefined,
      markLine: index === 0 && input.threshold ? {
        symbol: "none",
        label: { formatter: input.threshold.name },
        lineStyle: { color: input.threshold.color || "#b36052", type: "dashed" },
        data: [{ yAxis: input.threshold.value }],
      } : undefined,
    })),
  };
}

export function buildHorizontalBarOption(input: {
  rows: Array<{ name: string; value: number; color?: string }>;
  xName?: string;
  threshold?: { value: number; name: string };
}): EChartsOption {
  return {
    animationDuration: 480,
    grid: { left: 18, right: 32, top: 42, bottom: 54, containLabel: true },
    toolbox: { right: 8, feature: { dataZoom: {}, restore: {}, saveAsImage: { pixelRatio: 2 } } },
    tooltip: { trigger: "axis", valueFormatter: (value) => Number(value).toFixed(3) },
    xAxis: { type: "value", name: input.xName, axisLabel: { formatter: (value: number) => Number(value).toFixed(3) }, splitLine: { lineStyle: { color: "#e8e3df" } } },
    yAxis: { type: "category", data: input.rows.map((row) => row.name), axisLabel: { width: 154, overflow: "break", lineHeight: 14 } },
    dataZoom: [{ type: "inside", xAxisIndex: 0, filterMode: "none" }],
    series: [{
      type: "bar",
      data: input.rows.map((row) => ({ value: row.value, itemStyle: { color: row.color || "#607f9e", borderRadius: [0, 7, 7, 0] } })),
      markLine: input.threshold ? { symbol: "none", data: [{ xAxis: input.threshold.value }], label: { formatter: input.threshold.name }, lineStyle: { color: "#c47d59", type: "dashed" } } : undefined,
    }],
  };
}

export function buildScenarioOption(input: {
  categories: string[];
  leftName: string;
  rightName: string;
  series: Array<{ name: string; values: number[]; type: "bar" | "line"; color: string; axis?: "left" | "right"; stack?: string }>;
}): EChartsOption {
  return {
    animationDuration: 520,
    color: input.series.map((row) => row.color),
    grid: { left: 34, right: 34, top: 58, bottom: 48, containLabel: true },
    legend: { top: 4, type: "scroll" },
    toolbox: { right: 8, feature: { dataZoom: {}, restore: {}, saveAsImage: { pixelRatio: 2 } } },
    tooltip: { trigger: "axis", valueFormatter: (value) => Number(value).toFixed(3) },
    xAxis: { type: "category", data: input.categories, axisLabel: { interval: 0, hideOverlap: true } },
    yAxis: [
      { type: "value", name: input.leftName, scale: true, axisLabel: { formatter: (value: number) => Number(value).toFixed(3) }, splitLine: { lineStyle: { color: "#e8e3df" } } },
      { type: "value", name: input.rightName, scale: true, axisLabel: { formatter: (value: number) => Number(value).toFixed(3) }, splitLine: { show: false } },
    ],
    dataZoom: [{ type: "inside", filterMode: "none" }],
    series: input.series.map((row) => row.type === "bar" ? {
      type: "bar",
      name: row.name,
      data: row.values,
      yAxisIndex: row.axis === "right" ? 1 : 0,
      stack: row.stack,
      itemStyle: { color: row.color, borderRadius: [7, 7, 0, 0] },
    } : {
      type: "line",
      name: row.name,
      data: row.values,
      yAxisIndex: row.axis === "right" ? 1 : 0,
      lineStyle: { color: row.color, width: 2.6 },
      symbolSize: 7,
    }),
  };
}
