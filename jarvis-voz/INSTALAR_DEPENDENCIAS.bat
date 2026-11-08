@echo off
setlocal
cd /d "%~dp0"
title Instalador de dependencias - Jarvis
echo ==========================================
echo   JARVIS - INSTALACAO DE DEPENDENCIAS
echo ==========================================
where py >nul 2>nul
if errorlevel 1 (
  echo Python nao encontrado. Instale Python 3.12 x64 e marque Add Python to PATH.
  pause
  exit /b 1
)
if not exist ".venv\Scripts\python.exe" (
  py -3.12 -m venv .venv
  if errorlevel 1 (
    echo Nao foi possivel criar o ambiente Python.
    pause
    exit /b 1
  )
)
".venv\Scripts\python.exe" -m pip install --upgrade pip
".venv\Scripts\python.exe" -m pip install -r requirements.txt pyinstaller
if errorlevel 1 (
  echo Falha ao instalar dependencias.
  pause
  exit /b 1
)
echo.
echo Dependencias instaladas com sucesso.
pause
