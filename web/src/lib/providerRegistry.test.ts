import { describe, expect, it } from "vitest";

import {
  expandSearchTerms,
  rankProviderResults,
  type ProviderSeries,
} from "./providerRegistry";

const catalog: ProviderSeries[] = [
  { id: "FRED-GOLDAMGBD228NLBM", name: "Gold Fixing Price", nameZh: "伦敦黄金定盘价", provider: "FRED", frequency: "daily", unit: "USD" },
  { id: "YAHOO-GC=F", name: "Gold Futures", nameZh: "纽约黄金期货", provider: "Yahoo", frequency: "daily", unit: "USD" },
  { id: "GPRD", name: "Geopolitical Risk Index", nameZh: "地缘政治风险指数", provider: "GPRD", frequency: "daily", unit: "index" },
  { id: "FRED-DCOILWTICO", name: "WTI spot price", nameZh: "WTI现货价格", provider: "FRED", frequency: "daily", unit: "USD/bbl" },
];

describe("provider catalog search", () => {
  it("expands bilingual finance aliases without losing the original term", () => {
    expect(expandSearchTerms("黄金")).toEqual(expect.arrayContaining(["黄金", "gold", "bullion"]));
    expect(expandSearchTerms("gold")).toEqual(expect.arrayContaining(["gold", "黄金"]));
  });

  it("ranks exact identifiers first and fuzzy bilingual matches afterwards", () => {
    expect(rankProviderResults(catalog, "GC=F")[0].id).toBe("YAHOO-GC=F");
    expect(rankProviderResults(catalog, "gold").map((item) => item.id)).toEqual([
      "YAHOO-GC=F",
      "FRED-GOLDAMGBD228NLBM",
    ]);
    expect(rankProviderResults(catalog, "地缘风险")[0].id).toBe("GPRD");
  });
});
