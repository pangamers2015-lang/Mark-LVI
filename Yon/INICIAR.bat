@echo off
setlocal
cd /d "%~dp0"
title Yon - Interface

if not exist ".venv\Scripts\python.exe" (
    echo [Yon] Criando ambiente Python isolado...
    py -3.12 -m venv .venv 2>nul
    if errorlevel 1 python -m venv .venv
    if errorlevel 1 (
        echo [ERRO] Nao foi possivel criar o ambiente Python.
        echo Instale Python 3.12 e tente novamente.
        pause
        exit /b 1
    )
)

echo [Yon] Verificando e instalando dependencias...
".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -r requirements.txt
if errorlevel 1 (
    echo [ERRO] Falha ao instalar dependencias.
    pause
    exit /b 1
)

echo [Yon] Iniciando interface...
".venv\Scripts\python.exe" app.py
if errorlevel 1 pause
endlocal
