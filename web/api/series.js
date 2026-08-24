import { catalog, publicSeries } from "./_catalog.js";

const iso = (value, fallback) => /^\d{4}-\d{2}-\d{2}$/.test(String(value || "")) ? String(value) : fallback;

function monthly(points) {
  const groups = new Map();
  for (const point of points) {
    const month = point.date.slice(0, 7);
    const values = groups.get(month) || [];
    values.push(point.value);
    groups.set(month, values);
  }
  return [...groups].map(([date, values]) => ({
    date,
    value: Number((values.reduce((a, b) => a + b, 0) / values.length).toFixed(4)),
  }));
}

async function fetchFred(providerId, start, end) {
  const key = process.env.FRED_API_KEY;
  if (key) {
    const url = new URL("https://api.stlouisfed.org/fred/series/observations");
    url.searchParams.set("series_id", providerId);
    url.searchParams.set("api_key", key);
    url.searchParams.set("file_type", "json");
    url.searchParams.set("observation_start", start);
    url.searchParams.set("observation_end", end);
    const response = await fetch(url, { headers: { accept: "application/json" } });
    if (response.ok) {
      const payload = await response.json();
      const points = (payload.observations || [])
        .filter((row) => row.value !== "." && Number.isFinite(Number(row.value)))
        .map((row) => ({ date: row.date, value: Number(row.value) }));
      if (points.length) return points;
    }
  }
  const url = new URL("https://fred.stlouisfed.org/graph/fredgraph.csv");
  url.searchParams.set("id", providerId);
  url.searchParams.set("cosd", start);
  url.searchParams.set("coed", end);
  const response = await fetch(url);
  if (!response.ok) throw new Error(`FRED CSV ${response.status}`);
  return (await response.text()).trim().split(/\r?\n/).slice(1).flatMap((line) => {
    const [date, raw] = line.split(",");
    const value = Number(String(raw ?? "").trim());
    return date && Number.isFinite(value) ? [{ date, value }] : [];
  });
}

function decodeEia(id) {
  return JSON.parse(Buffer.from(id.slice(5), "base64url").toString("utf8"));
}

async function fetchEia(id, start, end, frequency) {
  const { route, facet, series } = decodeEia(id);
  const key = process.env.EIA_API_KEY || "DEMO_KEY";
  const metaUrl = new URL(`https://api.eia.gov/v2/${route}/`);
  metaUrl.searchParams.set("api_key", key);
  const metaResponse = await fetch(metaUrl);
  if (!metaResponse.ok) throw new Error(`EIA metadata ${metaResponse.status}`);
  const metadata = (await metaResponse.json()).response || {};
  const available = (metadata.frequency || []).map((row) => row.id);
  const requested = frequency === "monthly" ? "monthly" : "daily";
  const chosen = available.includes(requested) ? requested : available.includes("monthly") ? "monthly" : available[0];
  const url = new URL(`https://api.eia.gov/v2/${route}/data/`);
  url.searchParams.set("api_key", key);
  if (chosen) url.searchParams.set("frequency", chosen);
  url.searchParams.set("data[0]", "value");
  url.searchParams.set(`facets[${facet}][]`, series);
  url.searchParams.set("start", start);
  url.searchParams.set("end", end);
  url.searchParams.set("sort[0][column]", "period");
  url.searchParams.set("sort[0][direction]", "asc");
  url.searchParams.set("length", "5000");
  const response = await fetch(url, { headers: { accept: "application/json" } });
  if (!response.ok) throw new Error(`EIA data ${response.status}`);
  const payload = await response.json();
  if (payload.error) throw new Error(payload.error.message || "EIA API error");
  const rows = payload.response?.data || [];
  const points = rows.flatMap((row) => Number.isFinite(Number(row.value)) ? [{ date: String(row.period), value: Number(row.value) }] : []);
  if (!points.length) throw new Error("The selected EIA series has no observations in this date range");
  return {
    points: requested === "monthly" && chosen !== "monthly" ? monthly(points) : points,
    name: rows[0]?.[`${facet}-name`] || rows[0]?.["series-description"] || series,
    unit: rows[0]?.units || "",
    frequency: chosen || requested,
  };
}

