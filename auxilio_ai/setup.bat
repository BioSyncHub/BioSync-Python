@echo off
setlocal
cd /d "%~dp0"
set "APP_ROOT=%~dp0.."

where py >nul 2>&1
if errorlevel 1 (
    echo [ERRO] Python Launcher nao encontrado.
    echo Instale Python 3.11 e habilite o Python Launcher.
    exit /b 1
)

py -3.11 --version >nul 2>&1
if errorlevel 1 (
    echo [ERRO] Python 3.11 nao encontrado.
    echo O runtime ONNX desta referencia requer um ambiente compativel com Python 3.11.
    exit /b 1
)

if not exist "%APP_ROOT%\.venv-auxilio-ai\Scripts\python.exe" (
    echo [1/2] Criando ambiente isolado...
    py -3.11 -m venv "%APP_ROOT%\.venv-auxilio-ai"
    if errorlevel 1 (
        echo [ERRO] Nao foi possivel criar o ambiente virtual.
        exit /b 1
    )
)

echo [2/2] Instalando dependencias do Auxilio-AI...
"%APP_ROOT%\.venv-auxilio-ai\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
    echo [ERRO] Falha ao instalar as dependencias.
    exit /b 1
)

echo.
echo Auxilio-AI pronto.
