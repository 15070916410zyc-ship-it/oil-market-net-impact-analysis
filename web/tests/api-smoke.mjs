import catalogHandler from "../api/catalog.js";
import seriesHandler from "../api/series.js";
import instrumentsHandler from "../api/instruments.js";

const call = (handler, query = {}, method = "GET") => new Promise((resolve, reject) => {
  const response = {
    statusCode: 200,
    setHeader() {},
    status(code) { this.statusCode = code; return this; },
    json(body) { resolve({ status: this.statusCode, body }); },
  };
  Promise.resolve(handler({ query, method, body: query }, response)).catch(reject);
});

const catalog = await call(catalogHandler, { q: "wti crude" });
console.log(JSON.stringify({ kind: "catalog", status: catalog.status, count: catalog.body.items.length, sources: [...new Set(catalog.body.items.map((item) => item.source))], warnings: catalog.body.warnings }));

const encoded = Buffer.from(JSON.stringify({ route: "petroleum/pri/spt", facet: "series", series: "RWTC" })).toString("base64url");
const series = await call(seriesHandler, { id: `EIA2-${encoded}`, frequency: "daily", start: "2026-08-01", end: "2026-08-18" });
console.log(JSON.stringify({ kind: "series", status: series.status, source: series.body.source, points: series.body.points?.length, last: series.body.points?.at(-1), detail: series.body.detail }));

const instruments = await call(instrumentsHandler, { benchmark: "WTI", volume: 300000, coverage: 60, futuresShare: 70 });
console.log(JSON.stringify({ kind: "instruments", status: instruments.status, products: instruments.body.products.map((item) => ({ code: item.code, contracts: item.contracts, size: item.size })), execution: instruments.body.executionEnabled }));

if (catalog.status !== 200 || !catalog.body.items.length) process.exitCode = 1;
if (series.status !== 200 || !series.body.points?.length) process.exitCode = 1;
if (instruments.status !== 200 || instruments.body.executionEnabled !== false) process.exitCode = 1;
