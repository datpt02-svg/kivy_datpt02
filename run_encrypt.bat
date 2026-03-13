@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

REM =====================================================
REM Usage:
REM   run_encrypt.bat [HTTP_PROXY] [HTTPS_PROXY]
REM
REM   HTTP_PROXY  : e.g. http://192.168.15.186:8088
REM   HTTPS_PROXY : if omitted, HTTPS proxy will use HTTP_PROXY
REM
REM   This batch script:
REM     - Obfuscates the source code with Pyarmor using --outer
REM     - Does NOT include any key file in the output
REM     - Produces a common "dist" directory that requires an external
REM       Pyarmor key (pyarmor.rkey) at runtime.
REM =====================================================

REM --- Configure proxy from arguments (optional) ---
if not "%~1"=="" (
    set "http_proxy=%~1"
)
if not "%~2"=="" (
    set "https_proxy=%~2"
) else (
    if not "%~1"=="" (
        set "https_proxy=%~1"
    )
)

REM Set both lowercase and uppercase variants for compatibility
if defined http_proxy (
    echo [INFO] HTTP proxy: %http_proxy%
    set "HTTP_PROXY=%http_proxy%"
)
if defined https_proxy (
    echo [INFO] HTTPS proxy: %https_proxy%
    set "HTTPS_PROXY=%https_proxy%"
)

REM --- Force Python to use UTF-8 to avoid cp932 decoding issues ---
set "PYTHONUTF8=1"

echo --- Cleaning up previous build ---
if exist dist (
    rmdir /S /Q dist
)
mkdir dist

set "TARGET_DIR=dist"

echo --- Obfuscating 'app' and 'db' with --outer ---

rem Check how to run pyarmor (try uv first, then .venv, then global)
set "PYARMOR_CMD="
powershell -NoProfile -ExecutionPolicy Bypass -Command "if (Get-Command uv -ErrorAction SilentlyContinue) { exit 0 } else { exit 1 }"
if %ERRORLEVEL% equ 0 (
    set "PYARMOR_CMD=uv run pyarmor"
) else if exist ".venv\Scripts\pyarmor.exe" (
    set "PYARMOR_CMD=.\.venv\Scripts\pyarmor"
) else (
    set "PYARMOR_CMD=pyarmor"
)

echo [INFO] Using pyarmor command: !PYARMOR_CMD!
call !PYARMOR_CMD! gen -O "%TARGET_DIR%" --outer -r app db

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [FATAL ERROR] Pyarmor obfuscation failed! Exiting.
    exit /b %ERRORLEVEL%
)

echo --- Copying required non-Python assets and entry script ---

rem Copy entry script main.py as clear text
copy "main.py" "%TARGET_DIR%\" >nul

rem Copy assets and configurations directories
if exist "app\libs\assets" (
    xcopy "app\libs\assets" "dist\app\libs\assets\" /E /I /H /Y >nul
)
if exist "app\libs\language" (
    xcopy "app\libs\language" "dist\app\libs\language\" /E /I /H /Y >nul
)

rem Copy all non-Python UI and config files recursively within app
xcopy "app\*.kv" "dist\app\" /S /I /Y >nul
xcopy "app\*.json" "dist\app\" /S /I /Y >nul
xcopy "app\*.png" "dist\app\" /S /I /Y >nul
xcopy "app\*.jpg" "dist\app\" /S /I /Y >nul

rem Copy Alembic folder (versions need to be unobfuscated for Alembic to parse revisions)
if exist "db\alembic" (
    xcopy "db\alembic" "dist\db\alembic\" /E /I /H /Y >nul
)

echo --- Copying essential folders (data, datasets, etc.) ---
for %%D in (data datasets default_data default_settings logs scripts) do (
    if exist "%%D" (
        xcopy "%%D" "dist\%%D\" /E /I /H /Y >nul
    ) else (
        echo Warning: '%%D' directory not found. Skipping.
    )
)

