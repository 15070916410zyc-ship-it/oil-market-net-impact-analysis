export type ProviderId = "FRED" | "EIA" | "GPRD" | "Yahoo" | "AKShare" | "Upload" | string;

export type ProviderSeries = {
  id: string;
  name: string;
  nameZh?: string;
  provider: ProviderId;
  frequency: string;
  unit: string;
  category?: string;
  description?: string;
};

const aliasGroups = [
  ["gold", "黄金", "金价", "bullion", "precious metal", "gc=f"],
  ["silver", "白银", "银价", "si=f"],
  ["oil", "原油", "油价", "crude", "brent", "wti"],
  ["geopolitical risk", "地缘政治风险", "地缘风险", "gpr", "gprd"],
  ["inventory", "inventories", "库存", "stocks"],
  ["dollar", "美元", "美元指数", "usd", "dxy"],
  ["interest rate", "利率", "yield", "treasury"],
  ["inflation", "通胀", "物价", "cpi", "ppi"],
  ["natural gas", "天然气", "henry hub", "ng=f"],
  ["copper", "铜", "铜价", "hg=f"],
] as const;

export function normalizeSearchText(value: string): string {
  return value
    .normalize("NFKC")
    .toLocaleLowerCase()
    .replace(/[\p{P}\p{S}]+/gu, " ")
    .replace(/\s+/g, " ")
    .trim();
}

export function expandSearchTerms(query: string): string[] {
  const original = normalizeSearchText(query);
  if (!original) return [];
  const expanded = new Set<string>([original]);
  for (const group of aliasGroups) {
    if (group.some((term) => {
      const normalized = normalizeSearchText(term);
      return normalized.includes(original) || original.includes(normalized);
    })) {
      group.forEach((term) => expanded.add(normalizeSearchText(term)));
    }
  }
  return [...expanded].filter(Boolean);
}

function tokenScore(haystack: string, term: string): number {
  if (!term) return 0;
  if (haystack === term) return 120;
  if (haystack.startsWith(`${term} `)) return 80;
  if (haystack.includes(` ${term} `) || haystack.endsWith(` ${term}`)) return 70;
  if (haystack.includes(term)) return 48;
  const tokens = term.split(" ").filter(Boolean);
  if (tokens.length && tokens.every((token) => haystack.includes(token))) return 35 + tokens.length;
  return 0;
}

export function rankProviderResults<T extends ProviderSeries>(rows: T[], query: string): T[] {
  const terms = expandSearchTerms(query);
  if (!terms.length) return [...rows];
  return rows
    .map((row, index) => {
      const id = normalizeSearchText(row.id);
      const name = normalizeSearchText(row.name);
      const nameZh = normalizeSearchText(row.nameZh || "");
      const metadata = normalizeSearchText([
        row.provider,
        row.category,
        row.description,
        row.frequency,
        row.unit,
      ].filter(Boolean).join(" "));
      const score = Math.max(...terms.map((term) => {
        const idScore = tokenScore(id, term);
        return Math.max(
        idScore > 0 ? idScore + 20 : 0,
        tokenScore(name, term),
        tokenScore(nameZh, term),
        tokenScore(metadata, term) * 0.55,
      );
      }));
      return { row, score, index };
    })
    .filter((entry) => entry.score > 0)
    .sort((a, b) => b.score - a.score || a.index - b.index)
    .map((entry) => entry.row);
}
