from __future__ import annotations

import importlib.util
import subprocess
import sys
import time
import tkinter as tk
from pathlib import Path
from tkinter import messagebox
from typing import Optional

from core.paths import project_root, user_data_root

CORE_MODULES: dict[str, str] = {
    "CustomTkinter": "customtkinter",
    "vgamepad": "vgamepad",
    "pynput": "pynput",
    "Pillow": "PIL",
    "darkdetect": "darkdetect",
}

STARTUP_VISUAL_DURATION_SECONDS = 5.0
STARTUP_VISUAL_MESSAGES = (
    "BioSync | preparando a interface",
    "Controle virtual | inicialização por etapas",
    "ONNX | motor auxiliar sob demanda",
    "Cache | arquivos do usuário preservados",
    "ReShade | nenhuma alteração executada",
)


def startup_visual_message(elapsed_seconds: float) -> str:
    if elapsed_seconds >= STARTUP_VISUAL_DURATION_SECONDS:
        return STARTUP_VISUAL_MESSAGES[-1]
    interval = STARTUP_VISUAL_DURATION_SECONDS / len(STARTUP_VISUAL_MESSAGES)
    index = max(0, int(max(0.0, elapsed_seconds) / interval))
    return STARTUP_VISUAL_MESSAGES[index]


def missing_core_dependencies() -> list[str]:
    missing: list[str] = []
    for package, module in CORE_MODULES.items():
        try:
            found = importlib.util.find_spec(module) is not None
        except (ImportError, ValueError):
            found = False
        if not found:
            missing.append(package)
    return missing


