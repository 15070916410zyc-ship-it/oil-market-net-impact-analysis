# Website acceptance report

Date: 2026-08-23

## Outcome

The decision and professional workspaces were exercised in a real Chromium browser after the redesign. The final local build completed the automated suite with `132 passed, 9 subtests passed`, imported all changed modules, compiled all Python files, and produced no browser console errors or warnings in the clean acceptance session.

## Five visual review rounds

1. Established a bright research canvas and checked the first desktop hierarchy and chart composition (`output/playwright/bright-dashboard-final.png`, `output/playwright/bright-decision-chart-final.png`).
2. Rebuilt the hero as a site-wide animated data terrain and removed the separate decorative illustration (`output/playwright/round2/round2-decision-1440-entire.png`).
3. Checked 1440 px and 390 px layouts, fixed the API/language dock, and changed the professional tool selector to a balanced 2-by-2 mobile grid (`output/playwright/round3/decision-1440.png`, `output/playwright/round3/decision-390.png`, `output/playwright/round3/professional-390-fixed2.png`).
4. Ran and inspected professional forecasting, crisis warning, and connected-data search with real output (`output/playwright/round4/pro-forecast-brent-20.png`, `output/playwright/round4/pro-crisis-complete.png`, `output/playwright/round4/data-search-crude-stocks-monthly.png`).
5. Changed detailed procurement assumptions, checked all displayed values, and repeated desktop/mobile English acceptance (`output/playwright/round5/decision-cost-inputs.png`, `output/playwright/round5/decision-english-1440.png`, `output/playwright/round5/decision-english-390-clean.png`).

## Functional matrix

| Area | Exercised | Result |
| --- | --- | --- |
| Workspace switch | Decision to professional and back | 0.35 s / 0.29 s in the measured local browser session; no intermediate professional home page |
| Brent forecast | 20 trading days, 60 months | Completed with point path, 50/80/95% empirical intervals, validation metrics, table, and download |
| WTI forecast | 5 days/24 months and 60 days/84 months | Completed in 2.4 s and 1.5 s after cache-first repair |
| Crisis warning | 15-year requested window | Completed in about 31 s with five-day risk ranking and Hamilton high-volatility-regime probability |
| Connected-data search | Chinese query `原油库存` | Three indexed results; stored EIA series rendered with date range, daily/monthly switch, Excel download, and add/update action |
| Research store | SQLite read/write/readback and PostgreSQL health/migration behavior | Covered by automated tests; local UI reported the SQLite store healthy |
| Procurement model | Basis, FX, quality, freight, tax, initial margin, strategy mix | Inputs changed the cost, liquidity, and impact outputs without errors |
| Responsive UI | 1440 and 390 px, Chinese and English | No horizontal overflow, control collision, clipped slider values, or console errors |

## Defects found and corrected during acceptance

- Public-source failure chains could hold WTI forecasting for roughly 80 seconds. Fresh, complete cached data is now checked before online providers.
- A short forecast request could overwrite the long raw-history cache. Raw cache saves now merge by date and preserve prior history.
- A cache could be current at the end but omit the requested historical start. Cache acceptance now checks both recency and requested-start coverage.
- Staggered external-market calendars removed too much of the oil-price history in crisis warning. The price calendar is retained and optional transformed signals use past-only forward filling plus a neutral leading value.
- Professional tabs wrapped unevenly on narrow screens. The mobile selector now uses a balanced 2-by-2 grid.

## External boundaries

The application does not fabricate unavailable vendor data. Public providers can still be unavailable or rate-limited; in that case the UI uses a recent, sufficiently complete verified cache and shows the actual data-through date. PostgreSQL/Neon is selected only when `DATABASE_URL` exists and passes its health check; otherwise the local SQLite research store remains usable.
