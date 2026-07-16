@echo off
REM ─────────────────────────────────────────────────────────────
REM  DealCourier launcher for Windows
REM  - creates/activates a .venv if missing
REM  - installs the project into it
REM  - starts the web dashboard
REM  Close this window or press Ctrl+C to stop.
REM ─────────────────────────────────────────────────────────────
setlocal
cd /d "%~dp0"

if not exist "config.yaml" (
    if exist "config_init.yaml" (
        echo [setup] config.yaml not found -- copying config_init.yaml to config.yaml
        echo [setup] Remember to edit config.yaml and set your api_key!
        copy /y "config_init.yaml" "config.yaml" >nul
        echo.
    ) else (
        echo [error] Neither config.yaml nor config_init.yaml found in %CD%
        echo         Copy config_init.yaml to config.yaml and fill in your api_key.
        pause
        exit /b 1
    )
)

REM Read port from config.yaml (default 8000) so we open the right URL
set "PORT=8000"
for /f "tokens=*" %%i in ('powershell -NoProfile -Command "try { (Select-String -Path config.yaml -Pattern '^\s*port:\s*(\d+)' -AllMatches | Select-Object -First 1).Matches[0].Groups[1].Value } catch { '' }"') do set "PORT=%%i"
if "%PORT%"=="" set "PORT=8000"
echo [info] Dashboard will open at http://127.0.0.1:%PORT% once the server is ready

REM Background waiter: poll /health, open default browser when ready, then exit
start "DealCourier browser opener" /min powershell -NoProfile -WindowStyle Hidden -Command ^
  "for($i=0;$i -lt 60;$i++){try{if((Invoke-WebRequest -Uri 'http://127.0.0.1:%PORT%/health' -UseBasicParsing -TimeoutSec 1).StatusCode -eq 200){Start-Process 'http://127.0.0.1:%PORT%'; break}}catch{}; Start-Sleep -Milliseconds 800}"

REM Pick a Python interpreter
set "PY="
where uv >nul 2>&1
if %errorlevel%==0 (
    set "USE_UV=1"
) else (
    set "USE_UV=0"
)

if "%USE_UV%"=="1" (
    echo [run] uv detected -- syncing dependencies
    uv sync
    if errorlevel 1 ( echo [error] uv sync failed & pause & exit /b 1 )
    echo.
    echo [run] Starting DealCourier ...  (Ctrl+C to stop)
    uv run python -m dealcourier.main
    goto :end
)

REM Plain pip path
where py >nul 2>&1
if %errorlevel%==0 ( set "PY=py" ) else ( set "PY=python" )

if not exist ".venv\Scripts\python.exe" (
    echo [setup] Creating virtual environment (.venv)
    %PY% -m venv .venv
    if errorlevel 1 ( echo [error] Could not create .venv & pause & exit /b 1 )
)

echo [setup] Installing dependencies into .venv
call ".venv\Scripts\activate.bat"
python -m pip install --upgrade pip >nul
pip install -e .
if errorlevel 1 ( echo [error] pip install failed & pause & exit /b 1 )

echo.
echo [run] Starting DealCourier ...  (Ctrl+C to stop)
python -m dealcourier.main

:end
echo.
echo DealCourier has stopped.
pause
endlocal
