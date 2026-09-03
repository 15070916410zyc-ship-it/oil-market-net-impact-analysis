# Initiative 40: research platform upgrade

## Objective

Upgrade the public React/Vercel oil-market research site without replacing its verified-data statistical core. The work covers modular architecture, provider-based discovery, interactive analytical charts, browser-local AI explanation, executable multi-asset hedge portfolios, statistical diagnostics, bilingual UX, and full browser verification.

## Non-negotiable method boundaries

- No demo or synthetic result may replace a failed live calculation.
- Non-significant selected-scale Granger results remain visible for audit but do not enter FEVD.
- The main IMF scale is selected from calculated evidence and may contain one or two scales.
- FEVD horizon is the trading-day distance between extrema of the selected scale.
- AI explains validated structured outputs and never changes authoritative calculations.
- Default variables are protected; only user-added variables may be removed.
- Displayed decimals use at most three decimal places.

## Architecture decisions

1. Keep React/Vite and Vercel functions; split reusable chart, provider, AI, portfolio, and page logic into typed modules.
2. Add a local provider contract and independent adapters instead of incorporating AGPL OpenBB code.
3. Use Apache ECharts for analytical time series, interval, heatmap and network visualizations. Retain Recharts only for small summary graphics during migration.
4. Use Perspective's maintained `@perspective-dev/*` packages for the data-workspace table and local user-driven slicing.
5. Load WebLLM dynamically in a dedicated Worker after explicit user consent and device checks.
6. Implement transparent constrained portfolio and multi-leg option calculations in project-owned code; expose every assumption and cost.
7. Preserve Statsmodels-based Granger/VAR/FEVD logic and add independently tested structural-break diagnostics.

## Workstreams and dependencies

1. Regression baseline and module contracts.
2. Provider search and data workspace.
3. Chart system, depending on normalized data contracts.
4. AI explanation, depending on validated analysis snapshots.
5. Portfolio analytics, depending on instruments and analytical outputs.
6. Statistical diagnostics and API validation.
7. Bilingual, responsive, accessibility and production verification.

## Verification evidence

Evidence and final PASS/FAIL status will be posted to GitHub Issue #40 and stored under `output/playwright/initiative-40/`.
