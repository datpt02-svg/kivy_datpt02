@echo off
REM =============================================
REM 1. Install uv
REM =============================================
where uv >nul 2>&1
IF ERRORLEVEL 1 (
  echo uv not found, installing...
  powershell -ExecutionPolicy Bypass -Command "irm https://astral.sh/uv/install.ps1 | iex"
) ELSE (
  echo uv already installed.
)

REM =============================================
REM 2. Ensure Python version is installed
REM =============================================
echo Ensuring Python 3.9 is installed...
uv python install 3.9

REM =============================================
REM 3. Run uv sync in project folder
REM =============================================
cd ./
echo Syncing project dependencies...
uv sync

REM =============================================
REM 4. Notify success
REM =============================================
echo.
echo All set! Project is ready to use.
echo.
if "%1"=="--no-pause" (
    echo Setup completed automatically.
) else (
    set /p "=Press any key to exit..." <nul
    pause >nul
)