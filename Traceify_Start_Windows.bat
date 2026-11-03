@echo off
rem ======================================================================
rem  Traceify - Start und automatische Einrichtung (Windows)
rem  Beim ersten Start wird alles Noetige geholt und installiert:
rem  Python 3.12, Bibliotheken, Tesseract OCR + Sprachdaten, Ollama + KI-Modell
rem  Optionen:  --ja  (alles bestaetigen)   --ohne-ki   --modell NAME
rem ======================================================================
setlocal EnableExtensions EnableDelayedExpansion
chcp 65001 >nul
cd /d "%~dp0"
title Traceify
set "PYTHONIOENCODING=utf-8"
set "PYTHONUTF8=1"

call :findpy
if not defined PY call :installpy
if not defined PY (
  echo.
  echo Python konnte nicht automatisch installiert werden.
  echo Bitte Python 3.12 von https://www.python.org installieren und erneut starten.
  pause
  exit /b 1
)

"%PY%" "traceify\installer.py" %*
if errorlevel 1 (
  echo.
  echo Die Einrichtung ist fehlgeschlagen. Details siehe oben.
  pause
  exit /b 1
)

start "" ".venv\Scripts\pythonw.exe" -m traceify
exit /b 0

rem ----------------------------------------------------------------------
:findpy
set "PY="
for %%V in (3.12 3.13 3.11 3.10) do (
  if not defined PY (
    for /f "delims=" %%i in ('py -%%V -c "import sys;print(sys.executable)" 2^>nul') do set "PY=%%i"
  )
)
if not defined PY (
  for /f "delims=" %%i in ('python -c "import sys;print(sys.executable) if (3,10)<=sys.version_info[:2]<=(3,13) else exit(1)" 2^>nul') do set "PY=%%i"
)
for %%V in (312 313 311 310) do (
  if not defined PY if exist "%LOCALAPPDATA%\Programs\Python\Python%%V\python.exe" set "PY=%LOCALAPPDATA%\Programs\Python\Python%%V\python.exe"
  if not defined PY if exist "%ProgramFiles%\Python%%V\python.exe" set "PY=%ProgramFiles%\Python%%V\python.exe"
)
exit /b 0

rem ----------------------------------------------------------------------
:installpy
echo Python wird installiert (einmalig) ...
where winget >nul 2>nul
if not errorlevel 1 (
  winget install -e --id Python.Python.3.12 --scope user --silent --accept-package-agreements --accept-source-agreements
)
call :findpy
if defined PY exit /b 0
echo Lade Python-Installer von python.org ...
set "PYSETUP=%TEMP%\python-3.12.10-amd64.exe"
powershell -NoProfile -ExecutionPolicy Bypass -Command "[Net.ServicePointManager]::SecurityProtocol='Tls12'; Invoke-WebRequest -UseBasicParsing 'https://www.python.org/ftp/python/3.12.10/python-3.12.10-amd64.exe' -OutFile '%PYSETUP%'"
if exist "%PYSETUP%" (
  "%PYSETUP%" /quiet InstallAllUsers=0 PrependPath=1 Include_launcher=1 Include_test=0
)
call :findpy
exit /b 0
