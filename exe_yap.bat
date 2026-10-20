@echo off
chcp 65001 >nul
cd /d "%~dp0"
call _python.bat || exit /b 1
"%PY%" -m pip install pyinstaller
"%PY%" -m PyInstaller --noconfirm --onefile --windowed --name TradePulse --icon logo.ico --add-data "web;web" app.py
if errorlevel 1 (echo Derleme basarisiz. & pause & exit /b 1)
copy /y dist\TradePulse.exe TradePulse.exe >nul
rmdir /s /q build
del /q TradePulse.spec
echo.
echo TradePulse.exe hazir. Masaustune kisayol olusturabilirsin.
pause
