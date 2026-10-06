#!/usr/bin/env python3
"""
BioSync | AA HUB — Python prototype
CustomTkinter UI (MW4/Warzone grade) + vgamepad backend

Requisitos Windows:
  1. ViGEmBus instalado (https://github.com/nefarius/ViGEmBus/releases)
  2. pip install -r requirements.txt

Uso:
  python main.py
"""
from __future__ import annotations

import sys

from core.paths import auxilio_ai_environment_root, project_root
from startup import StartupSplash, missing_core_dependencies, startup_install_log

# Garante import dos pacotes locais
ROOT = project_root()
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main():
    splash = StartupSplash()
    splash.set_progress(10, "Verificando dependências do aplicativo...")
    missing = missing_core_dependencies()
    if missing:
        if getattr(sys, "frozen", False):
            from tkinter import messagebox

            messagebox.showerror(
                "Build incompleta",
                "O executável foi criado sem componentes necessários:\n\n"
                + ", ".join(missing)
                + "\n\nGere novamente o EXE com build_exe.bat.",
                parent=splash.root,
            )
            splash.close()
            return 1
        if not splash.ask_install_core_dependencies(missing):
            splash.close()
            return 1
        install_code = splash.install_core_dependencies(startup_install_log())
        if install_code != 0 or missing_core_dependencies():
            from tkinter import messagebox

            messagebox.showerror(
                "Falha ao instalar dependências",
                "A instalação não foi concluída. Verifique a conexão e consulte:\n"
                f"{startup_install_log()}",
                parent=splash.root,
            )
            splash.close()
            return 1

    splash.set_progress(42, "Carregando os módulos de controle e interface...")
    from ui.app import BioSyncApp

    splash.set_progress(68, "Inicializando o motor do controle virtual...")
    app = BioSyncApp()
    if sys.platform == "win32":
        if app.engine.virtual_pad_available:
            controller_status = "Controle virtual: pronto (ViGEmBus)"
        else:
            controller_status = "Controle virtual: ViGEmBus ausente ou indisponível"
    else:
        controller_status = "Controle virtual: disponível apenas no Windows"

    auxilio_ai_dir = ROOT / "auxilio_ai"
    model_exists = any((auxilio_ai_dir / "models").glob("*.onnx"))
    interpreter = auxilio_ai_environment_root() / "Scripts" / "python.exe"
    if model_exists and interpreter.is_file():
        onnx_status = "Motor ONNX: ambiente isolado encontrado; runtime validado ao iniciar"
    elif model_exists:
        onnx_status = "Motor ONNX: modelo disponível; dependências serão confirmadas ao iniciar"
    else:
        onnx_status = "Motor ONNX: nenhum arquivo .onnx encontrado"
    splash.set_progress(88, "Finalizando a interface BioSync | AA HUB...", controller_status)
    splash.set_progress(96, onnx_status, controller_status)
    splash.root.withdraw()
    splash.set_progress(100, "Inicialização concluída")
    splash.root.after(650, splash.root.quit)
    splash.root.mainloop()
    splash.close()

    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
