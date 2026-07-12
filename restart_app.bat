@echo off
cd /d "%~dp0"
echo Stopping any existing app_nicegui.py process...
taskkill /F /IM python.exe /T >nul 2>&1
timeout /t 2 /nobreak >nul
echo Starting USIO IR Platform (with DB connection-pooling fix) from %cd% ...
python app_nicegui.py
pause