class StartupSplash:
    _WIDTH = 620
    _HEIGHT = 340

    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title("BioSync")
        self.root.overrideredirect(True)
        self.root.configure(bg="#0A0A0F")
        self.root.resizable(False, False)
        self._center()
        self._load_brand_font()
        self._started_at = time.monotonic()
        self._build()
        self._install_result: Optional[int] = None
        self.set_progress(3, "Iniciando o BioSync | AA HUB...")
        self.root.after(100, self._update_startup_timing)
        self.root.update()

    def _center(self) -> None:
        x = (self.root.winfo_screenwidth() - self._WIDTH) // 2
        y = (self.root.winfo_screenheight() - self._HEIGHT) // 2
        self.root.geometry(f"{self._WIDTH}x{self._HEIGHT}+{x}+{y}")

    @staticmethod
    def _load_brand_font() -> None:
        if sys.platform != "win32":
            return
        font_path = project_root() / "assets" / "fonts" / "MODERN WARFARE.otf"
        if not font_path.is_file():
            return
        try:
            import ctypes

            ctypes.windll.gdi32.AddFontResourceExW(str(font_path), 0x10, 0)
        except (AttributeError, OSError):
            pass

    def _build(self) -> None:
        panel = tk.Frame(self.root, bg="#1A191E", highlightbackground="#3E3D44", highlightthickness=1)
        panel.pack(fill="both", expand=True, padx=1, pady=1)

        brand = tk.Frame(panel, bg="#1A191E")
        brand.pack(pady=(30, 0))
        tk.Label(
            brand, text="BioSync", bg="#1A191E", fg="#FFFFFF",
            font=("MODERN WARFARE", 25, "bold"),
        ).pack(side="left")
        tk.Label(
            brand, text=" | ", bg="#1A191E", fg="#5C5C66",
            font=("MODERN WARFARE", 25, "bold"),
        ).pack(side="left")
        tk.Label(
            brand, text="MENU", bg="#1A191E", fg="#FFCF00",
            font=("MODERN WARFARE", 25, "bold"),
        ).pack(side="left")

        tk.Frame(panel, bg="#FFCF00", height=3).pack(fill="x", padx=64, pady=(12, 0))
        tk.Label(
            panel, text="AA HUB  ·  INICIALIZAÇÃO",
            bg="#1A191E", fg="#9A9AA3", font=("Segoe UI", 9, "bold"),
        ).pack(pady=(22, 10))

        self._status = tk.StringVar(value="Preparando...")
        tk.Label(
            panel, textvariable=self._status, bg="#1A191E", fg="#F2F2F5",
            font=("Segoe UI", 11), anchor="w",
        ).pack(fill="x", padx=64)

        self._details = tk.StringVar(value="")
        tk.Label(
            panel, textvariable=self._details, bg="#1A191E", fg="#9A9AA3",
            font=("Segoe UI", 9), anchor="w",
        ).pack(fill="x", padx=64, pady=(5, 0))

        self._bar = tk.Canvas(
            panel, height=8, bg="#2E2D33", highlightthickness=0, bd=0,
        )
        self._bar.pack(fill="x", padx=64, pady=(19, 0))
        self._bar.bind("<Configure>", lambda _event: self._draw_progress())
        self._percent = tk.StringVar(value="0%")
        tk.Label(
            panel, textvariable=self._percent, bg="#1A191E", fg="#FFCF00",
            font=("Segoe UI", 9, "bold"),
        ).pack(anchor="e", padx=64, pady=(5, 0))

        footer = tk.Frame(panel, bg="#1A191E")
        footer.pack(side="bottom", fill="x", padx=64, pady=(0, 18))
        self._visual_message = tk.StringVar(value=STARTUP_VISUAL_MESSAGES[0])
        tk.Label(
            footer, textvariable=self._visual_message,
            bg="#1A191E", fg="#5C5C66", font=("Segoe UI", 8, "bold"),
        ).pack(side="left")
        self._elapsed = tk.StringVar(value="0.0 / 5.0 s")
        tk.Label(
            footer, textvariable=self._elapsed,
            bg="#1A191E", fg="#5C5C66", font=("Segoe UI", 8),
        ).pack(side="right")

    def _update_startup_timing(self) -> None:
        elapsed = max(0.0, time.monotonic() - self._started_at)
        visible_elapsed = min(elapsed, STARTUP_VISUAL_DURATION_SECONDS)
        self._visual_message.set(startup_visual_message(elapsed))
        self._elapsed.set(f"{visible_elapsed:.1f} / 5.0 s")
        if elapsed < STARTUP_VISUAL_DURATION_SECONDS:
            self.root.after(100, self._update_startup_timing)

    def _draw_progress(self) -> None:
        self._bar.delete("progress")
        width = self._bar.winfo_width()
        fill_width = int(width * getattr(self, "_progress", 0) / 100)
        if fill_width > 0:
            self._bar.create_rectangle(
                0, 0, fill_width, 8, fill="#FFCF00", width=0, tags="progress",
            )

    def set_progress(self, percent: int, status: str, details: str = "") -> None:
        self._progress = max(0, min(100, percent))
        self._status.set(status)
        self._details.set(details)
        self._percent.set(f"{self._progress}%")
        self._draw_progress()
        self.root.update_idletasks()
        self.root.update()

    def ask_install_core_dependencies(self, missing: list[str]) -> bool:
        packages = ", ".join(missing)
        return messagebox.askyesno(
            "Dependências necessárias",
            "Estes componentes do BioSync não foram encontrados:\n\n"
            f"{packages}\n\n"
            "Deseja baixá-los e instalá-los agora? O processo pode levar alguns minutos.",
            parent=self.root,
        )

    def install_core_dependencies(self, log_path: Path) -> int:
        requirements = project_root() / "requirements.txt"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        self.set_progress(
            18, "Baixando e instalando dependências do BioSync...",
            "Acompanhe o pacote atual no arquivo de log.",
        )
        with log_path.open("w", encoding="utf-8") as log_file:
            process = subprocess.Popen(
                [
                    sys.executable, "-m", "pip", "install",
                    "-r", str(requirements), "--progress-bar", "off",
                ],
                cwd=project_root(),
                stdout=log_file,
                stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )

        def poll() -> None:
            return_code = process.poll()
            if return_code is not None:
                self._install_result = return_code
                self.root.quit()
                return
            detail = "O instalador está trabalhando..."
            try:
                lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
                if lines:
                    detail = lines[-1][-90:]
            except OSError:
                pass
            self.set_progress(18, "Baixando e instalando dependências do BioSync...", detail)
            self.root.after(500, poll)

        self._install_result = None
        self.root.after(100, poll)
        self.root.mainloop()
        return self._install_result if self._install_result is not None else 1

    def close(self) -> None:
        try:
            self.root.destroy()
        except tk.TclError:
            pass


def startup_install_log() -> Path:
    return user_data_root() / "logs" / "startup-install.log"
