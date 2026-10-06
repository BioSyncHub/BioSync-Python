@echo off
setlocal
cd /d "%~dp0"

where python >nul 2>&1
if not errorlevel 1 (
    set "PYTHON=python"
) else (
    where py >nul 2>&1
    if errorlevel 1 (
        echo [ERRO] Python nao encontrado no PATH.
        echo Instale Python 3.10+ e marque "Add to PATH".
        pause
        exit /b 1
    )
    set "PYTHON=py -3"
)

%PYTHON% -m pip install -r requirements.txt
if errorlevel 1 (
    echo [ERRO] Falha ao instalar dependencias do projeto.
    pause
    exit /b 1
)

%PYTHON% -m pip install --upgrade pip pyinstaller
if errorlevel 1 (
    echo [ERRO] Falha ao instalar PyInstaller.
    pause
    exit /b 1
)

for /f "delims=" %%I in ('%PYTHON% -c "import pathlib, vgamepad; print(pathlib.Path(vgamepad.__file__).parent)"') do set "VGAMEPAD_DIR=%%I"
if not defined VGAMEPAD_DIR (
    echo [ERRO] Pacote vgamepad nao encontrado no Python usado para compilar.
    pause
    exit /b 1
)
if not exist "%VGAMEPAD_DIR%\win\vigem\client\x64\ViGEmClient.dll" (
    echo [ERRO] Biblioteca ViGEmClient.dll nao encontrada em "%VGAMEPAD_DIR%".
    pause
    exit /b 1
)

%PYTHON% -m PyInstaller --noconfirm --clean --onedir --windowed --name BioSync ^
    --specpath build ^
    --add-binary "%VGAMEPAD_DIR%\win\vigem\client\x64\ViGEmClient.dll;vgamepad\win\vigem\client\x64" ^
    --add-binary "%VGAMEPAD_DIR%\win\vigem\client\x86\ViGEmClient.dll;vgamepad\win\vigem\client\x86" ^
    --add-data "%~dp0config;config" ^
    --add-data "%~dp0assets\target;assets\target" ^
    --add-data "%~dp0assets\fonts;assets\fonts" ^
    --add-data "%~dp0auxilio_ai\main.py;auxilio_ai" ^
    --add-data "%~dp0auxilio_ai\config.ini;auxilio_ai" ^
    --add-data "%~dp0auxilio_ai\requirements.txt;auxilio_ai" ^
    --add-data "%~dp0auxilio_ai\BioSync_AI-ico.ico;auxilio_ai" ^
    --add-data "%~dp0auxilio_ai\core;auxilio_ai\core" ^
    --add-data "%~dp0auxilio_ai\gui;auxilio_ai\gui" ^
    --add-data "%~dp0auxilio_ai\models\BioSync-Warzone.onnx;auxilio_ai\models" ^
    --add-data "%~dp0auxilio_ai\models\BioSync-Fortnite.onnx;auxilio_ai\models" ^
    main.py

if errorlevel 1 (
    echo [ERRO] Falha ao gerar o executavel.
    pause
    exit /b 1
)

attrib +h "dist\BioSync\_internal"
if errorlevel 1 (
    echo [ERRO] Executavel criado, mas nao foi possivel ocultar dist\BioSync\_internal.
    pause
    exit /b 1
)

echo.
echo [OK] Executavel gerado em dist\BioSync\BioSync.exe
echo A pasta _internal esta oculta. Mantenha-a na pasta BioSync ao distribuir.
pause
