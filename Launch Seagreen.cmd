@echo off
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 (
  echo Python 3.10 or newer is recommended. Install Python from python.org, then run this launcher again.
  pause
  exit /b 1
)
if not exist ".venv\Scripts\python.exe" py -3 -m venv .venv
if errorlevel 1 goto failed
.venv\Scripts\python.exe -m pip install .
if errorlevel 1 goto failed
.venv\Scripts\python.exe -m seagreen web
pause
exit /b 0
:failed
echo Seagreen could not be installed. Review the error above.
pause
exit /b 1
