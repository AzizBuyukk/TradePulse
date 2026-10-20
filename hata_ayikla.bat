@echo off
chcp 65001 >nul
cd /d "%~dp0"
call _python.bat || exit /b 1
echo Kullanilan Python: %PY%
echo Hata ayiklama modu: hata olursa bu pencerede gorunur.
"%PY%" app.py
pause
