# Multiscale Net-Impact Analysis System

A bilingual Streamlit website for multiscale net-impact analysis of oil-market
events and daily explanatory variables. Use the top language control to switch
the interface between Chinese and English.

## What It Does

The app supports this workflow:

1. Choose **Quick mode** or **Professional mode** for net-impact analysis.
2. Refresh daily market and explanatory-variable data.
3. Clean data with complete-case handling, so any date with a missing selected
   variable is removed before analysis windows are split.
4. Run VMD, MRGC screening, FEVD contribution analysis, net-impact calculation,
   and structural-break diagnostics.
5. Review generated tables and figures in the dashboard.
6. Run the separate five-day crisis-risk workflow and, when public access is
   available, overlay a Google Trends attention timeline.
7. Generate a dedicated Brent point-price forecast from five frequency-ordered
   IMFs, with a holdout-validated empirical forecast band.
8. Upload optional local candidate-variable files.

The website separates net-impact interpretation, price forecasting and crisis
risk ranking into distinct result pages so that one output is not presented as
another.

## Brent Price Forecast

The Price Forecast page is a runnable point-price baseline that stays connected
to the supplied CRP-MIF-F paper: it decomposes the latest Brent series into five
frequency-ordered IMFs, uses a BPNN for IMF1, autoregressive ridge baselines for
IMF2-IMF5, and reconstructs the component forecasts. The shaded 80% band is
scaled from a pre-forecast holdout error rather than claimed as a calibrated
probability interval.

This is not a full replication of the paper's weekly high/low interval model.
The current automatic source provides a daily Brent point series, so the app
labels the output accordingly and keeps the full method boundary in a collapsed
note on the result page.

## Quick and Professional Modes

**Quick mode** asks only for the event window. It automatically:

- sets a contiguous pre-event estimation window of up to 504 business days,
  bounded by the available data;
- fixes the decomposition at five IMFs;
- groups explanatory variables by the paper-aligned channels;
- runs data refresh, VMD review, MRGC, FEVD-h determination, and final FEVD
  without intermediate confirmation;
- renders interactive channel pies and IMF response charts.

The fixed interpretation follows the supplied CRP-MIF-F paper:

| IMF | Economic interpretation |
| --- | --- |
| IMF1 | Speculation |
| IMF2 | OPEC+ production announcements |
| IMF3 | Inventories |
| IMF4 | Supply |
| IMF5 | Demand |

This mapping is an economic interpretation framework, not causal
identification. **Professional mode preserves the original settings and all
three manual confirmation gates** for data preparation, VMD review, and FEVD-h
review.

## Crisis Warning

The Crisis Warning tab implements the currently supported part of the DC-CLOF
extension: a five-business-day fast-clock Random Forest risk ranking based on
expanding-tail oil-stress labels. The displayed score is a historical risk
percentile, not a calibrated crisis probability. It must not be interpreted as
predicting the date of a particular war, pandemic, or disaster.

Google Trends is shown as a separate attention/nowcasting timeline and is not
treated as a causal variable or long-horizon warning proof. Google's official
Trends API is still limited-access alpha. The app therefore uses best-effort
public web access and falls back to a local cache when the public endpoint is
unavailable or rate limited.

## Data Sources

The app refreshes daily data from configured online sources and local caches.
Expanded candidate variables are defined in:

```text
config/variable_sources.yaml
```

Optional uploaded variables must be one file per variable. Each file must
contain exactly two data columns after any leading title or note rows:

```text
Date, Value
2024-01-02, 123.45
2024-01-03, 124.10
```

The app starts from the first row where column 1 can be parsed as a date and
column 2 can be parsed as a numeric value.

Data refresh uses this priority automatically:

1. A visitor-uploaded value with the same variable name.
2. The configured official API source, including FRED and EIA.
3. Public no-key sources and the local cache when an API is unavailable.

## Cloud Results and File Lifetime

On Streamlit Community Cloud, generated files are stored temporarily in the
app container. They are not written back to GitHub or copied automatically to
the visitor's computer, and they may be removed when the app restarts or is
redeployed.

After an analysis finishes, open **Net-Impact Results** and select **Download
all results**. The ZIP contains generated tables, figures, reports, and model
outputs. It intentionally excludes raw uploads, downloaded caches, processed
working data, `API.env`, and Streamlit secrets.

The hosted website keeps the API-key interface and asks every visitor to use
their own FRED and EIA keys. Keys are isolated from other visitors, encrypted,
and remembered for one year in that browser. They are never written to the
shared `API.env` file or included in result downloads. Use **Forget API keys in
this browser** to remove them. A different browser, private window, or cleared
browser storage requires the keys to be entered again.

The site owner must add one Fernet key named `BROWSER_API_COOKIE_KEY` in the
Streamlit deployment's **Advanced settings > Secrets**. Generate it locally:

```powershell
.venv\Scripts\python.exe -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Then save it in Streamlit Secrets without committing it to GitHub:

```toml
BROWSER_API_COOKIE_KEY = "paste-the-generated-value-here"
```

Without this owner secret, visitor keys still work in the current session but
cannot be restored after the session ends. Cloud visitors never inherit keys
from the server environment or another visitor. The destructive workspace
cleanup control remains local-only.

## Run Locally

Double-click the website launcher:

```text
Start_Website.bat
```

`Start_Net_Impact_Analysis.bat` remains available as a compatible launcher.

The startup file creates a local `.venv`, installs `requirements.txt`, starts
Streamlit, and opens:

```text
http://localhost:8501
```

Keep the command window open while using the dashboard. Press `Ctrl+C` in that
window to stop the app.

## Optional API Keys

For more stable online data refreshes, use the top-right API menu. In the local
Windows software, keys can also be stored in `API.env` in the project folder:

```text
FRED_API_KEY=your_fred_api_key
EIA_API_KEY=your_eia_api_key
```

FRED API keys come from Federal Reserve Economic Data:
https://fred.stlouisfed.org/docs/api/api_key.html

EIA API keys come from U.S. Energy Information Administration Open Data:
https://www.eia.gov/opendata/register.php

GPRD does not need an API key. It downloads from the official
Caldara-Iacoviello daily GPR file.

Do not share private API keys in packages.

## Build a Windows Package

Run this from PowerShell in the project folder:

```powershell
powershell -ExecutionPolicy Bypass -File packaging\Build_Windows_Package.ps1
```

The portable setup package is written to:

```text
dist\Multiscale_Net_Impact_Analysis_Setup.zip
```

If Inno Setup 6 is installed, the same script also creates:

```text
dist\Multiscale_Net_Impact_Analysis_Setup.exe
```

The `.exe` installer shows a destination-folder page. The zip installer also
opens a folder picker when `Install_Net_Impact_Analysis.bat` is run.

The package excludes local secrets, virtual environments, uploaded files, raw
downloaded data, and generated analysis outputs.

## Project Structure

```text
app/
  streamlit_app.py
config/
  variable_sources.yaml
src/
  data_cleaner.py
  data_fetcher.py
  feature_selector.py
  mrgc_selector.py
  paper_replication.py
  plot_utils.py
  variable_pool.py
  vmd_module.py
packaging/
  Build_Windows_Package.ps1
  Install_Net_Impact_Analysis.bat
  install.ps1
Start_Net_Impact_Analysis.bat
requirements.txt
```
