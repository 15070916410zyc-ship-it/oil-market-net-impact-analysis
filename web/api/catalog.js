import { catalog } from "./_catalog.js";

export default async function handler(request, response) {
  const normalize = (value) => String(value || "").trim().toLowerCase().replace(/\binventories\b/g, "inventory").replace(/\bprices\b/g, "price").replace(/\brates\b/g, "rate");
  const q = normalize(request.query?.q);
  let rows = q
    ? catalog.filter((item) => normalize(`${item.id} ${item.name} ${item.nameEn} ${item.category} ${item.source}`).includes(q))
    : catalog;
  const key = process.env.FRED_API_KEY;
  if (q.length >= 2 && key) {
    try {
      const url = new URL("https://api.stlouisfed.org/fred/series/search");
      url.searchParams.set("api_key", key); url.searchParams.set("file_type", "json"); url.searchParams.set("search_text", q); url.searchParams.set("limit", "40"); url.searchParams.set("order_by", "search_rank");
      const result = await fetch(url, { headers: { accept: "application/json" } });
      if (result.ok) {
        const payload = await result.json();
        const discovered = (payload.seriess || []).map((item) => ({ id: `FRED-${item.id}`, name: item.title, nameEn: item.title, category: "FRED search result", source: "FRED", unit: item.units_short || item.units, frequency: item.frequency_short || item.frequency, updated: item.last_updated?.slice(0,10) || "", color: "#587a9a" }));
        rows = [...rows, ...discovered.filter((item) => !rows.some((row) => row.id === item.id))];
      }
    } catch { /* Keep the verified built-in catalog when discovery is unavailable. */ }
  }
  response.setHeader("Cache-Control", "public, s-maxage=3600, stale-while-revalidate=86400");
  response.status(200).json({ items: rows.map(({ providerId: _privateId, ...item }) => item) });
}
