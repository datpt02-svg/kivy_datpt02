@echo off
setlocal EnableDelayedExpansion

echo ============================================
echo  EVS-UI Docker Auto Setup Script
echo ============================================

:: ---- 1. Install Visual C++ Redistributable ----
echo [1/5] Installing Visual C++ Redistributable...
curl -L -o "%TEMP%\vc_redist.exe" "https://aka.ms/vs/17/release/vc_redist.x64.exe"
"%TEMP%\vc_redist.exe" /quiet /norestart
del "%TEMP%\vc_redist.exe"

:: ---- 2. Install Python 3.9.18 ----
echo [2/5] Installing Python 3.9.18...
curl -L -o "%TEMP%\python-installer.exe" "https://www.python.org/ftp/python/3.9.18/python-3.9.18-amd64.exe"
"%TEMP%\python-installer.exe" /quiet InstallAllUsers=1 PrependPath=1 Include_test=0
del "%TEMP%\python-installer.exe"

:: Reload PATH
set "PATH=C:\Program Files\Python39;C:\Program Files\Python39\Scripts;%PATH%"

:: ---- 3. Upgrade pip ----
echo [3/5] Upgrading pip...
python -m pip install --upgrade pip

:: ---- 4. Install project dependencies ----
echo [4/5] Installing Python dependencies...
pip install -r \\host.lan\Data\requirements.txt

:: ---- 5. Create startup task to auto-run main.py on login ----
echo [5/5] Creating scheduled startup task...
powershell -Command "$Action = New-ScheduledTaskAction -Execute 'python' -Argument '\\host.lan\Data\main.py' -WorkingDirectory 'C:\shared'; $Trigger = New-ScheduledTaskTrigger -AtLogon; $Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries; Register-ScheduledTask -TaskName 'EVS-UI' -Action $Action -Trigger $Trigger -Settings $Settings -RunLevel Highest -Force"

echo ============================================
echo  Setup complete! Starting EVS-UI...
echo ============================================

:: Run the application immediately
cd /d C:\shared
start "" python main.py
