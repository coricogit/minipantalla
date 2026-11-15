@echo off
cd /d "%~dp0"
echo [%date% %time%] > install.log
where py >nul 2>nul
if %errorlevel%==0 (
  py -3 -u install.py %* >> install.log 2>&1
) else (
  python -u install.py %* >> install.log 2>&1
)
echo exit=%errorlevel% >> install.log
type install.log
echo.
pause
