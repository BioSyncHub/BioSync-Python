@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\pyinstaller.exe" (
    echo PyInstaller nao encontrado. Execute primeiro a instalacao das dependencias de build.
    pause
    exit /b 1
)

".venv\Scripts\pyinstaller.exe" --noconfirm --clean --onefile --noconsole --name BioSync --icon "BioSync_AI-ico.ico" --collect-all onnxruntime --collect-all bettercam --collect-all comtypes --collect-all customtkinter --collect-all darkdetect --add-data "BioSync_AI-ico.ico;." --add-data "config.ini;." --add-data "models\BioSync-Warzone.onnx;models" --add-data "models\BioSync-Fortnite.onnx;models" main.py
if errorlevel 1 (
    echo Falha ao compilar. Consulte a mensagem acima.
    pause
    exit /b 1
)

if not exist "dist\BioSync-Portable\profiles" mkdir "dist\BioSync-Portable\profiles"
copy /y "dist\BioSync.exe" "dist\BioSync-Portable\BioSync.exe" >nul
if exist "profiles\active.json" copy /y "profiles\active.json" "dist\BioSync-Portable\profiles\active.json" >nul
if exist "README.md" copy /y "README.md" "dist\BioSync-Portable\README.md" >nul
powershell -NoProfile -Command "Compress-Archive -Path 'dist\BioSync-Portable\BioSync.exe','dist\BioSync-Portable\profiles','dist\BioSync-Portable\README.md' -DestinationPath 'dist\BioSync-Portable.zip' -Force"
if errorlevel 1 (
    echo Falha ao criar o pacote ZIP.
    pause
    exit /b 1
)

echo.
echo Compilacao concluida: dist\BioSync-Portable\BioSync.exe
echo Pacote para compartilhar: dist\BioSync-Portable.zip
pause