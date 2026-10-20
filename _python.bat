@echo off
rem Python yolunu bulur ve PY / PYW degiskenlerine yazar. Diger .bat dosyalari bunu cagirir.
rem Tercih sirasi: Python 3.13, 3.12, varsayilan python, Anaconda, diger kurulumlar.
set "PY="
set "PYW="
set "CAND="
for %%C in (python3.13 python3.12 python py) do if not defined CAND (%%C --version >NUL 2>NUL && set "CAND=%%C")
if defined CAND for /f "delims=" %%I in ('%CAND% -c "import sys;print(sys.executable)"') do set "PY=%%I"
if not defined PY if exist "%USERPROFILE%\anaconda3\python.exe" set "PY=%USERPROFILE%\anaconda3\python.exe"
if not defined PY if exist "%LOCALAPPDATA%\anaconda3\python.exe" set "PY=%LOCALAPPDATA%\anaconda3\python.exe"
if not defined PY if exist "%ProgramData%\anaconda3\python.exe" set "PY=%ProgramData%\anaconda3\python.exe"
if not defined PY for /d %%D in ("%LOCALAPPDATA%\Programs\Python\Python3*") do if exist "%%D\python.exe" set "PY=%%D\python.exe"
if not defined PY goto :yok
"%PY%" --version >NUL 2>NUL || goto :yok
set "PYW=%PY:python.exe=pythonw.exe%"
if not exist "%PYW%" set "PYW=%PY%"
exit /b 0
:yok
echo.
echo Python bulunamadi.
echo Komut istemine "py install 3.13" yaz veya python.org adresinden Python kur.
echo Sonra bu dosyayi tekrar calistir.
echo.
pause
exit /b 1
