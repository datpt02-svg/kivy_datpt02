@echo off
setlocal enabledelayedexpansion

rem ================================================================
rem  STEP 0: Parse args - choose console or no console
rem   - default: console=False
rem   - use: build.bat --console  -> console=True
rem ================================================================
set "CONSOLE_VALUE=False"
if /I "%~1"=="--console" (
    set "CONSOLE_VALUE=True"
)

echo [0] Build console: %CONSOLE_VALUE%
echo.

rem ================================================================
rem  STEP 1: Precheck - Ensure uv and Python 3.9 exist
rem ================================================================
echo [1] Checking for uv and Python 3.9...

rem ===== Config =====
set UV_VERSION=0.8.20

rem --- Check uv ---
powershell -NoProfile -ExecutionPolicy Bypass -Command "if (Get-Command uv -ErrorAction SilentlyContinue) { Write-Host '[OK] uv found:' (uv --version) } else { Write-Host '[Installing] uv not found, installing uv %UV_VERSION%...'; $env:UV_VERSION='%UV_VERSION%'; irm https://astral.sh/uv/install.ps1 | iex }"

if %ERRORLEVEL% neq 0 (
    echo [Error] Failed to install uv.
    exit /b 1
)

rem --- Check python3.9 ---
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
    "if (Get-Command python3.9 -ErrorAction SilentlyContinue) { Write-Host '[OK] python3.9 found' } else { Write-Host '[Installing] python3.9 not found, installing via uv...'; uv python install 3.9 }"

if %ERRORLEVEL% neq 0 (
    echo [Error] Failed to install Python 3.9.
    exit /b 1
)

echo [OK] Precheck done.
echo.

rem ================================================================
rem  STEP 2: Clean any running .venv Python process
rem ================================================================
set SCRIPT_DIR=%~dp0
set SCRIPT_DIR=%SCRIPT_DIR:~0,-1%
echo [2] Checking for running python.exe processes inside .venv...

powershell -NoProfile -Command ^
    "Get-Process | Where-Object { $_.Path -like '*\\.venv\\Scripts\\python.exe*' } | ForEach-Object { Write-Host ('[INFO] Terminating process: ' + $_.Id + ' ' + $_.Path); Stop-Process -Id $_.Id -Force }"

rem ================================================================
rem  STEP 3: Create root virtual environment
rem ================================================================
echo [3] Creating virtual environment in project root...
python3.9 -m venv .venv

if not exist ".venv\Scripts\activate.bat" (
    echo [Error] Failed to create .venv
    exit /b 1
)

rem ================================================================
rem  STEP 4: Activate root venv and sync dependencies
rem ================================================================
echo [4] Activating virtual environment...
call "%SCRIPT_DIR%\.venv\Scripts\activate.bat"

echo [4.1] Syncing environment with uv...
uv sync

rem ================================================================
rem  STEP 4.4: Read current console flag from evs-ui.spec
rem ================================================================
echo [4.4] Reading current console flag...
for /f "usebackq delims=" %%v in (`powershell -NoProfile -Command "(Get-Content -Raw '%SCRIPT_DIR%\evs-ui.spec' | Select-String -Pattern 'console\s*=\s*(True|False)').Matches[0].Groups[1].Value"`) do set "ORIG_CONSOLE=%%v"
if not defined ORIG_CONSOLE set "ORIG_CONSOLE=False"
echo [INFO] Original console=%ORIG_CONSOLE%

rem ================================================================
rem  STEP 4.5: Update evs-ui.spec console flag based on arg
rem ================================================================
echo [4.5] Setting console=%CONSOLE_VALUE% in evs-ui.spec...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$p = '%SCRIPT_DIR%\evs-ui.spec';" ^
  "if (-not (Test-Path $p)) { Write-Error 'Spec file not found'; exit 1 }" ^
  "$c = Get-Content -Raw $p;" ^
  "$n = [regex]::Replace($c, 'console\s*=\s*(True|False)', 'console=%CONSOLE_VALUE%');" ^
  "Set-Content -NoNewline -Path $p -Value $n;" ^
  "Write-Host ('[OK] evs-ui.spec updated to console=%CONSOLE_VALUE%')"

