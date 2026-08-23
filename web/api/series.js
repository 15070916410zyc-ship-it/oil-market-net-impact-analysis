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
    try {
      const url = new URL("https://api.stlouisfed.org/fred/series/observations");
      url.searchParams.set("series_id", providerId);
      url.searchParams.set("api_key", key);
      url.searchParams.set("file_type", "json");
      url.searchParams.set("observation_start", start);
      url.searchParams.set("observation_end", end);
      const result = await fetch(url, { headers: { accept: "application/json" } });
      if (result.ok) {
        const payload = await result.json();
        const points = payload.observations
          .filter((row) => typeof row.value === "string" && row.value.trim() !== "" && row.value !== "." && Number.isFinite(Number(row.value)))
          .map((row) => ({ date: row.date, value: Number(row.value) }));
        if (points.length) return points;
      }
    } catch {
      // The official CSV endpoint below remains available without a key.
    }
  }
  const url = new URL("https://fred.stlouisfed.org/graph/fredgraph.csv");
  url.searchParams.set("id", providerId);
  url.searchParams.set("cosd", start);
  url.searchParams.set("coed", end);
  const result = await fetch(url);
  if (!result.ok) throw new Error(`FRED CSV ${result.status}`);
  const text = await result.text();
  return text.trim().split(/\r?\n/).slice(1).flatMap((line) => {
    const [date, raw] = line.split(",");
    const clean = String(raw ?? "").trim();
    if (!date || clean === "" || clean === ".") return [];
    const value = Number(clean);
    return Number.isFinite(value) ? [{ date, value }] : [];
  });
}

export default async function handler(request, response) {
  const id = String(request.query?.id || "");
  const item = catalog.find((candidate) => candidate.id === id) || (/^FRED-[A-Z0-9_]+$/.test(id) ? { id, providerId: id.slice(5), name: id.slice(5), nameEn: id.slice(5), source: "FRED", unit: "", frequency: "", color: "#587a9a" } : null);
  if (!item) return response.status(404).json({ error: "Unknown series" });
  const today = new Date().toISOString().slice(0, 10);
  const start = iso(request.query?.start, "2018-01-01");
  const end = iso(request.query?.end, today);
  const frequency = request.query?.frequency === "monthly" ? "monthly" : "daily";
  try {
    const raw = await fetchFred(item.providerId, start, end);
    const points = frequency === "monthly" ? monthly(raw) : raw;
    response.setHeader("Cache-Control", "public, s-maxage=1800, stale-while-revalidate=43200");
    return response.status(200).json(publicSeries(item, points));
  } catch (error) {
    return response.status(502).json({ error: "Official data provider unavailable", detail: String(error?.message || error) });
  }
}
