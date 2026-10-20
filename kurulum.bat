@echo off
chcp 65001 >nul
cd /d "%~dp0"
call _python.bat || exit /b 1
echo Kullanilan Python: %PY%
echo TradePulse kurulumu basliyor...
"%PY%" -m pip install --upgrade pip
"%PY%" -m pip install "pyodbc>=5.0"
if errorlevel 1 (
  echo.
  echo pyodbc kurulamadi. Yukaridaki hatanin ekran goruntusunu al.
  pause
  exit /b 1
)
"%PY%" -m pip install "pywebview>=5.0"
if errorlevel 1 (
  echo.
  echo pywebview kurulamadi. Sorun degil: uygulama Microsoft Edge penceresinde acilacak.
)
echo.
echo Kurulum tamamlandi. TradePulse.bat ile acabilirsin.
pause
