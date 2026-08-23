import { catalog } from "./_catalog.js";

export default function handler(request, response) {
  const q = String(request.query?.q || "").trim().toLowerCase();
  const rows = q
    ? catalog.filter((item) => `${item.id} ${item.name} ${item.source}`.toLowerCase().includes(q))
    : catalog;
  response.setHeader("Cache-Control", "public, s-maxage=3600, stale-while-revalidate=86400");
  response.status(200).json({ items: rows.map(({ providerId: _privateId, ...item }) => item) });
}
