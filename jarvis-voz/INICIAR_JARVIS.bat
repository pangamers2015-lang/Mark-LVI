@echo off
setlocal
cd /d "%~dp0"

where py >nul 2>nul
if errorlevel 1 (
  echo Python 3.11 ou superior nao foi encontrado.
  echo Instale Python e marque "Add Python to PATH".
  pause
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  py -3 -m venv .venv
  if errorlevel 1 goto erro
)

".venv\Scripts\python.exe" -m pip install --upgrade pip
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto erro

".venv\Scripts\python.exe" app.py
if errorlevel 1 goto erro
exit /b 0

:erro
echo.
echo Nao foi possivel iniciar o Jarvis. Confira a mensagem acima.
pause
exit /b 1
