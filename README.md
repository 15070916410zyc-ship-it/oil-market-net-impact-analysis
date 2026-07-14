# Multiscale Net-Impact Analysis System

A bilingual Streamlit website for multiscale net-impact analysis of oil-market
events and daily explanatory variables. Use the top language control to switch
the interface between Chinese and English.

## What It Does

The app supports this workflow:

1. Refresh daily market and explanatory-variable data.
2. Clean data with complete-case handling, so any date with a missing selected
   variable is removed before analysis windows are split.
3. Confirm the effective common data window, event period, and pre-event window.
4. Run VMD, MRGC screening, FEVD contribution analysis, net-impact calculation,
   and structural-break diagnostics.
5. Review generated tables and figures in the dashboard.
6. Upload optional local candidate-variable files.

The app is dedicated to the multiscale net-impact research workflow. It
explains how selected market variables contribute to oil-market movements; it
does not generate oil-price forecasts.

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

When an uploaded variable has the same name as an existing variable, the
uploaded values take priority automatically.

## Cloud Results and File Lifetime

On Streamlit Community Cloud, generated files are stored temporarily in the
app container. They are not written back to GitHub or copied automatically to
the visitor's computer, and they may be removed when the app restarts or is
redeployed.

After an analysis finishes, open **Net-Impact Results** and select **Download
all results**. The ZIP contains generated tables, figures, reports, and model
outputs. It intentionally excludes raw uploads, downloaded caches, processed
working data, `API.env`, and Streamlit secrets.

The API and workspace-cleanup menu is available in the local Windows software
but hidden on the hosted website. Configure hosted API keys through the
Streamlit deployment's **Advanced settings > Secrets** instead of saving an
`API.env` file from the public interface.

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

For more stable online data refreshes in the local Windows software, use the
top-right app menu or create `API.env` in the project folder:

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
