@echo off
cd /d "%~dp0"
echo Starting USIO IR Platform from %cd% ...
python app_nicegui.py
pause
