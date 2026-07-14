@echo off
chcp 65001 > nul
title Multiscale Net-Impact Analysis System

set "PROJECT_DIR=%~dp0"
cd /d "%PROJECT_DIR%"
set "VENV_PY=%PROJECT_DIR%.venv\Scripts\python.exe"
set "APP_URL=http://localhost:8501"

echo ============================================================
echo  Multiscale Net-Impact Analysis System
echo ============================================================
echo.
echo Project directory:
echo %PROJECT_DIR%
echo.

set "PYTHON_CMD=python"
where python > nul 2> nul
if errorlevel 1 (
    set "PYTHON_CMD=py -3"
    where py > nul 2> nul
    if errorlevel 1 (
        echo Python was not found.
        echo Please install Python 3.10+ and tick "Add python.exe to PATH".
        echo Download: https://www.python.org/downloads/
        echo.
        pause
        exit /b 1
    )
)

if not exist "%VENV_PY%" (
    echo Creating local virtual environment...
    %PYTHON_CMD% -m venv .venv
    if errorlevel 1 (
        echo Failed to create the virtual environment.
        pause
        exit /b 1
    )
)

echo Installing or checking required packages...
"%VENV_PY%" -m pip install --upgrade pip
"%VENV_PY%" -m pip install -r requirements.txt
if errorlevel 1 (
    echo Failed to install required packages.
    echo Please check your network connection and try again.
    pause
    exit /b 1
)

if not exist ".env" if not exist "API.env" (
    echo.
    echo Warning: .env or API.env was not found.
    echo The dashboard can open, but online FRED data updates need FRED_API_KEY.
    echo Create API.env with: FRED_API_KEY=your_key
    echo.
)

echo Starting Streamlit app...
echo Browser URL: %APP_URL%
echo.
call :open_chrome_when_ready "%APP_URL%"
echo Keep this window open while using the dashboard.
echo Press Ctrl+C in this window to stop the app.
echo.

"%VENV_PY%" -m streamlit run app\streamlit_app.py --server.address localhost --server.port 8501 --server.headless true

echo.
echo Streamlit has stopped.
pause
exit /b 0

:find_chrome
set "CHROME_EXE="
if exist "%ProgramFiles%\Google\Chrome\Application\chrome.exe" set "CHROME_EXE=%ProgramFiles%\Google\Chrome\Application\chrome.exe"
if not defined CHROME_EXE if exist "%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe" set "CHROME_EXE=%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"
if not defined CHROME_EXE if exist "%LocalAppData%\Google\Chrome\Application\chrome.exe" set "CHROME_EXE=%LocalAppData%\Google\Chrome\Application\chrome.exe"
exit /b 0

:open_chrome_when_ready
call :find_chrome
set "NET_IMPACT_APP_URL=%~1"
set "NET_IMPACT_CHROME_EXE=%CHROME_EXE%"
if not defined NET_IMPACT_CHROME_EXE goto chrome_not_found
echo Chrome will open automatically when the app is ready.
start "Open Net-Impact Analysis" /min powershell -NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -Command "$url = $env:NET_IMPACT_APP_URL; $chrome = $env:NET_IMPACT_CHROME_EXE; for ($i = 0; $i -lt 90; $i++) { try { Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 1 | Out-Null; break } catch { Start-Sleep -Seconds 1 } }; Start-Process -FilePath $chrome -ArgumentList $url"
exit /b 0

:chrome_not_found
echo Chrome was not found automatically. Open %NET_IMPACT_APP_URL% manually in Chrome.
exit /b 0
