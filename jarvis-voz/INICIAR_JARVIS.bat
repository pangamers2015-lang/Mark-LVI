@echo off
setlocal
cd /d "%~dp0"
title JARVIS
if exist "Jarvis\Jarvis.exe" (
  start "" "Jarvis\Jarvis.exe"
  exit /b 0
)
if exist "dist\Jarvis\Jarvis.exe" (
  start "" "dist\Jarvis\Jarvis.exe"
  exit /b 0
)
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" app.py
  exit /b %errorlevel%
)
echo O aplicativo ainda nao foi preparado.
echo Execute INSTALAR_DEPENDENCIAS.bat e depois rode novamente.
pause
