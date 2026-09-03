import { describe, expect, it } from "vitest";

import { buildForecastOption, buildTimeSeriesOption, normalizeForecastRows } from "./chartOptions";

describe("forecast chart options", () => {
  const rows = [
    { date: "2026-01-02", actual: 80 },
    { date: "2026-01-05", median: 81, low50: 77, high50: 85, low80: 73, high80: 89, low95: 68, high95: 94 },
    { date: "2026-01-06", median: 82, low50: 78, high50: 86, low80: 74, high80: 90, low95: 69, high95: 95 },
  ];

  it("bridges the final observation to the first forecast without fabricating history", () => {
    const normalized = normalizeForecastRows(rows);
    expect(normalized[0].median).toBe(80);
    expect(normalized[0].low50).toBeNull();
    expect(normalized[1].median).toBe(81);
  });

  it("builds three visually distinct nested confidence bands with zoom controls", () => {
    const option = buildForecastOption(rows, "en");
    const series = option.series as Array<{ name?: string; type?: string; data?: unknown[]; itemStyle?: { color?: string } }>;
    expect(series.map((item) => item.name)).toEqual(expect.arrayContaining([
      "95% interval",
      "80% interval",
      "50% interval",
      "Observed price",
      "Median forecast",
    ]));
    const intervalBands = series.filter((item) => item.type === "custom");
    expect(intervalBands).toHaveLength(3);
    expect(intervalBands.every((item) => item.data?.length === 1)).toBe(true);
    expect(series.find((item) => item.name === "95% interval")?.itemStyle?.color).toBe("#9fb8cc");
    expect(option.dataZoom).toHaveLength(2);
  });

  it("gives every analytical time-series chart inside and slider zoom controls", () => {
    const option = buildTimeSeriesOption({
      rows: [{ date: "2026-01", observed: 1.23456 }],
      series: [{ key: "observed", name: "Observed", color: "#222" }],
      yName: "USD",
    });
    expect(option.dataZoom).toEqual(expect.arrayContaining([
      expect.objectContaining({ type: "inside" }),
      expect.objectContaining({ type: "slider" }),
    ]));
    expect(JSON.stringify(option)).toContain("saveAsImage");
  });
});
