@echo off
title BioSync | AA HUB
cd /d "%~dp0"

echo ============================================
echo   BioSync ^| AA HUB  -  Python Prototype
echo ============================================
echo.

where python >nul 2>&1
if errorlevel 1 (
    echo [ERRO] Python nao encontrado no PATH.
    echo Instale Python 3.10+ e marque "Add to PATH".
    pause
    exit /b 1
)

echo Iniciando...
echo.
echo  NOTA: ViGEmBus precisa estar instalado para o pad virtual.
echo  https://github.com/nefarius/ViGEmBus/releases
echo.
echo  Dependencias ausentes serao identificadas pelo aplicativo e instaladas
echo  somente apos sua autorizacao.
echo.
python main.py
if errorlevel 1 pause
