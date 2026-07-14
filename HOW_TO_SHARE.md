# How to Share the Multiscale Net-Impact Analysis System

## Recommended: Build a Windows package

Run this command from PowerShell in the project folder:

```powershell
powershell -ExecutionPolicy Bypass -File packaging\Build_Windows_Package.ps1
```

The package is created here:

```text
dist\Multiscale_Net_Impact_Analysis_Setup.zip
```

If Inno Setup 6 is installed on the build computer, the script also creates:

```text
dist\Multiscale_Net_Impact_Analysis_Setup.exe
```

Send either the `.zip` or the `.exe` to another Windows user.

The `.exe` installer lets the user choose the destination folder during setup.

## Installing from the zip package

1. Unzip `Multiscale_Net_Impact_Analysis_Setup.zip`.
2. Double-click `Install_Net_Impact_Analysis.bat`.
3. Choose the destination folder in the folder picker.
4. It creates a desktop shortcut named `Multiscale Net-Impact Analysis`.
5. Double-click the desktop shortcut to start the dashboard.

The first launch creates a local `.venv`, installs `requirements.txt`, starts
Streamlit, and opens:

```text
http://localhost:8501
```

## Startup file

The project provides a website launcher and keeps the original compatible launcher:

```text
Start_Website.bat
Start_Net_Impact_Analysis.bat
```

The website has a Chinese / English switch at the top of the page.

Keep this command window open while using the dashboard. Press `Ctrl+C` in that
window to stop the app.

## Python and API keys

The package expects Python 3.10+ on the user's Windows computer. During Python
installation, tick **Add python.exe to PATH**.

For more stable online data refreshes, use the top-right app menu or create
`API.env` in the installed app folder:

```text
FRED_API_KEY=their_fred_api_key
EIA_API_KEY=their_eia_api_key
```

FRED API keys come from Federal Reserve Economic Data:
https://fred.stlouisfed.org/docs/api/api_key.html

EIA API keys come from U.S. Energy Information Administration Open Data:
https://www.eia.gov/opendata/register.php

GPRD does not need an API key. It downloads from the official
Caldara-Iacoviello daily GPR file.

Do not share your private API key unless you intend to.

The dashboard can open without API keys. The app uses public fallbacks when
available, but personal FRED and EIA keys make online refreshes more stable.

## Local uploaded variable format

Local candidate variables can be uploaded from the Run Analysis page. Each file
must contain exactly two data columns:

```text
Date, Value
2024-01-02, 123.45
2024-01-03, 124.10
```

Leading title, note, or header rows are allowed. The app starts from the first
row where column 1 can be parsed as a date and column 2 can be parsed as a
numeric value. Each uploaded file is registered as one candidate variable.