echo --- Copying sample configurations and env files ---
for %%F in (.python-version .env.sample config.ini.sample delete_setting.ini delete_setting.ini.sample alembic.ini requirements.txt pyproject.toml uv.lock README.md setup.bat build.bat) do (
    if exist "%%F" (
        copy "%%F" "dist\" >nul
    ) else (
        echo Warning: '%%F' file not found. Skipping.
    )
)

REM =====================================================
REM [XU LY DATE/TIME CHUAN ISO - KHONG PHU THUOC LOCALE]
REM =====================================================
echo --- Generating version info ---
set OUTPUT_FILE=dist\version_info.txt

REM 1. Dung PowerShell lay ngay gio (Tranh loi font tieng Nhat/Locale)
for /f "usebackq tokens=*" %%i in (`powershell -Command "Get-Date -Format 'yyyy/MM/dd HH:mm:ss'"`) do (
    set CURRENT_DATETIME=%%i
)

REM 2. Lay thong tin Git
REM Lay hash commit
for /f "usebackq tokens=*" %%i in (`git log -1 --pretty^=format:%%H`) do ( set GIT_HASH=%%i )
REM Lay branch hien tai
for /f "usebackq tokens=*" %%i in (`git branch --show-current`) do ( set GIT_BRANCH=%%i )
REM Lay tag (neu co)
for /f "usebackq tokens=*" %%i in (`git describe --tags --always --dirty 2^>nul`) do ( set GIT_TAG=%%i )

REM 3. Ghi ra file trong thu muc dist
echo [Build Information] > "%OUTPUT_FILE%"
echo Date:   !CURRENT_DATETIME! >> "%OUTPUT_FILE%"
echo Branch: !GIT_BRANCH! >> "%OUTPUT_FILE%"
echo Tag:    !GIT_TAG! >> "%OUTPUT_FILE%"
echo Commit: !GIT_HASH! >> "%OUTPUT_FILE%"
echo ---------------------------------------- >> "%OUTPUT_FILE%"
echo Note: This package requires an external license key. >> "%OUTPUT_FILE%"
REM =====================================================

echo.
echo --- Build completed. Output is in the 'dist' directory. ---
echo NOTE:
echo   This build uses Pyarmor with --outer.
echo   An external Pyarmor key (pyarmor.rkey) must be deployed
echo   separately on each customer PC and referenced via PYARMOR_RKEY.
echo.

echo =====================================================
echo Next steps to prepare per-customer keys
echo =====================================================
echo 1. On each target PC, run the following command to get
echo    the Machine ID and hardware information:
echo.
echo       python -m pyarmor.cli.hdinfo
echo.
echo    Write down at least:
echo       - Machine ID
echo       - Harddisk serial number and/or MAC address
echo.
echo 2. On this build machine, generate a key using the
echo    expiration date and machine information.
echo    Examples:
echo.
echo       !PYARMOR_CMD! gen key -O keys\CUSTOMER_NAME -e YYYY-MM-DD -b "*MID:<MACHINE_ID>"
echo       !PYARMOR_CMD! gen key -O keys\CUSTOMER_NAME -e YYYY-MM-DD -b "*HARDDISK:<DISK_SERIAL>"
echo.
echo 3. Copy the generated key file "pyarmor.rkey" from
echo    the output directory (e.g. keys\CUSTOMER_NAME\pyarmor.rkey)
echo    to the customer PC.
echo.
echo    Place it in a secure location on the customer PC,
echo    for example:
echo       C:\keys\CUSTOMER_NAME\pyarmor.rkey
echo.
echo    Then set PYARMOR_RKEY on the customer PC before
echo    running the application, for example:
echo.
echo       set PYARMOR_RKEY=C:\keys\CUSTOMER_NAME\pyarmor.rkey
echo       cd dist
echo       ..\.venv\Scripts\python main.py
echo.
echo =====================================================

endlocal
exit /b 0