function decodeYahoo(id) {
  return Buffer.from(id.slice(6), "base64url").toString("utf8");
}

async function fetchYahoo(id, start, end, frequency) {
  const symbol = decodeYahoo(id);
  if (!symbol) throw new Error("Yahoo series identifier is invalid");
  const period1 = Math.floor(new Date(`${start}T00:00:00Z`).getTime() / 1000);
  const period2 = Math.floor(new Date(`${end}T00:00:00Z`).getTime() / 1000) + 86400;
  const url = new URL(`https://query1.finance.yahoo.com/v8/finance/chart/${encodeURIComponent(symbol)}`);
  url.searchParams.set("period1", String(period1));
  url.searchParams.set("period2", String(period2));
  url.searchParams.set("interval", "1d");
  url.searchParams.set("events", "history");
  const response = await fetch(url, {
    headers: { accept: "application/json", "user-agent": "Mozilla/5.0 (compatible; OilPriceIntelligence/1.0)" },
  });
  if (!response.ok) throw new Error(`Yahoo chart HTTP ${response.status}`);
  const payload = await response.json();
  const result = payload.chart?.result?.[0];
  if (!result) throw new Error(payload.chart?.error?.description || "Yahoo chart returned no result");
  const timestamps = result.timestamp || [];
  const closes = result.indicators?.quote?.[0]?.close || [];
  const points = timestamps.flatMap((timestamp, index) => {
    const value = Number(closes[index]);
    return Number.isFinite(value) ? [{ date: new Date(timestamp * 1000).toISOString().slice(0, 10), value }] : [];
  });
  if (!points.length) throw new Error("Yahoo chart returned no usable close values");
  const meta = result.meta || {};
  return {
    id,
    providerId: symbol,
    name: meta.longName || meta.shortName || symbol,
    nameEn: meta.longName || meta.shortName || symbol,
    source: "Yahoo Finance / supplementary",
    unit: meta.currency || "Market quote",
    frequency: frequency === "monthly" ? "Monthly" : "Daily",
    updated: points.at(-1)?.date || "",
    color: "#477c8d",
    points: frequency === "monthly" ? monthly(points) : points,
  };
}

export default async function handler(request, response) {
  const id = String(request.query?.id || "");
  const today = new Date().toISOString().slice(0, 10);
  const start = iso(request.query?.start, "2000-01-01");
  const end = iso(request.query?.end, today);
  const frequency = request.query?.frequency === "monthly" ? "monthly" : "daily";
  try {
    if (id.startsWith("EIA2-")) {
      const result = await fetchEia(id, start, end, frequency);
      response.setHeader("Cache-Control", "public, s-maxage=1800, stale-while-revalidate=43200");
      return response.status(200).json({ id, name: result.name, nameEn: result.name, source: "EIA", unit: result.unit, frequency: result.frequency, updated: result.points.at(-1)?.date || "", color: "#9b6d51", points: result.points });
    }
    if (id.startsWith("YAHOO-")) {
      const result = await fetchYahoo(id, start, end, frequency);
      response.setHeader("Cache-Control", "public, s-maxage=300, stale-while-revalidate=1800");
      return response.status(200).json(result);
    }
    const item = catalog.find((candidate) => candidate.id === id) || (/^FRED-[A-Z0-9_]+$/i.test(id) ? { id, providerId: id.slice(5), name: id.slice(5), nameEn: id.slice(5), source: "FRED", unit: "", frequency: "", color: "#587a9a" } : null);
    if (!item) return response.status(404).json({ error: "Unknown series" });
    const raw = await fetchFred(item.providerId, start, end);
    const points = frequency === "monthly" ? monthly(raw) : raw;
    response.setHeader("Cache-Control", "public, s-maxage=1800, stale-while-revalidate=43200");
    return response.status(200).json(publicSeries(item, points));
  } catch (error) {
    return response.status(502).json({ error: "Data provider unavailable", detail: String(error?.message || error) });
  }
}
