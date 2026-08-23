export default function handler(_request, response) {
  response.setHeader("Cache-Control", "no-store");
  response.status(200).json({
    ok: true,
    service: "oil-price-intelligence-api",
    officialData: true,
    providers: {
      fred: Boolean(process.env.FRED_API_KEY),
      eia: Boolean(process.env.EIA_API_KEY),
    },
    checkedAt: new Date().toISOString(),
  });
}
