@echo off
cd /d "%~dp0"
call _python.bat || exit /b 1
start "" "%PYW%" app.py