if %ERRORLEVEL% neq 0 (
    echo [Error] Failed to update evs-ui.spec.
    exit /b 1
)

rem ================================================================
rem  STEP 5: Build with PyInstaller
rem ================================================================
echo [5] Building with PyInstaller...
uv run pyinstaller --noconfirm --clean "%SCRIPT_DIR%\evs-ui.spec"

if %ERRORLEVEL% neq 0 (
    echo [Error] PyInstaller build failed.
    echo [5.1] Restoring evs-ui.spec console=%ORIG_CONSOLE%...
    powershell -NoProfile -ExecutionPolicy Bypass -Command ^
      "$p = '%SCRIPT_DIR%\evs-ui.spec'; $c = Get-Content -Raw $p; $n = [regex]::Replace($c, 'console\s*=\s*(True|False)', 'console=%ORIG_CONSOLE%'); Set-Content -NoNewline -Path $p -Value $n"
    exit /b 1
)

echo [5.1] Restoring evs-ui.spec console=%ORIG_CONSOLE%...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$p = '%SCRIPT_DIR%\evs-ui.spec'; $c = Get-Content -Raw $p; $n = [regex]::Replace($c, 'console\s*=\s*(True|False)', 'console=%ORIG_CONSOLE%'); Set-Content -NoNewline -Path $p -Value $n"

set INTERNAL_DIR=%SCRIPT_DIR%\dist\evs-ui

if exist "%SCRIPT_DIR%\.env.sample" (
    copy "%SCRIPT_DIR%\.env.sample" "%INTERNAL_DIR%\" >nul
)

if exist "%SCRIPT_DIR%\.ini.sample" (
    copy "%SCRIPT_DIR%\.ini.sample" "%INTERNAL_DIR%\" >nul
)

if exist "%SCRIPT_DIR%\delete_setting.ini.sample" (
    copy "%SCRIPT_DIR%\delete_setting.ini.sample" "%INTERNAL_DIR%\" >nul
)

if exist "%SCRIPT_DIR%\scripts" (
    echo [INFO] Copying scripts folder...
    xcopy "%SCRIPT_DIR%\scripts" "%INTERNAL_DIR%\scripts\" /E /I /H /Y >nul
)

rem ================================================================
rem  STEP 6: Setup _internal venv
rem ================================================================
echo [6] Changing directory to _internal...
cd /d "%INTERNAL_DIR%\_internal"

echo [6.1] Deactivating root venv...
call "%SCRIPT_DIR%\.venv\Scripts\deactivate.bat"

echo [6.2] Creating internal virtual environment...
python3.9 -m venv .venv

if not exist ".venv\Scripts\activate.bat" (
    echo [Error] Failed to create internal .venv
    exit /b 1
)

call ".venv\Scripts\activate.bat"

echo [6.3] Syncing environment with uv...
uv sync --active

rem ================================================================
rem  STEP 7: Copy cached Python 3.9 from uv folder
rem ================================================================
echo [7] Copying Python 3.9 into _internal\.venv...

cd .venv

rem Lấy đường dẫn AppData động
set "UV_PY_BASE=%AppData%\uv\python"

rem Tìm thư mục đầu tiên có chứa "3.9"
for /f "delims=" %%p in ('dir /b /ad "%UV_PY_BASE%" ^| findstr /i "3.9"') do (
    set "PY_FOLDER=%%p"
    goto :found
)

:found
if not defined PY_FOLDER (
    echo [Error] Could not find any folder containing "3.9" in "%UV_PY_BASE%"
    echo Please run: uv python install 3.9
    exit /b 1
)

echo [INFO] Found Python folder: %PY_FOLDER%
echo [INFO] Copying "%UV_PY_BASE%\%PY_FOLDER%" to current directory...

xcopy "%UV_PY_BASE%\%PY_FOLDER%" ".\%PY_FOLDER%\" /E /I /H /Y >nul

if %ERRORLEVEL% neq 0 (
    echo [Error] Copy failed.
    exit /b 1
)

echo [OK] Python 3.9 copied successfully to .\%PY_FOLDER%

echo.
echo [Build completed successfully!]
endlocal
exit /b 0