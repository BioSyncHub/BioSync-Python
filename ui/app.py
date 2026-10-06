"""
BioSync | AA HUB — CustomTkinter frontend
Visual target: MW4 / Warzone tactical HUD
"""
from __future__ import annotations

import customtkinter as ctk
import configparser
import json
import os
import re
import sys
import time
import logging
import subprocess
import webbrowser
from dataclasses import asdict
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, simpledialog
from typing import Optional
from pynput import keyboard
from PIL import Image, ImageTk

from ui import theme as T
from core.config import EngineConfig, load_profiles, save_profile
from core.engine import InputEngine
from core.input_capture import InputCapture
from core.paths import auxilio_ai_environment_root, user_data_root
from core.recoil import load_recoil_profiles
from auxilio_ai.core.model_profiles import (
    discover_model_profiles,
    normalize_model_profile_path,
)
from auxilio_ai.gui.view_settings import DEFAULT_VIEW_SETTINGS

logger = logging.getLogger(__name__)

AUX_AI_TARGET_PREVIEWS = {
    "BioSync-Warzone": {
        "image": "target-wz-onnx.png",
        "focus": {"head": (0.50, 0.13), "chest": (0.51, 0.30), "belly": (0.50, 0.46)},
    },
    "BioSync-Fortnite": {
        "image": "target-wfortnite-onnx.png",
        "focus": {"head": (0.52, 0.12), "chest": (0.50, 0.30), "belly": (0.50, 0.42)},
    },
}
AUX_AI_FOCUS_COLORS = {
    "head": "#F06464",
    "chest": "#F2C94C",
    "belly": "#00E566",
}


def auxilio_ai_child_environment(data_dir: Path, resource_dir: Path) -> dict[str, str]:
    environment = os.environ.copy()
    environment.pop("TCL_LIBRARY", None)
    environment.pop("TK_LIBRARY", None)
    environment.update({
        "BIOSYNC_AUX_DATA_DIR": str(data_dir),
        "BIOSYNC_AUX_RESOURCE_DIR": str(resource_dir),
    })
    return environment


class BioSyncApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        ctk.set_appearance_mode(T.APPEARANCE)
        ctk.set_default_color_theme(T.COLOR_THEME)

        self.title("BioSync | AA HUB  ·  v6.2-py")
        self.geometry("1000x720")
        self.resizable(False, False)
        self.configure(fg_color=T.BG_DEEP)
        T.load_mw_font()  # register MODERN WARFARE.otf before widgets

        self.sidebar_width = 220

        # ── Core ──────────────────────────────────────────────
        self.cfg = EngineConfig.load()
        self.engine = InputEngine(self.cfg)
        self.capture: Optional[InputCapture] = None
        self._engine_running = False
        self._mapping_capture: Optional[str] = None
        self._mapping_entries: dict[str, ctk.CTkEntry] = {}
        self._macro_controls: dict[str, tuple[ctk.CTkSlider, ctk.CTkLabel, str, str]] = {}
        self._save_after_id: Optional[str] = None
        self._hotkey_listener: Optional[keyboard.Listener] = None
        self._toggle_key_down = False
        self._auxilio_ai_dir = Path(__file__).resolve().parent.parent / "auxilio_ai"
        self._aux_ai_target_images_dir = (
            Path(__file__).resolve().parent.parent / "assets" / "target"
        )
        self._aux_ai_preview_photo = None
        self._auxilio_ai_data_dir = user_data_root() / "auxilio_ai"
        self._auxilio_ai_env_dir = auxilio_ai_environment_root()
        self._auxilio_ai_process: Optional[subprocess.Popen] = None
        self._auxilio_ai_started_at: Optional[float] = None
        self._auxilio_ai_started_model_path: Optional[Path] = None
        self._auxilio_ai_log_offset = 0
        self._auxilio_ai_model_ready = False
        self._auxilio_ai_poll_id: Optional[str] = None
        self._auxilio_ai_setup_process: Optional[subprocess.Popen] = None
        self._auxilio_ai_setup_poll_id: Optional[str] = None
        self._auxilio_ai_setup_stage: Optional[str] = None
        self._auxilio_ai_capture_target: Optional[str] = None
        self._auxilio_ai_restart_after_stop = False
        self._auxilio_ai_stopping = False
        self._auxilio_ai_model_ready = False
        self._auxilio_ai_menu_key_down = False
        self._aux_ai_pages = {}
        self._aux_ai_view_vars = {}
        self._aux_ai_model_classes = []
        self._aux_ai_last_model_metadata = None
        self._current_tab = "home"
        self._auxilio_ai_settings = self._load_auxilio_ai_settings()
        self._recoil_profiles = load_recoil_profiles()
        try:
            self._profiles = load_profiles()
        except (OSError, ValueError, TypeError) as exc:
            logger.exception("Failed to load saved profiles.")
            self._profiles = {}
            messagebox.showerror("Erro ao carregar perfis", str(exc), parent=self)

        # ── Layout ────────────────────────────────────────────
        self.grid_columnconfigure(0, weight=0)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self._build_sidebar()
        self._build_main()

        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(0, self._start_global_hotkey_listener)

        # Default tab
        self._show_tab("home")

    # ══════════════════════════════════════════════════════════
    # SIDEBAR
    # ══════════════════════════════════════════════════════════
    def _build_sidebar(self):
        self.sidebar = ctk.CTkFrame(
            self, width=self.sidebar_width, corner_radius=0,
            fg_color=T.BG_PANEL, border_width=0
        )
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_propagate(False)
        self.sidebar.grid_columnconfigure(0, weight=1)
        self.sidebar.grid_rowconfigure(8, weight=1)

        # Brand — "BioSync | MENU" centered; fonte MODERN WARFARE.otf
        brand_wrap = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        brand_wrap.grid(row=0, column=0, padx=4, pady=(28, 2), sticky="ew")
        brand_wrap.grid_columnconfigure(0, weight=1)

        brand_row = ctk.CTkFrame(brand_wrap, fg_color="transparent")
        brand_row.grid(row=0, column=0)

        _bf = T.brand_font(15)

        ctk.CTkLabel(
            brand_row, text="BioSync",
            font=_bf, text_color=T.WHITE_LOGO
        ).pack(side="left")

        ctk.CTkLabel(
            brand_row, text=" | ",
            font=_bf, text_color=T.TEXT_DIM
        ).pack(side="left")

        ctk.CTkLabel(
            brand_row, text="MENU",
            font=_bf, text_color=T.GOLD
        ).pack(side="left")

        accent_bar = ctk.CTkFrame(
            self.sidebar, height=3, corner_radius=1,
            fg_color=T.GOLD
        )
        accent_bar.grid(row=1, column=0, padx=20, pady=(6, 6), sticky="ew")

        sub = ctk.CTkLabel(
            self.sidebar, text="AA HUB  ·  MW / WARZONE",
            font=T.FONT_SMALL, text_color=T.TEXT_MUTED, anchor="center"
        )
        sub.grid(row=2, column=0, padx=12, pady=(0, 20), sticky="ew")

        # Nav buttons
        self._nav_btns: dict[str, ctk.CTkButton] = {}
        nav = [
            ("home",   "HOME"),
            ("sens",   "SENSITIVITY"),
            ("map",    "MAPPING"),
            ("macro",  "MACROS"),
            ("auxilio_ai", "AUXILIO-AI"),
        ]
        for i, (key, label) in enumerate(nav):
            btn = ctk.CTkButton(
                self.sidebar, text=label, anchor="w",
                font=T.FONT_HUD, height=40, corner_radius=6,
                fg_color="transparent", hover_color=T.BG_CARD_HOVER,
                text_color=T.TEXT_MUTED,
                command=lambda k=key: self._show_tab(k)
            )
            btn.grid(row=3 + i, column=0, padx=12, pady=3, sticky="ew")
            self._nav_btns[key] = btn

        self.user_btn = ctk.CTkButton(
            self.sidebar, text="USER  ·  CONTA",
            anchor="w", font=T.FONT_HUD, height=38, corner_radius=6,
            fg_color="transparent", hover_color=T.BG_CARD_HOVER,
            text_color=T.TEXT_MUTED,
            command=lambda: self._show_tab("user"),
        )
        self.user_btn.grid(row=9, column=0, padx=12, pady=(0, 8), sticky="ew")

        # Status + Toggle
        self.lbl_status = ctk.CTkLabel(
            self.sidebar, text="● STANDBY",
            font=T.FONT_HUD, text_color=T.TEXT_DIM
        )
        self.lbl_status.grid(row=10, column=0, padx=20, pady=(0, 6), sticky="w")

        self.btn_toggle = ctk.CTkButton(
            self.sidebar, text="ARM ENGINE",
            font=("Segoe UI", 13, "bold"), height=44, corner_radius=8,
            fg_color=T.GOLD, hover_color=T.GOLD_DIM,
            text_color=T.BG_DEEP,
            command=self._toggle_engine
        )
        self.btn_toggle.grid(row=11, column=0, padx=16, pady=(0, 14), sticky="ew")

    # ══════════════════════════════════════════════════════════
    # MAIN CONTAINER + TABS
    # ══════════════════════════════════════════════════════════
    def _build_main(self):
        self.main = ctk.CTkFrame(self, corner_radius=0, fg_color=T.BG_DEEP)
        self.main.grid(row=0, column=1, sticky="nsew")
        self.main.grid_columnconfigure(0, weight=1)
        self.main.grid_rowconfigure(0, weight=1)

        self.tabs: dict[str, ctk.CTkFrame] = {}
        for key in ("home", "sens", "map", "macro", "auxilio_ai", "user"):
            frame = ctk.CTkFrame(self.main, corner_radius=0, fg_color=T.BG_DEEP)
            frame.grid(row=0, column=0, sticky="nsew")
            frame.grid_columnconfigure(0, weight=1)
            self.tabs[key] = frame

        self._build_home()
        self._build_sens()
        self._build_map()
        self._build_macro()
        self._build_auxilio_ai()
        self._build_user()

    def _show_tab(self, key: str):
        for k, f in self.tabs.items():
            f.grid_remove()
        self.tabs[key].grid()
        self._current_tab = key
        for k, btn in self._nav_btns.items():
            if k == key:
                btn.configure(fg_color=T.BG_CARD, text_color=T.GOLD)
            else:
                btn.configure(fg_color="transparent", text_color=T.TEXT_MUTED)
        self.user_btn.configure(
            fg_color=T.BG_CARD if key == "user" else "transparent",
            text_color=T.GOLD if key == "user" else T.TEXT_MUTED,
        )

    def _build_auxilio_ai(self):
        f = self.tabs["auxilio_ai"]
        f.grid_columnconfigure(0, weight=1)
        f.grid_rowconfigure(2, weight=1)

        colors = {
            "panel": "#191B27",
            "field": "#242634",
            "line": "#2B2D3B",
            "text": "#E8EAF0",
            "muted": "#9196A8",
            "accent": "#8A2BE2",
            "accent_hover": "#7022B8",
            "cyan": "#00D9EE",
            "success": "#00E566",
        }
        self._aux_ai_colors = colors

        header = ctk.CTkFrame(f, fg_color="transparent")
        header.grid(row=0, column=0, padx=14, pady=(12, 8), sticky="ew")
        header.grid_columnconfigure(0, weight=1)
        self._aux_ai_page_title = ctk.CTkLabel(
            header, text="Configuracao",
            font=("Segoe UI", 22, "bold"), text_color=colors["cyan"],
        )
        self._aux_ai_page_title.grid(row=0, column=0, sticky="w")
        self._aux_ai_page_subtitle = ctk.CTkLabel(
            header, text="FOV, resposta e atalhos",
            font=("Segoe UI", 10), text_color=colors["muted"],
        )
        self._aux_ai_page_subtitle.grid(row=1, column=0, sticky="w", pady=(2, 0))
        self._aux_ai_page_selector = ctk.CTkSegmentedButton(
            header,
            values=["Aim", "Views"],
            selected_color=colors["accent"],
            selected_hover_color=colors["accent_hover"],
            unselected_color=colors["field"],
            unselected_hover_color=colors["line"],
            text_color=colors["text"],
            command=self._show_aux_ai_page,
        )
        self._aux_ai_page_selector.grid(row=0, column=1, rowspan=2, padx=(8, 10))
        self._aux_ai_page_selector.set("Aim")
        ctk.CTkButton(
            header, text="Ocultar", width=88, height=34, corner_radius=7,
            fg_color="#242634", hover_color="#2B2D3B",
            text_color=colors["text"], command=self._hide_aux_ai_panel,
        ).grid(row=0, column=2, sticky="e")
        self._auxilio_ai_status = ctk.CTkLabel(
            header, text="● PARADO",
            font=T.FONT_HUD, text_color=T.TEXT_DIM,
        )
        self._auxilio_ai_status.grid(row=1, column=2, sticky="e")

        content = ctk.CTkFrame(f, fg_color="transparent")
        content.grid(row=2, column=0, padx=14, pady=(0, 8), sticky="nsew")
        content.grid_columnconfigure(0, weight=1)
        content.grid_rowconfigure(0, weight=1)

        aim_page = ctk.CTkFrame(content, fg_color="transparent")
        aim_page.grid_columnconfigure((0, 1), weight=1, uniform="aux-ai-columns")
        aim_page.grid_rowconfigure(0, weight=1)
        aim_page.grid(row=0, column=0, sticky="nsew")
        views_page = ctk.CTkScrollableFrame(
            content, fg_color="transparent", corner_radius=0,
        )
        views_page.grid_columnconfigure((0, 1), weight=1, uniform="aux-ai-views")
        self._aux_ai_pages = {"Aim": aim_page, "Views": views_page}

        acquisition = self._aux_ai_panel(
            aim_page, "Area de deteccao",
            "Defina o tamanho e o ponto de referencia",
        )
        acquisition.grid(row=0, column=0, sticky="nsew", padx=(0, 7))
        response = self._aux_ai_panel(
            aim_page, "Resposta e atalhos",
            "Configure controles de forma independente",
        )
        response.grid(row=0, column=1, sticky="nsew", padx=(7, 0))

        model_panel = self._aux_ai_panel(
            views_page, "Perfil do modelo",
            "Selecione um modelo ONNX carregado dinamicamente",
        )
        model_panel.grid(row=0, column=0, columnspan=2, sticky="new", padx=6, pady=(0, 6))
        self._aux_ai_model_profiles = discover_model_profiles(
            self._auxilio_ai_dir / "models"
        )
        selected_model = Path(self._auxilio_ai_settings["model_path"]).stem
        profile_values = list(self._aux_ai_model_profiles) or ["Nenhum modelo ONNX"]
        if self._aux_ai_model_profiles and selected_model not in self._aux_ai_model_profiles:
            selected_model = profile_values[0]
            self._auxilio_ai_settings["model_path"] = str(
                Path("models")
                / self._aux_ai_model_profiles[selected_model].name
            )
        self._aux_ai_model_profile = ctk.CTkOptionMenu(
            model_panel,
            values=profile_values,
            width=190,
            height=30,
            corner_radius=6,
            fg_color=colors["field"],
            button_color=colors["accent"],
            button_hover_color=colors["accent_hover"],
            dropdown_fg_color=colors["panel"],
            dropdown_hover_color=colors["field"],
            command=self._on_aux_ai_model_profile_change,
            state="normal" if self._aux_ai_model_profiles else "disabled",
        )
        self._aux_ai_model_profile.grid(
            row=2, column=1, sticky="e", padx=16, pady=(5, 8),
        )
        self._aux_ai_model_profile.set(
            selected_model
        )
        ctk.CTkLabel(
            model_panel, text="Perfil do modelo",
            font=("Segoe UI", 11, "bold"), text_color=colors["text"],
        ).grid(row=2, column=0, sticky="w", padx=16, pady=(5, 8))

        self._aux_ai_fov_value = ctk.CTkLabel(
            acquisition, text="", font=("Segoe UI", 10, "bold"),
            text_color=colors["cyan"],
        )
        self._aux_ai_fov_value.grid(row=2, column=1, sticky="e", padx=16, pady=(7, 3))
        ctk.CTkLabel(
            acquisition, text="Tamanho do FOV",
            font=("Segoe UI", 11, "bold"), text_color=colors["text"],
        ).grid(row=2, column=0, sticky="w", padx=16, pady=(7, 3))
        self._aux_ai_fov_slider = ctk.CTkSlider(
            acquisition, from_=160, to=640, number_of_steps=30,
            fg_color=colors["field"], progress_color=colors["accent"],
            button_color=colors["cyan"], button_hover_color="#00B8CA",
            command=self._on_aux_ai_fov_change,
        )
        self._aux_ai_fov_slider.grid(
            row=3, column=0, columnspan=2, sticky="ew", padx=16, pady=(0, 10),
        )
        self._aux_ai_fov_slider.set(self._auxilio_ai_settings["fov"])

        ctk.CTkLabel(
            acquisition, text="Ponto de referencia",
            font=("Segoe UI", 11, "bold"), text_color=colors["text"],
        ).grid(row=4, column=0, columnspan=2, sticky="w", padx=16, pady=(4, 4))
        self._aux_ai_aim_selector = ctk.CTkSegmentedButton(
            acquisition, values=["Cabeca", "Peito", "Barriga"],
            selected_color=colors["accent"], selected_hover_color=colors["accent_hover"],
            unselected_color=colors["field"], unselected_hover_color=colors["line"],
            text_color=colors["text"], corner_radius=6,
            command=self._on_aux_ai_aim_change,
        )
        self._aux_ai_aim_selector.grid(
            row=5, column=0, columnspan=2, sticky="ew", padx=16, pady=(0, 8),
        )
        self._aux_ai_aim_selector.set(self._aux_ai_aim_label(self._auxilio_ai_settings["aim_point"]))

        focus_row = ctk.CTkFrame(acquisition, fg_color="transparent")
        focus_row.grid(row=6, column=0, columnspan=2, sticky="ew", padx=16, pady=(0, 0))
        focus_row.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(
            focus_row, text="Foco atual",
            font=("Segoe UI", 11, "bold"), text_color=colors["text"],
        ).grid(row=0, column=0, sticky="w")
        self._aux_ai_focus_value = ctk.CTkLabel(
            focus_row, text="", font=("Segoe UI", 10, "bold"),
            text_color=colors["cyan"],
        )
        self._aux_ai_focus_value.grid(row=0, column=1, sticky="e")
        acquisition.grid_rowconfigure(7, weight=1)
        self._aux_ai_preview = tk.Canvas(
            acquisition, height=320, bg=colors["panel"], highlightthickness=0,
        )
        self._aux_ai_preview.grid(
            row=7, column=0, columnspan=2, sticky="nsew", padx=12, pady=(0, 8),
        )
        self._aux_ai_preview.bind("<Configure>", lambda _event: self._draw_aux_ai_preview())
        self._draw_aux_ai_preview()
        self._update_aux_ai_focus_label()

        ctk.CTkLabel(
            response, text="Tecla de ativacao",
            font=("Segoe UI", 11, "bold"), text_color=colors["text"],
        ).grid(row=2, column=0, sticky="w", padx=16, pady=(9, 4))
        self._aux_ai_activation_button = ctk.CTkButton(
            response, text=self._auxilio_ai_settings["aim_key"],
            width=132, height=34, corner_radius=6, fg_color=colors["field"],
            hover_color=colors["line"], text_color=colors["text"],
            command=lambda: self._begin_aux_ai_key_capture("aim_key"),
        )
        self._aux_ai_activation_button.grid(row=2, column=1, sticky="e", padx=16, pady=(7, 3))

        ctk.CTkLabel(
            response, text="Botoes do mouse",
            font=("Segoe UI", 10, "bold"), text_color=colors["text"],
        ).grid(row=3, column=0, sticky="w", padx=16, pady=(3, 4))
        self._aux_ai_mouse_option = ctk.CTkOptionMenu(
            response,
            values=["Selecione...", "Botao esquerdo", "Botao central", "Botao direito", "Mouse 4", "Mouse 5"],
            width=142, height=30, corner_radius=6,
            fg_color=colors["field"], button_color=colors["accent"],
            button_hover_color=colors["accent_hover"],
            dropdown_fg_color=colors["panel"], dropdown_hover_color=colors["field"],
            command=self._on_aux_ai_mouse_change,
        )
        self._aux_ai_mouse_option.grid(row=3, column=1, sticky="e", padx=16, pady=(0, 3))
        self._aux_ai_mouse_option.set(self._aux_ai_mouse_label(self._auxilio_ai_settings["aim_key"]))
        ctk.CTkLabel(
            response, text="Ou capture uma tecla pelo botao acima",
            font=("Segoe UI", 9), text_color=colors["muted"],
        ).grid(row=4, column=0, columnspan=2, sticky="w", padx=16, pady=(0, 6))

        ctk.CTkLabel(
            response, text="Atalho para abrir/fechar o menu",
            font=("Segoe UI", 11, "bold"), text_color=colors["text"],
        ).grid(row=5, column=0, sticky="w", padx=16, pady=(6, 3))
        self._aux_ai_menu_button = ctk.CTkButton(
            response, text=self._auxilio_ai_settings["menu_key"],
            width=132, height=34, corner_radius=6, fg_color=colors["field"],
            hover_color=colors["line"], text_color=colors["text"],
            command=lambda: self._begin_aux_ai_key_capture("menu_key"),
        )
        self._aux_ai_menu_button.grid(row=5, column=1, sticky="e", padx=16, pady=(3, 3))
        ctk.CTkLabel(
            response, text="Escolha uma tecla diferente da ativacao",
            font=("Segoe UI", 9), text_color=colors["muted"],
        ).grid(row=6, column=0, columnspan=2, sticky="w", padx=16, pady=(0, 12))

        ctk.CTkLabel(
            response, text="Suavizacao da resposta",
            font=("Segoe UI", 11, "bold"), text_color=colors["text"],
        ).grid(row=7, column=0, sticky="w", padx=16, pady=(4, 3))
        self._aux_ai_smoothing_value = ctk.CTkLabel(
            response, text="", font=("Segoe UI", 10, "bold"),
            text_color=colors["cyan"],
        )
        self._aux_ai_smoothing_value.grid(row=7, column=1, sticky="e", padx=16, pady=(4, 3))
        self._aux_ai_smoothing_slider = ctk.CTkSlider(
            response, from_=0.05, to=1.0, number_of_steps=95,
            fg_color=colors["field"], progress_color=colors["accent"],
            button_color=colors["cyan"], button_hover_color="#00B8CA",
            command=self._on_aux_ai_smoothing_change,
        )
        self._aux_ai_smoothing_slider.grid(
            row=8, column=0, columnspan=2, sticky="ew", padx=16, pady=(0, 4),
        )
        self._aux_ai_smoothing_slider.set(self._auxilio_ai_settings["smoothing"])
        ctk.CTkLabel(
            response, text="Humanizer · velocidade ate o alvo",
            font=("Segoe UI", 11, "bold"), text_color=colors["text"],
        ).grid(row=9, column=0, sticky="w", padx=16, pady=(8, 3))
        self._aux_ai_humanizer_value = ctk.CTkLabel(
            response, text="", font=("Segoe UI", 10, "bold"),
            text_color=colors["cyan"],
        )
        self._aux_ai_humanizer_value.grid(row=9, column=1, sticky="e", padx=16, pady=(8, 3))
        self._aux_ai_humanizer_slider = ctk.CTkSlider(
            response, from_=200, to=4000, number_of_steps=38,
            fg_color=colors["field"], progress_color=colors["accent"],
            button_color=colors["cyan"], button_hover_color="#00B8CA",
            command=self._on_aux_ai_humanizer_change,
        )
        self._aux_ai_humanizer_slider.grid(
            row=10, column=0, columnspan=2, sticky="ew", padx=16, pady=(0, 12),
        )
        self._aux_ai_humanizer_slider.set(
            self._auxilio_ai_settings["humanizer_speed"]
        )
        self._on_aux_ai_fov_change(self._auxilio_ai_settings["fov"])
        self._on_aux_ai_smoothing_change(self._auxilio_ai_settings["smoothing"])
        self._on_aux_ai_humanizer_change(
            self._auxilio_ai_settings["humanizer_speed"]
        )
        self._build_aux_ai_views(views_page)
        self._refresh_aux_ai_model_classes()

        footer = ctk.CTkFrame(f, fg_color="transparent")
        footer.grid(row=3, column=0, padx=14, pady=(0, 12), sticky="ew")
        footer.grid_columnconfigure(0, weight=1)
        self._aux_ai_message = ctk.CTkLabel(
            footer, text="Pronto", font=("Segoe UI", 10),
            text_color=colors["muted"], anchor="w",
        )
        self._aux_ai_message.grid(row=0, column=0, sticky="w")
        ctk.CTkButton(
            footer, text="Salvar perfil", width=112, height=36,
            corner_radius=7, fg_color=colors["field"], hover_color=colors["line"],
            text_color=colors["text"], command=self._save_aux_ai_profile,
        ).grid(row=0, column=1, padx=(6, 0))
        ctk.CTkButton(
            footer, text="Aplicar", width=92, height=36,
            corner_radius=7, fg_color=colors["accent"], hover_color=colors["accent_hover"],
            text_color="#FFFFFF", command=self._apply_aux_ai_settings,
        ).grid(row=0, column=2, padx=(6, 0))
        self._aux_ai_start_button = ctk.CTkButton(
            footer, text="Iniciar Aux-AI", width=116, height=36,
            corner_radius=7, fg_color=colors["success"], hover_color="#00B85A",
            text_color="#10131A", command=self._start_auxilio_ai,
        )
        self._aux_ai_start_button.grid(row=0, column=3, padx=(6, 0))
        self._aux_ai_stop_button = ctk.CTkButton(
            footer, text="Encerrar Aux-AI", width=126, height=36,
            corner_radius=7, fg_color="#343746", hover_color="#45495A",
            text_color=colors["text"], state="disabled",
            command=self._stop_auxilio_ai,
        )
        self._aux_ai_stop_button.grid(row=0, column=4, padx=(6, 0))

        self.bind("<KeyPress>", self._on_aux_ai_key_press, add="+")
        self._show_aux_ai_page("Aim")

    def _hide_aux_ai_panel(self):
        self._show_tab("home")

    def _show_aux_ai_page(self, page):
        if page not in self._aux_ai_pages:
            return
        for frame in self._aux_ai_pages.values():
            frame.grid_remove()
        self._aux_ai_pages[page].grid(row=0, column=0, sticky="nsew")
        self._aux_ai_page_title.configure(text="Configuracao" if page == "Aim" else "Views")
        self._aux_ai_page_subtitle.configure(
            text="FOV, resposta e atalhos" if page == "Aim" else "ESP, distancia e filtros de deteccao"
        )
        if page == "Views":
            self._refresh_aux_ai_model_classes()

    def _build_aux_ai_views(self, page):
        cards = (
            ("ESP Box", "Caixa, estilo e cor", (
                ("switch", "esp_enabled", "Ativar boxes"),
                ("option", "esp_style", "Estilo", ["Normal", "Filled", "Corner"]),
                ("slider", "esp_thickness", "Espessura", 1, 8, 7, ""),
                ("color", "esp_color", "Cor da caixa"),
                ("slider", "esp_opacity", "Opacidade", 0, 100, 100, "%"),
            )),
            ("Distancia", "Area da caixa como proxy de proximidade", (
                ("switch", "distance_filter", "Filtrar por distancia"),
                ("slider", "min_distance", "Distancia minima (perto)", 0, 1, 100, "%"),
                ("slider", "max_distance", "Distancia maxima (longe)", 0, 1, 100, "%"),
            )),
            ("Filtro de falso positivo", "Confidence, IOU e dimensoes", (
                ("slider", "min_confidence", "Confidence minima", 0, 1, 100, ""),
                ("slider", "iou_threshold", "IOU", 0, 1, 100, ""),
                ("slider", "max_detections", "Maximo de deteccoes", 1, 100, 99, ""),
                ("switch", "ignore_small_targets", "Ignorar alvos pequenos"),
                ("slider", "min_box_area", "Area minima da caixa", 0, 0.25, 250, "%"),
                ("switch", "ignore_large_targets", "Ignorar alvos grandes"),
                ("slider", "max_box_area", "Area maxima da caixa", 0, 1, 100, "%"),
            )),
            ("Linhas e indicadores", "Alvo selecionado", (
                ("switch", "snap_line", "Linha do centro ate o alvo"),
                ("color", "snap_line_color", "Cor da linha"),
                ("slider", "snap_line_thickness", "Espessura da linha", 1, 8, 7, ""),
                ("switch", "show_aim_marker", "Mostrar ponto de mira"),
                ("color", "marker_color", "Cor do marcador"),
            )),
            ("Skeleton / zonas", "Divisao proporcional dentro da caixa", (
                ("switch", "show_body_zones", "Desenhar zonas corporais"),
                ("color", "head_color", "Cor da cabeca"),
                ("color", "chest_color", "Cor do peito"),
                ("color", "belly_color", "Cor da barriga"),
            )),
            ("FOV visual", "Circulo do campo de visao", (
                ("switch", "show_fov", "Mostrar circulo FOV"),
                ("color", "fov_color", "Cor do circulo"),
                ("slider", "overlay_opacity", "Opacidade do overlay", 10, 100, 90, "%"),
            )),
            ("Classes do modelo", "Filtra as classes lidas do metadata ONNX", (
                ("entry", "target_classes", "Classes-alvo separadas por virgula"),
            )),
        )
        for index, (title, description, controls) in enumerate(cards):
            card = self._aux_ai_panel(page, title, description)
            card.grid(row=index // 2 + 1, column=index % 2, sticky="new", padx=6, pady=6)
            for row, control in enumerate(controls, start=2):
                self._add_aux_ai_view_control(card, row, control)
        page.grid_rowconfigure((1, 2, 3, 4), weight=0)

    def _add_aux_ai_view_control(self, card, row, control):
        kind, key, label, *options = control
        colors = self._aux_ai_colors
        field_label = ctk.CTkLabel(
            card, text=label, font=("Segoe UI", 10), text_color=colors["text"],
        )
        field_label.grid(row=row, column=0, sticky="w", padx=14, pady=4)
        value = self._auxilio_ai_settings.get(key, DEFAULT_VIEW_SETTINGS.get(key, ""))
        variable_type = tk.BooleanVar if isinstance(value, bool) else (
            tk.StringVar if isinstance(value, str) else tk.DoubleVar
        )
        variable = variable_type(master=self, value=value)
        self._aux_ai_view_vars[key] = variable
        if kind == "switch":
            ctk.CTkSwitch(
                card, text="", variable=variable, onvalue=True, offvalue=False,
                progress_color=colors["accent"], button_color=colors["cyan"],
            ).grid(row=row, column=1, sticky="e", padx=14, pady=3)
        elif kind == "option":
            ctk.CTkOptionMenu(
                card, variable=variable, values=options[0], width=112, height=28,
                fg_color=colors["field"], button_color=colors["accent"],
                dropdown_fg_color=colors["panel"],
            ).grid(row=row, column=1, sticky="e", padx=14, pady=3)
        elif kind == "entry":
            entry = ctk.CTkEntry(
                card, textvariable=variable, width=150, height=28,
                fg_color=colors["field"], border_color=colors["line"],
            )
            entry.grid(row=row, column=1, sticky="e", padx=14, pady=3)
            self._aux_ai_target_classes_entry = entry
            self._aux_ai_target_classes_label = field_label
        elif kind == "color":
            controls_frame = ctk.CTkFrame(card, fg_color="transparent")
            controls_frame.grid(row=row, column=1, sticky="e", padx=14, pady=3)
            preset_var = tk.StringVar(master=self)
            preset_var.set(self._aux_ai_color_label(value))
            ctk.CTkOptionMenu(
                controls_frame,
                variable=preset_var,
                values=["Verde", "Ciano", "Amarelo", "Vermelho", "Branco"],
                command=lambda preset, target=variable: target.set(self._aux_ai_color_value(preset)),
                width=83,
                height=28,
                fg_color=colors["field"],
                button_color=colors["accent"],
                dropdown_fg_color=colors["panel"],
            ).pack(side="left", padx=(0, 4))
            ctk.CTkEntry(
                controls_frame, textvariable=variable, width=88, height=28,
                fg_color=colors["field"], border_color=colors["line"],
            ).pack(side="left")
        else:
            lower, upper, steps, suffix = options
            slider_value = float(value)
            if key in ("min_box_area", "max_box_area"):
                slider_value *= 100
            slider = ctk.CTkSlider(
                card, from_=lower, to=upper, number_of_steps=steps, width=125,
                fg_color=colors["field"], progress_color=colors["accent"],
                button_color=colors["cyan"],
                command=lambda current, k=key, unit=suffix: self._on_aux_ai_view_slider(k, current, unit),
            )
            slider.grid(row=row, column=1, sticky="e", padx=(4, 14), pady=3)
            slider.set(slider_value)
            self._aux_ai_view_vars[key] = variable
            initial_display = slider_value
            label_value = f"{initial_display:.2f}" if key in ("min_confidence", "iou_threshold") else f"{initial_display:.0f}{suffix}"
            value_label = ctk.CTkLabel(card, text=label_value, width=42, text_color=colors["cyan"])
            value_label.grid(row=row, column=2, sticky="e", padx=(0, 8))
            setattr(self, f"_aux_ai_view_label_{key}", value_label)
            setattr(self, f"_aux_ai_view_suffix_{key}", suffix)

    @staticmethod
    def _aux_ai_color_value(preset):
        return {
            "Verde": "#32D7A0",
            "Ciano": "#32C7D7",
            "Amarelo": "#F2C94C",
            "Vermelho": "#F06464",
            "Branco": "#E8EEF2",
        }[preset]

    @classmethod
    def _aux_ai_color_label(cls, color):
        for label in ("Verde", "Ciano", "Amarelo", "Vermelho", "Branco"):
            if cls._aux_ai_color_value(label).casefold() == str(color).casefold():
                return label
        return "Verde"

    def _on_aux_ai_view_slider(self, key, value, suffix):
        converted = float(value)
        if key in ("min_box_area", "max_box_area"):
            converted /= 100
        self._aux_ai_view_vars[key].set(converted)
        label = getattr(self, f"_aux_ai_view_label_{key}", None)
        if label is not None:
            text = f"{converted:.2f}" if key in ("min_confidence", "iou_threshold") else f"{float(value):.0f}{suffix}"
            label.configure(text=text)

    def _refresh_aux_ai_model_classes(self):
        metadata_path = self._auxilio_ai_data_dir / "profiles" / "model_metadata.json"
        configured_model = Path(self._auxilio_ai_settings["model_path"])
        if not configured_model.is_absolute():
            configured_model = (self._auxilio_ai_dir / configured_model).resolve()
        try:
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            if Path(metadata.get("model_path", "")).resolve() != configured_model:
                self._clear_aux_ai_model_classes()
                return
            classes = metadata.get("class_names", {})
            self._aux_ai_model_classes = list(classes.values()) if isinstance(classes, dict) else list(classes)
            metadata_signature = (str(configured_model), tuple(self._aux_ai_model_classes))
            if metadata_signature == self._aux_ai_last_model_metadata:
                return
            self._aux_ai_last_model_metadata = metadata_signature
            if len(self._aux_ai_model_classes) == 1:
                self._aux_ai_view_vars["target_classes"].set(self._aux_ai_model_classes[0])
                self._aux_ai_target_classes_entry.configure(state="disabled")
                self._aux_ai_target_classes_label.configure(
                    text=f"Classe unica ({self._aux_ai_model_classes[0]})"
                )
            else:
                self._aux_ai_target_classes_entry.configure(state="normal")
                self._aux_ai_target_classes_label.configure(
                    text=f"Classes: {', '.join(self._aux_ai_model_classes)}"
                )
        except FileNotFoundError:
            self._clear_aux_ai_model_classes()
        except (OSError, json.JSONDecodeError, TypeError) as exc:
            logger.warning("Could not read ONNX class metadata for Views: %s", exc)

    def _clear_aux_ai_model_classes(self):
        self._aux_ai_model_classes = []
        self._aux_ai_last_model_metadata = None
        if hasattr(self, "_aux_ai_target_classes_entry"):
            self._aux_ai_target_classes_entry.configure(state="normal")
            self._aux_ai_target_classes_label.configure(
                text="Classes lidas ao iniciar o modelo"
            )

    def _on_aux_ai_model_profile_change(self, profile_name):
        model_path = self._aux_ai_model_profiles.get(profile_name)
        if model_path is None:
            raise ValueError(f"Perfil ONNX desconhecido: {profile_name}")
        self._auxilio_ai_settings["model_path"] = str(
            Path("models") / model_path.name
        )
        self._aux_ai_view_vars["target_classes"].set("")
        self._clear_aux_ai_model_classes()
        self._draw_aux_ai_preview()
        self._refresh_aux_ai_model_classes()
        self._update_aux_ai_profile_preview()

    def _aux_ai_panel(self, parent, title, description):
        colors = self._aux_ai_colors
        panel = ctk.CTkFrame(parent, fg_color=colors["panel"], corner_radius=8)
        panel.grid_columnconfigure((0, 1), weight=1)
        ctk.CTkLabel(
            panel, text=title, font=("Segoe UI", 15, "bold"),
            text_color=colors["text"],
        ).grid(row=0, column=0, columnspan=2, sticky="w", padx=16, pady=(14, 0))
        ctk.CTkLabel(
            panel, text=description, font=("Segoe UI", 9),
            text_color=colors["muted"],
        ).grid(row=1, column=0, columnspan=2, sticky="w", padx=16, pady=(3, 8))
        return panel

    def _load_auxilio_ai_settings(self):
        defaults = {
            "fov": 320,
            "smoothing": 0.40,
            "humanizer_speed": 2000,
            "model_path": "models/BioSync-Warzone.onnx",
            "aim_point": "chest",
            "aim_key": "Right mouse",
            "menu_key": "X",
            "show_fov": True,
            "fov_color": "#32D7A0",
            "overlay_opacity": 85,
            **DEFAULT_VIEW_SETTINGS,
            "target_classes": "Enemy,character,exoai,player,bot,head",
        }
        path = self._auxilio_ai_data_dir / "profiles" / "active.json"
        config = configparser.ConfigParser()
        config.read(self._auxilio_ai_dir / "config.ini", encoding="utf-8")
        defaults["model_path"] = normalize_model_profile_path(config.get(
            "AI options", "AI_model_path", fallback=defaults["model_path"],
        ))
        defaults["target_classes"] = config.get(
            "AI options", "target_classes",
            fallback=defaults["target_classes"],
        )
        defaults["humanizer_speed"] = config.getfloat(
            "Mouse settings", "humanizer_speed",
            fallback=defaults["humanizer_speed"],
        )
        try:
            values = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(values, dict):
                defaults.update({key: value for key, value in values.items() if key in defaults})
                defaults["model_path"] = normalize_model_profile_path(
                    str(defaults["model_path"])
                )
        except FileNotFoundError:
            pass
        except (OSError, json.JSONDecodeError, TypeError) as exc:
            logger.exception("Could not read Auxilio-AI active profile: %s", exc)
        if self._aux_ai_vkey(defaults["menu_key"]) == self.cfg.vk_toggle:
            defaults["menu_key"] = next(
                f"F{number}" for number in (7, 6, 5, 4, 3, 2, 1, 9, 10, 11, 12)
                if self._aux_ai_vkey(f"F{number}") != self.cfg.vk_toggle
                and f"F{number}" != defaults["aim_key"]
            )
        return defaults

    @staticmethod
    def _aux_ai_aim_label(value):
        return {"head": "Cabeca", "chest": "Peito", "belly": "Barriga"}.get(value, "Peito")

    @staticmethod
    def _aux_ai_mouse_label(value):
        return {
            "Left mouse": "Botao esquerdo",
            "Middle mouse": "Botao central",
            "Right mouse": "Botao direito",
            "Mouse 4": "Mouse 4",
            "Mouse 5": "Mouse 5",
        }.get(value, "Selecione...")

    @staticmethod
    def _aux_ai_mouse_key(value):
        return {
            "Botao esquerdo": "Left mouse",
            "Botao central": "Middle mouse",
            "Botao direito": "Right mouse",
            "Mouse 4": "Mouse 4",
            "Mouse 5": "Mouse 5",
        }.get(value)

    def _on_aux_ai_fov_change(self, value):
        fov = max(160, min(640, int(round(float(value) / 16) * 16)))
        self._auxilio_ai_settings["fov"] = fov
        self._aux_ai_fov_value.configure(text=f"{fov} px")
        self._send_aux_ai_command({"type": "fov", "value": fov})
        self._update_aux_ai_profile_preview()

    def _send_aux_ai_command(self, command):
        process = self._auxilio_ai_process
        if process is None or process.poll() is not None or process.stdin is None:
            return False
        try:
            process.stdin.write(json.dumps(command) + "\n")
            process.stdin.flush()
            return True
        except (OSError, BrokenPipeError) as exc:
            logger.exception("Could not send a live settings command to Auxilio-AI.")
            self._aux_ai_message.configure(text=f"Falha ao enviar ajuste em tempo real: {exc}")
            return False

    def _on_aux_ai_smoothing_change(self, value):
        smoothing = max(0.05, min(1.0, round(float(value), 2)))
        self._auxilio_ai_settings["smoothing"] = smoothing
        self._aux_ai_smoothing_value.configure(text=f"{smoothing:.2f}")
        self._update_aux_ai_profile_preview()

    def _on_aux_ai_humanizer_change(self, value):
        speed = max(200, min(4000, int(round(float(value) / 100) * 100)))
        self._auxilio_ai_settings["humanizer_speed"] = speed
        self._aux_ai_humanizer_value.configure(text=f"{speed} px/s")
        self._update_aux_ai_profile_preview()

    def _on_aux_ai_aim_change(self, value):
        self._auxilio_ai_settings["aim_point"] = {
            "Cabeca": "head", "Peito": "chest", "Barriga": "belly",
        }[value]
        self._update_aux_ai_focus_label()
        self._draw_aux_ai_preview()
        self._update_aux_ai_profile_preview()

    def _on_aux_ai_mouse_change(self, label):
        key = self._aux_ai_mouse_key(label)
        if key is None:
            return
        self._auxilio_ai_settings["aim_key"] = key
        self._aux_ai_activation_button.configure(text=key)
        self._update_aux_ai_profile_preview()

    def _update_aux_ai_focus_label(self):
        focus = self._auxilio_ai_settings["aim_point"]
        label = self._aux_ai_aim_label(focus).upper()
        self._aux_ai_focus_value.configure(
            text=label,
            text_color=AUX_AI_FOCUS_COLORS.get(focus, self._aux_ai_colors["cyan"]),
        )

    def _draw_aux_ai_preview(self):
        canvas = getattr(self, "_aux_ai_preview", None)
        if canvas is None or not canvas.winfo_exists():
            return
        canvas.delete("all")
        width = max(canvas.winfo_width(), 300)
        height = max(canvas.winfo_height(), 160)
        if self._draw_aux_ai_image_preview(canvas, width, height):
            return
        center_x = width * 0.36
        head_y = height * 0.19
        body = "#1A1A24"
        fabric = "#222431"
        armor = "#303040"
        armor_light = "#3A3A4C"
        outline = "#656579"
        detail = "#85859A"

        def point(x_ratio, y_ratio):
            return center_x + width * x_ratio, height * y_ratio

        def polygon(points, fill, stroke=outline, stroke_width=2):
            coordinates = [
                coordinate
                for x_ratio, y_ratio in points
                for coordinate in point(x_ratio, y_ratio)
            ]
            canvas.create_polygon(
                *coordinates,
                fill=fill,
                outline=stroke,
                width=stroke_width,
                smooth=True,
                splinesteps=10,
            )

        def seam(x1, y1, x2, y2, color=detail, line_width=2):
            canvas.create_line(*point(x1, y1), *point(x2, y2), fill=color, width=line_width)

        # Build the soldier from rear limbs forward so the vest sits naturally
        # over the uniform while each region remains a solid, readable shape.
        for direction in (-1, 1):
            polygon([
                (direction*.12, .34), (direction*.18, .36),
                (direction*.22, .49), (direction*.215, .57),
                (direction*.18, .59), (direction*.155, .55),
                (direction*.15, .45),
            ], fabric, stroke_width=2)
            polygon([
                (direction*.17, .56), (direction*.215, .55),
                (direction*.225, .60), (direction*.20, .625),
                (direction*.165, .615),
            ], armor, stroke_width=1)
            polygon([
                (direction*.18, .60), (direction*.205, .605),
                (direction*.215, .64), (direction*.19, .65),
                (direction*.17, .635),
            ], armor_light, stroke_width=1)
            polygon([
                (direction*.04, .68), (direction*.095, .68),
                (direction*.105, .77), (direction*.075, .81),
                (direction*.025, .79), (direction*.02, .74),
            ], fabric)
            polygon([
                (direction*.025, .78), (direction*.075, .79),
                (direction*.085, .84), (direction*.075, .87),
                (direction*.025, .86), (direction*.015, .83),
            ], armor_light, stroke_width=2)
            polygon([
                (direction*.025, .87), (direction*.075, .87),
                (direction*.085, .94), (direction*.065, .97),
                (direction*.015, .965), (direction*.005, .94),
            ], body, stroke_width=2)
            seam(direction*.045, .69, direction*.045, .76, "#4D4D61", 1)
            seam(direction*.045, .82, direction*.045, .85, outline, 2)
            seam(direction*.04, .88, direction*.04, .94, "#4D4D61", 1)

        # Angular helmet and face mask; the head focus marker is centered on
        # the mask itself, rather than on the helmet crown.
        polygon([
            (-.055, .13), (-.05, .075), (-.025, .045),
            (.025, .045), (.05, .075), (.055, .13),
            (.04, .155), (-.04, .155),
        ], armor, stroke=outline, stroke_width=2)
        polygon([
            (-.043, .135), (-.036, .16), (-.03, .225),
            (-.018, .255), (.018, .255), (.03, .225),
            (.036, .16), (.043, .135), (.025, .15),
            (-.025, .15),
        ], body, stroke="#77778C", stroke_width=2)
        polygon([
            (-.035, .16), (-.018, .153), (.018, .153),
            (.035, .16), (.025, .18), (-.025, .18),
        ], armor_light, stroke="#5F5F73", stroke_width=1)
        seam(-.022, .205, .022, .205, "#67677C", 2)
        seam(-.018, .225, .018, .225, "#4F4F62", 2)
        polygon([
            (-.052, .105), (-.036, .09), (.036, .09), (.052, .105),
            (.058, .13), (.035, .14), (-.035, .14), (-.058, .13),
        ], "#292936", stroke="#77778C", stroke_width=1)
        seam(-.045, .12, .045, .12, detail, 1)

        # Neck, broad shoulder plates, and uniform torso.
        polygon([
            (-.025, .245), (-.025, .30), (-.12, .315),
            (-.155, .35), (-.12, .62), (-.08, .69),
            (.08, .69), (.12, .62), (.155, .35),
            (.12, .315), (.025, .30), (.025, .245),
        ], fabric, stroke_width=2)
        polygon([
            (-.13, .315), (-.075, .29), (-.035, .315),
            (-.045, .36), (-.12, .37), (-.16, .35),
        ], armor, stroke_width=2)
        polygon([
            (.13, .315), (.075, .29), (.035, .315),
            (.045, .36), (.12, .37), (.16, .35),
        ], armor, stroke_width=2)
        seam(-.135, .345, -.07, .355, detail, 1)
        seam(.135, .345, .07, .355, detail, 1)

        # Layered plate carrier, shoulder straps, and front equipment pouches.
        polygon([
            (-.105, .34), (-.075, .32), (.075, .32), (.105, .34),
            (.115, .44), (.095, .57), (.075, .615),
            (-.075, .615), (-.095, .57), (-.115, .44),
        ], armor, stroke="#77778C", stroke_width=2)
        polygon([
            (-.075, .345), (-.055, .33), (-.035, .35),
            (-.045, .405), (-.075, .42),
        ], armor_light, stroke="#656579", stroke_width=1)
        polygon([
            (.075, .345), (.055, .33), (.035, .35),
            (.045, .405), (.075, .42),
        ], armor_light, stroke="#656579", stroke_width=1)
        polygon([
            (-.045, .36), (-.03, .345), (.03, .345),
            (.045, .36), (.07, .48), (.055, .55),
            (-.055, .55), (-.07, .48),
        ], "#292936", stroke="#85859A", stroke_width=2)
        seam(0, .36, 0, .54, "#85859A", 1)
        seam(-.06, .435, .06, .435, "#77778C", 1)
        for x_ratio in (-.072, -.025, .025, .072):
            polygon([
                (x_ratio-.016, .49), (x_ratio+.016, .49),
                (x_ratio+.018, .555), (x_ratio-.018, .555),
            ], armor_light, stroke="#5D5D70", stroke_width=1)
            seam(x_ratio-.009, .505, x_ratio+.009, .505, detail, 1)

        # Utility belt and abdomen pouches align the lower reference marker.
        polygon([
            (-.09, .59), (-.08, .575), (.08, .575),
            (.09, .59), (.085, .635), (-.085, .635),
        ], "#292936", stroke="#85859A", stroke_width=2)
        polygon([
            (-.018, .585), (.018, .585), (.022, .625), (-.022, .625),
        ], armor_light, stroke=detail, stroke_width=1)
        for x_ratio in (-.065, -.033, .033, .065):
            polygon([
                (x_ratio-.012, .585), (x_ratio+.012, .585),
                (x_ratio+.012, .62), (x_ratio-.012, .62),
            ], armor, stroke="#5D5D70", stroke_width=1)
        seam(-.085, .65, .085, .65, detail, 1)

        positions = {
            "head": height * 0.205,
            "chest": height * 0.45,
            "belly": height * 0.605,
        }
        focus = self._auxilio_ai_settings["aim_point"]
        focus_y = positions[focus]
        callout_x = width * .66
        focus_color = AUX_AI_FOCUS_COLORS.get(focus, self._aux_ai_colors["cyan"])
        canvas.create_line(
            center_x, focus_y, callout_x-8, focus_y,
            fill=focus_color, width=2,
        )
        canvas.create_text(
            callout_x, focus_y-9, text="FOCO ATUAL", anchor="w",
            fill=self._aux_ai_colors["muted"], font=("Segoe UI", 8, "bold"),
        )
        canvas.create_text(
            callout_x, focus_y+9, text=self._aux_ai_aim_label(focus).upper(),
            anchor="w", fill=focus_color, font=("Segoe UI", 10, "bold"),
        )

    def _draw_aux_ai_image_preview(self, canvas, width, height):
        model_name = Path(self._auxilio_ai_settings["model_path"]).stem
        preview = AUX_AI_TARGET_PREVIEWS.get(model_name)
        if preview is None:
            return False

        image_path = self._aux_ai_target_images_dir / preview["image"]
        try:
            with Image.open(image_path) as source_image:
                image = source_image.convert("RGBA")
            original_width, original_height = image.size
            alpha_bounds = image.getchannel("A").getbbox() or (
                0, 0, original_width, original_height,
            )
            image = image.crop(alpha_bounds)
            crop_left, crop_top, crop_right, crop_bottom = alpha_bounds
            crop_width = crop_right - crop_left
            crop_height = crop_bottom - crop_top
            source_width, source_height = image.size
            max_width = max(1, int(width * 0.78))
            max_height = max(1, int(height * 1.48))
            scale = min(max_width / source_width, max_height / source_height)
            image = image.resize(
                (
                    max(1, round(source_width * scale)),
                    max(1, round(source_height * scale)),
                ),
                Image.Resampling.LANCZOS,
            )
            photo = ImageTk.PhotoImage(image, master=canvas)
        except OSError:
            logger.exception("Could not load Auxilio-AI target preview: %s", image_path)
            canvas.create_text(
                width * 0.5, height * 0.5,
                text="Nao foi possivel carregar a imagem do perfil",
                fill=self._aux_ai_colors["muted"],
                font=("Segoe UI", 9),
            )
            return True

        image_x = width * 0.34 - image.width / 2
        image_y = 0
        canvas.create_image(image_x, image_y, image=photo, anchor="nw")
        self._aux_ai_preview_photo = photo

        positions = {
            point: (
                image_x + image.width * (
                    coordinates[0] * original_width - crop_left
                ) / crop_width,
                image_y + image.height * (
                    coordinates[1] * original_height - crop_top
                ) / crop_height,
            )
            for point, coordinates in preview["focus"].items()
        }
        focus = self._auxilio_ai_settings["aim_point"]
        focus_x, focus_y = positions[focus]
        callout_x = width * 0.66
        focus_color = AUX_AI_FOCUS_COLORS.get(focus, self._aux_ai_colors["cyan"])
        canvas.create_line(
            focus_x, focus_y, callout_x-8, focus_y,
            fill=focus_color, width=2,
        )
        canvas.create_text(
            callout_x, focus_y-9, text="FOCO ATUAL", anchor="w",
            fill=self._aux_ai_colors["muted"], font=("Segoe UI", 8, "bold"),
        )
        canvas.create_text(
            callout_x, focus_y+9, text=self._aux_ai_aim_label(focus).upper(),
            anchor="w", fill=focus_color, font=("Segoe UI", 10, "bold"),
        )
        return True

    def _aux_ai_values(self):
        aim_key = self._auxilio_ai_settings["aim_key"]
        menu_key = self._auxilio_ai_settings["menu_key"]
        if aim_key == menu_key:
            raise ValueError("A tecla do menu deve ser diferente da tecla de ativacao.")
        if self._aux_ai_vkey(menu_key) == self.cfg.vk_toggle:
            raise ValueError("O atalho do menu Aux-AI nao pode ser o atalho ARM ENGINE.")
        values = {
            **self._auxilio_ai_settings,
            "fov": max(160, min(640, int(self._auxilio_ai_settings["fov"]))),
            "smoothing": max(0.05, min(1.0, float(self._auxilio_ai_settings["smoothing"]))),
            "humanizer_speed": max(
                200,
                min(4000, int(self._auxilio_ai_settings.get("humanizer_speed", 2000))),
            ),
        }
        for key, variable in self._aux_ai_view_vars.items():
            value = variable.get()
            if key.endswith("_color"):
                if not re.fullmatch(r"#[0-9A-Fa-f]{6}", str(value).strip()):
                    raise ValueError(f"Cor invalida em {key}; use #RRGGBB.")
                values[key] = str(value).strip().upper()
            elif isinstance(variable, tk.BooleanVar):
                values[key] = bool(value)
            elif isinstance(variable, tk.StringVar):
                values[key] = str(value).strip()
            elif key in ("esp_thickness", "esp_opacity", "snap_line_thickness", "overlay_opacity", "max_detections"):
                values[key] = int(round(float(value)))
            else:
                values[key] = float(value)
        values["min_confidence"] = max(0.0, min(1.0, values["min_confidence"]))
        values["iou_threshold"] = max(0.0, min(1.0, values["iou_threshold"]))
        values["esp_thickness"] = max(1, min(8, values["esp_thickness"]))
        values["snap_line_thickness"] = max(1, min(8, values["snap_line_thickness"]))
        values["esp_opacity"] = max(0, min(100, values["esp_opacity"]))
        values["overlay_opacity"] = max(10, min(100, values["overlay_opacity"]))
        values["max_detections"] = max(1, min(100, values["max_detections"]))
        values["min_distance"] = max(0.0, min(1.0, values["min_distance"]))
        values["max_distance"] = max(values["min_distance"], min(1.0, values["max_distance"]))
        values["min_box_area"] = max(0.0, min(0.25, values["min_box_area"]))
        values["max_box_area"] = max(values["min_box_area"], min(1.0, values["max_box_area"]))
        if self._aux_ai_model_classes and len(self._aux_ai_model_classes) == 1:
            values["target_classes"] = self._aux_ai_model_classes[0]
        return values

    def _update_aux_ai_profile_preview(self):
        if hasattr(self, "_aux_ai_message"):
            self._aux_ai_message.configure(text="Configuracao alterada · clique em Aplicar")

    def _apply_aux_ai_settings(self):
        try:
            values = self._aux_ai_values()
            profiles_dir = self._auxilio_ai_data_dir / "profiles"
            profiles_dir.mkdir(parents=True, exist_ok=True)
            (profiles_dir / "active.json").write_text(
                json.dumps(values, indent=2), encoding="utf-8",
            )
        except (OSError, ValueError) as exc:
            logger.exception("Could not apply Auxilio-AI settings.")
            messagebox.showerror("Erro ao aplicar configuracao", str(exc), parent=self)
            return

        process = self._auxilio_ai_process
        if (
            process is not None
            and process.poll() is None
            and self._auxilio_ai_started_model_path is not None
            and Path(values["model_path"]).name
            != self._auxilio_ai_started_model_path.name
        ):
            self._auxilio_ai_restart_after_stop = True
            self._aux_ai_message.configure(
                text="Perfil ONNX alterado; reiniciando o motor para carregar o novo modelo..."
            )
            self._stop_auxilio_ai()
            return

        self._aux_ai_message.configure(text="Configuracoes aplicadas e salvas")
        if self._auxilio_ai_process is not None and self._auxilio_ai_process.poll() is None:
            if self._send_aux_ai_command({"type": "settings", "settings": values}):
                self._aux_ai_message.configure(text="Configuracoes atualizadas sem reiniciar")

    def _save_aux_ai_profile(self):
        name = simpledialog.askstring("Salvar perfil", "Nome do perfil:", parent=self)
        if name is None:
            return
        profile_name = re.sub(r"[^A-Za-z0-9_-]+", "_", name).strip("_")
        if not profile_name:
            self._aux_ai_message.configure(text="Informe um nome de perfil valido")
            return
        try:
            values = self._aux_ai_values()
            profiles_dir = self._auxilio_ai_data_dir / "profiles"
            profiles_dir.mkdir(parents=True, exist_ok=True)
            (profiles_dir / f"{profile_name}.json").write_text(
                json.dumps(values, indent=2), encoding="utf-8",
            )
            (profiles_dir / "active.json").write_text(
                json.dumps(values, indent=2), encoding="utf-8",
            )
        except (OSError, ValueError) as exc:
            logger.exception("Could not save Auxilio-AI profile.")
            messagebox.showerror("Erro ao salvar perfil", str(exc), parent=self)
            return
        self._apply_aux_ai_settings()
        self._aux_ai_message.configure(text=f"Perfil salvo: {profile_name}")

    def _begin_aux_ai_key_capture(self, target):
        self._auxilio_ai_capture_target = target
        button = self._aux_ai_activation_button if target == "aim_key" else self._aux_ai_menu_button
        button.configure(text="Pressione uma tecla")
        self.focus_force()

    def _on_aux_ai_key_press(self, event):
        target = self._auxilio_ai_capture_target
        if target is None:
            return
        if event.keysym == "Escape":
            self._auxilio_ai_capture_target = None
            self._restore_aux_ai_key_labels()
            return "break"
        vk = int(event.keycode or 0)
        label = self._aux_ai_key_label(vk)
        if label is None:
            self._aux_ai_message.configure(text="Tecla nao suportada")
            return "break"
        self._assign_aux_ai_key(target, label)
        return "break"

    @staticmethod
    def _aux_ai_key_label(vk):
        if 0x30 <= vk <= 0x39 or 0x41 <= vk <= 0x5A:
            return chr(vk)
        if 0x70 <= vk <= 0x7B:
            return f"F{vk - 0x6F}"
        return {
            0x09: "Tab", 0x0D: "Enter", 0x10: "Shift",
            0x11: "Ctrl", 0x12: "Alt", 0x14: "Caps Lock",
            0x20: "Space", 0x21: "Page Up", 0x22: "Page Down",
            0x23: "End", 0x24: "Home", 0x2D: "Insert",
            0x2E: "Delete",
        }.get(vk)

    @staticmethod
    def _aux_ai_vkey(label):
        if len(label) == 1 and label.isalnum():
            return ord(label.upper())
        if label.startswith("F") and label[1:].isdigit():
            number = int(label[1:])
            return 0x70 + number - 1 if 1 <= number <= 12 else None
        return {
            "Tab": 0x09, "Enter": 0x0D, "Shift": 0x10,
            "Ctrl": 0x11, "Alt": 0x12, "Caps Lock": 0x14,
            "Space": 0x20, "Page Up": 0x21, "Page Down": 0x22,
            "End": 0x23, "Home": 0x24, "Insert": 0x2D,
            "Delete": 0x2E,
        }.get(label)

    def _assign_aux_ai_key(self, target, label):
        self._auxilio_ai_capture_target = None
        if target == "menu_key" and label == self._auxilio_ai_settings["aim_key"]:
            self._aux_ai_message.configure(text="A tecla do menu deve ser diferente da ativacao")
            self._restore_aux_ai_key_labels()
            return
        if target == "aim_key" and label == self._auxilio_ai_settings["menu_key"]:
            self._aux_ai_message.configure(text="A tecla de ativacao deve ser diferente do menu")
            self._restore_aux_ai_key_labels()
            return
        self._auxilio_ai_settings[target] = label
        self._restore_aux_ai_key_labels()
        if target == "aim_key":
            self._aux_ai_mouse_option.set("Selecione...")
        self._update_aux_ai_profile_preview()

    def _restore_aux_ai_key_labels(self):
        self._aux_ai_activation_button.configure(text=self._auxilio_ai_settings["aim_key"])
        self._aux_ai_menu_button.configure(text=self._auxilio_ai_settings["menu_key"])

    @staticmethod
    def _auxilio_ai_runtime_ready(interpreter: Path) -> bool:
        try:
            result = subprocess.run(
                [
                    str(interpreter), "-c",
                    "import bettercam, cv2, numpy, onnxruntime, win32api",
                ],
                cwd=interpreter.parent,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=20,
                check=False,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except (OSError, subprocess.TimeoutExpired):
            logger.exception("Could not validate Auxilio-AI runtime dependencies.")
            return False
        return result.returncode == 0

    def _start_auxilio_ai(self):
        if sys.platform != "win32":
            messagebox.showerror(
                "Auxilio-AI não suportado",
                "A aplicação de referência utiliza APIs nativas do Windows.",
                parent=self,
            )
            return

        if self._auxilio_ai_process is not None:
            if self._auxilio_ai_process.poll() is None:
                return
            self._auxilio_ai_process = None

        try:
            values = self._aux_ai_values()
            profiles_dir = self._auxilio_ai_data_dir / "profiles"
            profiles_dir.mkdir(parents=True, exist_ok=True)
            (profiles_dir / "active.json").write_text(
                json.dumps(values, indent=2), encoding="utf-8",
            )
        except (OSError, ValueError) as exc:
            logger.exception("Could not save Auxilio-AI settings before startup.")
            messagebox.showerror("Configuracao invalida", str(exc), parent=self)
            return

        interpreter = self._auxilio_ai_env_dir / "Scripts" / "python.exe"
        entrypoint = self._auxilio_ai_dir / "main.py"
        model = Path(self._auxilio_ai_settings["model_path"])
        if not model.is_absolute():
            model = self._auxilio_ai_dir / model
        model = model.resolve()
        if not entrypoint.is_file() or not model.is_file():
            messagebox.showerror(
                "Auxilio-AI incompleto",
                f"Não encontrei os arquivos do motor em:\n{self._auxilio_ai_dir}",
                parent=self,
            )
            return
        if not interpreter.is_file() or not self._auxilio_ai_runtime_ready(interpreter):
            self._confirm_auxilio_ai_setup()
            return

        log_path = self._auxilio_ai_data_dir / "biosync-runtime.log"
        try:
            self._auxilio_ai_data_dir.mkdir(parents=True, exist_ok=True)
            self._auxilio_ai_log_offset = log_path.stat().st_size if log_path.exists() else 0
            with log_path.open("a", encoding="utf-8") as log_file:
                self._auxilio_ai_process = subprocess.Popen(
                    [str(interpreter), "-u", str(entrypoint), "--embedded"],
                    cwd=self._auxilio_ai_data_dir,
                    stdout=log_file,
                    stderr=subprocess.STDOUT,
                    stdin=subprocess.PIPE,
                    text=True,
                    bufsize=1,
                    env=auxilio_ai_child_environment(
                        self._auxilio_ai_data_dir,
                        self._auxilio_ai_dir,
                    ),
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
            self._auxilio_ai_started_model_path = model
            self._auxilio_ai_started_at = time.time()
        except OSError as exc:
            self._auxilio_ai_process = None
            logger.exception("Failed to start Auxilio-AI.")
            messagebox.showerror("Não foi possível iniciar Auxilio-AI", str(exc), parent=self)
            return

        self._auxilio_ai_status.configure(
            text="● INICIANDO", text_color=self._aux_ai_colors["accent"],
        )
        self._auxilio_ai_stopping = False
        self._aux_ai_start_button.configure(state="disabled")
        self._aux_ai_stop_button.configure(state="normal")
        self._auxilio_ai_status.configure(
            text="● CARREGANDO ONNX", text_color=self._aux_ai_colors["accent"],
        )
        self._aux_ai_message.configure(
            text="Inicializando captura e carregando o modelo ONNX..."
        )
        self._poll_auxilio_ai()

    def _confirm_auxilio_ai_setup(self):
        if self._auxilio_ai_setup_process is not None:
            if self._auxilio_ai_setup_process.poll() is None:
                return
            self._auxilio_ai_setup_process = None

        if not messagebox.askyesno(
            "Preparar Auxilio-AI",
            "O ambiente Python 3.11 ou alguma dependência necessária do ONNX está ausente.\n\n"
            "Deseja criar o ambiente Python 3.11 e instalar as dependências agora? "
            "O download pode levar alguns minutos.",
            parent=self,
        ):
            return

        if not self._auxilio_ai_env_dir.joinpath("Scripts", "python.exe").is_file():
            try:
                python_available = subprocess.run(
                    ["py", "-3.11", "--version"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=10,
                    check=False,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                ).returncode == 0
            except (OSError, subprocess.TimeoutExpired):
                python_available = False
            if not python_available:
                if messagebox.askyesno(
                    "Python 3.11 necessário",
                    "O Python Launcher não encontrou Python 3.11, necessário para "
                    "o runtime ONNX desta versão.\n\nDeseja abrir a página oficial "
                    "para baixar Python 3.11?",
                    parent=self,
                ):
                    webbrowser.open("https://www.python.org/downloads/release/python-3119/")
                return

        setup_log = self._auxilio_ai_data_dir / "setup.log"
        interpreter = self._auxilio_ai_env_dir / "Scripts" / "python.exe"
        create_environment = not interpreter.is_file()
        try:
            self._auxilio_ai_data_dir.mkdir(parents=True, exist_ok=True)
            with setup_log.open("w", encoding="utf-8") as log_file:
                self._auxilio_ai_setup_process = subprocess.Popen(
                    (
                        ["py", "-3.11", "-m", "venv", str(self._auxilio_ai_env_dir)]
                        if create_environment
                        else [
                            str(interpreter), "-m", "pip", "install",
                            "-r", str(self._auxilio_ai_dir / "requirements.txt"),
                        ]
                    ),
                    cwd=self._auxilio_ai_data_dir,
                    stdout=log_file,
                    stderr=subprocess.STDOUT,
                    stdin=subprocess.DEVNULL,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
        except OSError as exc:
            self._auxilio_ai_setup_process = None
            logger.exception("Failed to start Auxilio-AI setup.")
            messagebox.showerror("Não foi possível preparar Auxilio-AI", str(exc), parent=self)
            return

        self._auxilio_ai_setup_stage = "venv" if create_environment else "dependencies"
        self._aux_ai_start_button.configure(state="disabled")
        self._aux_ai_stop_button.configure(state="disabled")
        self._auxilio_ai_status.configure(
            text="● PREPARANDO", text_color=self._aux_ai_colors["accent"],
        )
        self._aux_ai_message.configure(
            text=(
                "Criando ambiente isolado Python 3.11..."
                if create_environment
                else "Baixando ONNX Runtime, OpenCV e dependencias..."
            )
        )
        self._poll_auxilio_ai_setup()

    def _poll_auxilio_ai_setup(self):
        process = self._auxilio_ai_setup_process
        if process is None:
            return
        return_code = process.poll()
        if return_code is None:
            setup_log = self._auxilio_ai_data_dir / "setup.log"
            stage = self._auxilio_ai_setup_stage
            if stage == "venv":
                status = "Preparando ambiente isolado Python 3.11..."
            else:
                status = "Instalando runtime ONNX e dependencias..."
            try:
                lines = setup_log.read_text(encoding="utf-8", errors="replace").splitlines()
                if lines:
                    status = f"{status} {lines[-1][-80:]}"
            except OSError:
                pass
            self._aux_ai_message.configure(text=status)
            self._auxilio_ai_setup_poll_id = self.after(1000, self._poll_auxilio_ai_setup)
            return

        self._auxilio_ai_setup_process = None
        self._auxilio_ai_setup_poll_id = None
        interpreter = self._auxilio_ai_env_dir / "Scripts" / "python.exe"
        if return_code != 0:
            self._fail_auxilio_ai_setup(return_code)
            return

        if self._auxilio_ai_setup_stage == "venv":
            if not interpreter.is_file():
                self._fail_auxilio_ai_setup(return_code, missing_interpreter=True)
                return
            try:
                with (self._auxilio_ai_data_dir / "setup.log").open("a", encoding="utf-8") as log_file:
                    self._auxilio_ai_setup_process = subprocess.Popen(
                        [
                            str(interpreter), "-m", "pip", "install",
                            "-r", str(self._auxilio_ai_dir / "requirements.txt"),
                        ],
                        cwd=self._auxilio_ai_data_dir,
                        stdout=log_file,
                        stderr=subprocess.STDOUT,
                        stdin=subprocess.DEVNULL,
                        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                    )
            except OSError as exc:
                logger.exception("Failed to start Auxilio-AI dependency installation.")
                self._fail_auxilio_ai_setup(-1, detail=str(exc))
                return
            self._auxilio_ai_setup_stage = "dependencies"
            self._aux_ai_message.configure(
                text="Ambiente criado; baixando ONNX Runtime, OpenCV e dependencias..."
            )
            self._auxilio_ai_setup_poll_id = self.after(1000, self._poll_auxilio_ai_setup)
            return

        self._auxilio_ai_setup_stage = None
        if not interpreter.is_file():
            self._fail_auxilio_ai_setup(return_code, missing_interpreter=True)
            return

        self._auxilio_ai_status.configure(text="● PREPARADO", text_color=self._aux_ai_colors["success"])
        self._aux_ai_message.configure(text="Dependencias prontas; iniciando Auxilio-AI...")
        self.after(150, self._start_auxilio_ai)

    def _fail_auxilio_ai_setup(self, return_code, missing_interpreter=False, detail=None):
        self._auxilio_ai_setup_process = None
        self._auxilio_ai_setup_poll_id = None
        self._auxilio_ai_setup_stage = None
        setup_log = self._auxilio_ai_data_dir / "setup.log"
        interpreter = self._auxilio_ai_env_dir / "Scripts" / "python.exe"
        if return_code != 0 or missing_interpreter:
            self._auxilio_ai_status.configure(text="● ERRO NA PREPARACAO", text_color=T.RED_ALERT)
            self._aux_ai_start_button.configure(state="normal")
            self._aux_ai_message.configure(text="Falha ao instalar; consulte setup.log")
            logger.error(
                "Auxilio-AI setup failed (exit=%s, interpreter_exists=%s, detail=%s); see %s",
                return_code, interpreter.is_file(), detail, setup_log,
            )
            messagebox.showerror(
                "Falha ao preparar Auxilio-AI",
                f"A instalacao nao foi concluida.\n{detail or ''}\n"
                "Consulte o log:\n"
                f"{setup_log}\n\n"
                "Verifique se o Python Launcher/Python 3.11 estao instalados e se "
                "ha conexao com a internet.",
                parent=self,
            )

    def _poll_auxilio_ai(self):
        process = self._auxilio_ai_process
        if process is None:
            return
        return_code = process.poll()
        if return_code is None:
            metadata_path = self._auxilio_ai_data_dir / "profiles" / "model_metadata.json"
            model_ready = False
            if self._auxilio_ai_started_at is not None:
                try:
                    model_ready = metadata_path.stat().st_mtime >= self._auxilio_ai_started_at
                except OSError:
                    pass

            if self._aux_ai_pages.get("Views") is not None and self._aux_ai_pages["Views"].winfo_viewable():
                self._refresh_aux_ai_model_classes()
            if not self._auxilio_ai_stopping:
                self._auxilio_ai_status.configure(
                    text="● ATIVO" if model_ready else "● CARREGANDO ONNX",
                    text_color=(
                        self._aux_ai_colors["success"]
                        if model_ready else self._aux_ai_colors["accent"]
                    ),
                )
            if not model_ready:
                self._aux_ai_message.configure(
                    text=self._auxilio_ai_latest_startup_log_line()
                    or "Inicializando captura e carregando o modelo ONNX..."
                )
            elif not self._auxilio_ai_model_ready:
                self._auxilio_ai_model_ready = True
                self._aux_ai_message.configure(
                    text="Modelo ONNX carregado; runtime pronto."
                )
            self._auxilio_ai_poll_id = self.after(750, self._poll_auxilio_ai)
            return

        self._auxilio_ai_process = None
        self._auxilio_ai_poll_id = None
        self._auxilio_ai_started_at = None
        self._auxilio_ai_started_model_path = None
        self._auxilio_ai_model_ready = False
        self._auxilio_ai_stopping = False
        self._auxilio_ai_status.configure(text="● PARADO", text_color=T.TEXT_DIM)
        self._aux_ai_start_button.configure(state="normal")
        self._aux_ai_stop_button.configure(state="disabled")
        restart = self._auxilio_ai_restart_after_stop
        self._auxilio_ai_restart_after_stop = False
        if restart:
            self._aux_ai_message.configure(text="Reiniciando com as novas configuracoes...")
            self.after(150, self._start_auxilio_ai)
            return
        if return_code != 0:
            log_path = self._auxilio_ai_data_dir / "biosync-runtime.log"
            logger.error("Auxilio-AI exited with code %s; see %s", return_code, log_path)
            messagebox.showerror(
                "Auxilio-AI encerrou com erro",
                f"Código de saída: {return_code}\nConsulte o log:\n{log_path}",
                parent=self,
            )

    def _auxilio_ai_latest_startup_log_line(self):
        log_path = self._auxilio_ai_data_dir / "biosync-runtime.log"
        try:
            new_output = log_path.read_bytes()[self._auxilio_ai_log_offset:]
        except OSError:
            return ""
        lines = new_output.decode("utf-8", errors="replace").splitlines()
        return next((line.strip()[-180:] for line in reversed(lines) if line.strip()), "")

    def _stop_auxilio_ai(self):
        process = self._auxilio_ai_process
        if process is None or process.poll() is not None:
            self._poll_auxilio_ai()
            return
        if process.stdin is None:
            self._aux_ai_message.configure(text="Canal de controle do Auxilio-AI indisponivel")
            return
        try:
            process.stdin.write("STOP\n")
            process.stdin.flush()
        except OSError as exc:
            logger.exception("Could not request Auxilio-AI shutdown.")
            self._aux_ai_message.configure(text=f"Erro ao encerrar: {exc}")
            return
        self._auxilio_ai_status.configure(
            text="● ENCERRANDO", text_color=self._aux_ai_colors["accent"],
        )
        self._auxilio_ai_stopping = True
        self._aux_ai_stop_button.configure(state="disabled")

    def _build_user(self):
        f = self.tabs["user"]
        f.grid_columnconfigure(0, weight=1)
        f.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(
            f, text="USER",
            font=T.FONT_TITLE, text_color=T.TEXT_PRIMARY,
        ).grid(row=0, column=0, padx=32, pady=(18, 10), sticky="w")

        card = ctk.CTkFrame(f, fg_color=T.BG_CARD, corner_radius=12)
        card.grid(row=1, column=0, padx=32, pady=(0, 24), sticky="nsew")
        card.grid_columnconfigure(0, weight=1)
        card.grid_rowconfigure(0, weight=1)

        account = ctk.CTkFrame(card, fg_color="transparent")
        account.place(relx=0.5, rely=0.45, anchor="center")
        ctk.CTkLabel(
            account, text="PERFIL DE USUÁRIO",
            font=T.FONT_SECTION, text_color=T.CYAN_HUD,
        ).pack(pady=(0, 10))
        ctk.CTkLabel(
            account, text="Autenticação ainda não conectada",
            font=T.FONT_TITLE, text_color=T.TEXT_PRIMARY,
        ).pack()
        ctk.CTkLabel(
            account,
            text="Este painel ficará preparado para a futura integração pwfauth.",
            font=T.FONT_BODY, text_color=T.TEXT_MUTED,
        ).pack(pady=(8, 16))
        ctk.CTkButton(
            account, text="INTEGRAÇÃO FUTURA",
            width=210, height=36, state="disabled",
            font=T.FONT_HUD, fg_color=T.BG_PANEL,
            text_color=T.TEXT_DIM,
        ).pack()

    # ── HOME ──────────────────────────────────────────────────
    def _build_home(self):
        f = self.tabs["home"]
        f.grid_rowconfigure(3, weight=1)

        title = ctk.CTkLabel(
            f, text="OPERATOR DASHBOARD",
            font=T.FONT_TITLE, text_color=T.TEXT_PRIMARY
        )
        title.grid(row=0, column=0, padx=32, pady=(12, 2), sticky="w")

        hint = ctk.CTkLabel(
            f, text="Insert  ·  toggle engine     |     pipeline portado do BioSync C# v6.2",
            font=T.FONT_SMALL, text_color=T.TEXT_DIM
        )
        hint.grid(row=1, column=0, padx=32, pady=(0, 8), sticky="w")

        # Cards row
        cards = ctk.CTkFrame(f, fg_color="transparent")
        cards.grid(row=2, column=0, padx=32, sticky="ew")
        cards.grid_columnconfigure((0, 1, 2), weight=1)

        self._stat_engine = self._make_stat_card(cards, "ENGINE", "STANDBY", T.TEXT_DIM)
        self._stat_engine.grid(row=0, column=0, padx=(0, 10), sticky="ew")

        self._stat_sens = self._make_stat_card(
            cards, "SENS X / Y",
            f"{self.cfg.sens_x:.0f}  /  {self.cfg.sens_y:.0f}", T.CYAN_HUD
        )
        self._stat_sens.grid(row=0, column=1, padx=5, sticky="ew")

        self._stat_pad = self._make_stat_card(cards, "VIRTUAL PAD", "VX360", T.AMBER)
        self._stat_pad.grid(row=0, column=2, padx=(10, 0), sticky="ew")

        # Info block
        info = ctk.CTkFrame(f, fg_color=T.BG_CARD, corner_radius=10)
        info.grid(row=3, column=0, padx=32, pady=12, sticky="nsew")

        lines = [
            "PIPELINE  ·  Raw Δ → Gain × Filter × Sens × Curve → Accel power-law",
            "            → Friction · Smoothing · Inverse Deadzone · Clamp ±32767",
            "FEATURES  ·  Buffed Aim orbital · No-Recoil VOYAK KT-3 · WASD→LS · Triggers LMB/RMB",
            "LATENCY   ·  Soft 1 kHz loop (Python) — migrar hot-path p/ Cython/C++ depois",
            "REQUIRE   ·  Windows: ViGEmBus instalado  |  Linux: uinput (teste apenas)",
        ]
        for i, line in enumerate(lines):
            ctk.CTkLabel(
                info, text=line, font=T.FONT_MONO,
                text_color=T.TEXT_MUTED, anchor="w"
            ).pack(anchor="w", padx=20, pady=(8 if i == 0 else 2, 2 if i < len(lines) - 1 else 8))

    def _make_stat_card(self, parent, title: str, value: str, accent: str) -> ctk.CTkFrame:
        card = ctk.CTkFrame(parent, fg_color=T.BG_CARD, corner_radius=10, height=90)
        card.grid_propagate(False)
        ctk.CTkLabel(card, text=title, font=T.FONT_SMALL, text_color=T.TEXT_DIM).pack(
            anchor="w", padx=16, pady=(14, 0)
        )
        lbl = ctk.CTkLabel(card, text=value, font=("Segoe UI", 16, "bold"), text_color=accent)
        lbl.pack(anchor="w", padx=16, pady=(4, 14))
        card._value_lbl = lbl  # type: ignore
        return card

    # ── SENSITIVITY ───────────────────────────────────────────
    def _build_sens(self):
        f = self.tabs["sens"]
        f.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            f, text="SENSIBILIDADE DO ANALÓGICO",
            font=T.FONT_TITLE, text_color=T.TEXT_PRIMARY
        ).grid(row=0, column=0, padx=32, pady=(18, 10), sticky="w")

        content = ctk.CTkFrame(f, fg_color="transparent")
        content.grid(row=1, column=0, sticky="nsew", padx=24, pady=(0, 10))
        content.grid_columnconfigure((0, 1), weight=1)
        f.grid_rowconfigure(1, weight=1)

        self._sliders: dict[str, ctk.CTkSlider] = {}
        self._slider_lbls: dict[str, ctk.CTkLabel] = {}

        self._build_slider_card(
            content, "EIXO X · CALIBRAGEM HORIZONTAL", T.CYAN_HUD, 0, 0, 1,
            [
                ("sens_x", "Sensibilidade Base", 100, 30000, self.cfg.sens_x, ".0f"),
                ("filter_x", "Multiplicador Filtro", 0.1, 20.0, self.cfg.filter_x, ".2f"),
                ("curve_x", "Curva de Resposta", 0.05, 2.0, self.cfg.curve_x, ".2f"),
            ],
        )
        self._build_slider_card(
            content, "EIXO Y · CALIBRAGEM VERTICAL", T.GREEN_TACT, 0, 1, 1,
            [
                ("sens_y", "Sensibilidade Base", 100, 30000, self.cfg.sens_y, ".0f"),
                ("filter_y", "Multiplicador Filtro", 0.1, 20.0, self.cfg.filter_y, ".2f"),
                ("curve_y", "Curva de Resposta", 0.05, 2.0, self.cfg.curve_y, ".2f"),
            ],
        )
        self._build_slider_card(
            content, "DINÂMICA DE ACELERAÇÃO E SUAVIZAÇÃO", T.ORANGE, 1, 0, 2,
            [
                ("acceleration", "Acelerador Dinâmico (S-Curve)", 0.05, 2.0,
                 self.cfg.acceleration, ".2f"),
                ("hardware_gain", "Ganho Bruto do Sensor", 1.0, 100.0,
                 self.cfg.hardware_gain, ".1f"),
                ("friction", "Suavização / Fricção", 0.01, 0.95,
                 self.cfg.friction, ".3f"),
                ("inverse_deadzone", "Compensação de Deadzone", 0, 8000,
                 self.cfg.inverse_deadzone, ".0f"),
            ],
        )

        profile_card = ctk.CTkFrame(content, fg_color=T.BG_CARD, corner_radius=10)
        profile_card.grid(row=2, column=0, columnspan=2, sticky="ew", padx=4, pady=4)
        ctk.CTkLabel(
            profile_card, text="PERFIS DE CONFIGURAÇÃO",
            font=T.FONT_SECTION, text_color=T.CYAN_HUD,
        ).grid(row=0, column=0, padx=14, pady=(8, 4), sticky="w")
        profile_controls = ctk.CTkFrame(profile_card, fg_color="transparent")
        profile_controls.grid(row=1, column=0, padx=12, pady=(0, 8), sticky="ew")
        profile_controls.grid_columnconfigure(0, weight=1)
        self.sens_profile_choice = ctk.CTkOptionMenu(
            profile_controls,
            values=sorted(self._profiles) or ["Sem perfis"],
            height=30,
            font=T.FONT_BODY,
            fg_color=T.BG_PANEL,
            button_color=T.BG_CARD_HOVER,
            button_hover_color=T.BORDER,
            text_color=T.TEXT_PRIMARY,
        )
        self.sens_profile_choice.grid(row=0, column=0, sticky="ew")
        self.btn_load_sens_profile = ctk.CTkButton(
            profile_controls, text="CARREGAR PERFIL", width=140, height=30,
            font=("Segoe UI", 10, "bold"),
            fg_color=T.BG_PANEL, hover_color=T.BG_CARD_HOVER,
            text_color=T.TEXT_PRIMARY, command=self._load_selected_profile,
        )
        self.btn_load_sens_profile.grid(row=0, column=1, padx=(8, 0))
        self.btn_save_sens_profile = ctk.CTkButton(
            profile_controls, text="SALVAR PERFIL", width=130, height=30,
            font=("Segoe UI", 10, "bold"),
            fg_color=T.GOLD, hover_color=T.GOLD_DIM,
            text_color=T.BG_DEEP, command=self._save_profile,
        )
        self.btn_save_sens_profile.grid(row=0, column=2, padx=(8, 0))
        if not self._profiles:
            self.btn_load_sens_profile.configure(state="disabled")

        # Save button
        ctk.CTkButton(
            f, text="SAVE CONFIG", font=T.FONT_HUD, height=36,
            fg_color=T.BG_CARD, hover_color=T.BG_CARD_HOVER,
            border_width=1, border_color=T.ORANGE, text_color=T.ORANGE,
            command=self._save_cfg
        ).grid(row=2, column=0, padx=32, pady=(0, 12), sticky="e")

    def _build_slider_card(self, parent, title, accent, row, column, columnspan, specs):
        card = ctk.CTkFrame(parent, fg_color=T.BG_CARD, corner_radius=10)
        card.grid(
            row=row, column=column, columnspan=columnspan,
            sticky="nsew", padx=4, pady=4,
        )
        ctk.CTkLabel(
            card, text=title, font=T.FONT_SECTION, text_color=accent
        ).pack(anchor="w", padx=14, pady=(9, 4))

        for key, label, minimum, maximum, value, number_format in specs:
            row = ctk.CTkFrame(card, fg_color="transparent")
            row.pack(fill="x", padx=14, pady=(0, 2))
            value_label = ctk.CTkLabel(
                row,
                text=f"{label}: {value:{number_format}}",
                font=T.FONT_BODY,
                text_color=T.TEXT_PRIMARY,
                anchor="w",
            )
            value_label.pack(fill="x")
            self._slider_lbls[key] = value_label

            slider = ctk.CTkSlider(
                row, from_=minimum, to=maximum,
                number_of_steps=990 if key == "hardware_gain" else 500,
                progress_color=accent, button_color=accent,
                button_hover_color=T.AMBER, fg_color=T.BORDER,
                command=lambda new_value, k=key: self._on_slider(k, new_value),
            )
            slider.set(value)
            slider.pack(fill="x", pady=(0, 2))
            self._sliders[key] = slider

    def _on_slider(self, key: str, value: float):
        if key == "inverse_deadzone":
            value = int(round(value))
        setattr(self.cfg, key, value)
        if key in self._slider_lbls:
            labels = {
                "sens_x": "Sensibilidade Base",
                "sens_y": "Sensibilidade Base",
                "filter_x": "Multiplicador Filtro",
                "filter_y": "Multiplicador Filtro",
                "curve_x": "Curva de Resposta",
                "curve_y": "Curva de Resposta",
                "acceleration": "Acelerador Dinâmico (S-Curve)",
                "hardware_gain": "Ganho Bruto do Sensor",
                "friction": "Suavização / Fricção",
                "inverse_deadzone": "Compensação de Deadzone",
            }
            number_format = (
                ".0f" if key in ("sens_x", "sens_y", "inverse_deadzone")
                else ".1f" if key == "hardware_gain"
                else ".3f" if key == "friction"
                else ".2f"
            )
            self._slider_lbls[key].configure(
                text=f"{labels[key]}: {value:{number_format}}"
            )
        self.engine.update_config(self.cfg)
        self._refresh_home_stats()
        self._schedule_config_save()

    def _save_cfg(self):
        if self._save_after_id is not None:
            self.after_cancel(self._save_after_id)
            self._save_after_id = None
        try:
            self.cfg.save()
        except OSError as exc:
            messagebox.showerror("Erro ao salvar configuração", str(exc), parent=self)

    def _schedule_config_save(self):
        if self._save_after_id is not None:
            self.after_cancel(self._save_after_id)
        self._save_after_id = self.after(300, self._save_cfg)

    def _refresh_profile_choices(self, selected: Optional[str] = None):
        names = sorted(self._profiles)
        self.sens_profile_choice.configure(values=names or ["Sem perfis"])
        self.sens_profile_choice.set(
            selected if selected in self._profiles else (names[0] if names else "Sem perfis")
        )
        self.btn_load_sens_profile.configure(state="normal" if names else "disabled")

    def _save_profile(self):
        dialog = ctk.CTkInputDialog(
            text="Digite um nome para o perfil:",
            title="Salvar perfil",
        )
        name = dialog.get_input()
        if name is None:
            return
        name = name.strip()
        if not name:
            messagebox.showerror("Nome inválido", "Informe um nome para o perfil.", parent=self)
            return
        if len(name) > 32:
            messagebox.showerror("Nome inválido", "O nome do perfil deve ter até 32 caracteres.", parent=self)
            return
        try:
            save_profile(name, self.cfg)
            self._profiles = load_profiles()
        except (OSError, ValueError, TypeError) as exc:
            logger.exception("Failed to save profile '%s'.", name)
            messagebox.showerror("Erro ao salvar perfil", str(exc), parent=self)
            return
        self._refresh_profile_choices(name)

    def _load_selected_profile(self):
        name = self.sens_profile_choice.get()
        if name not in self._profiles:
            messagebox.showerror("Perfil indisponível", "Selecione um perfil salvo.", parent=self)
            return

        self.cfg = EngineConfig(**asdict(self._profiles[name]))
        self.engine.update_config(self.cfg)
        slider_labels = {
            "sens_x": "Sensibilidade Base",
            "sens_y": "Sensibilidade Base",
            "filter_x": "Multiplicador Filtro",
            "filter_y": "Multiplicador Filtro",
            "curve_x": "Curva de Resposta",
            "curve_y": "Curva de Resposta",
            "acceleration": "Acelerador Dinâmico (S-Curve)",
            "hardware_gain": "Ganho Bruto do Sensor",
            "friction": "Suavização / Fricção",
            "inverse_deadzone": "Compensação de Deadzone",
        }
        for key, slider in self._sliders.items():
            value = getattr(self.cfg, key)
            slider.set(value)
            number_format = (
                ".0f" if key in ("sens_x", "sens_y", "inverse_deadzone")
                else ".1f" if key == "hardware_gain"
                else ".3f" if key == "friction"
                else ".2f"
            )
            self._slider_lbls[key].configure(
                text=f"{slider_labels[key]}: {value:{number_format}}"
            )
        for key, (slider, value_label, label, suffix) in self._macro_controls.items():
            value = getattr(self.cfg, key)
            slider.set(value)
            value_label.configure(text=f"{label}: {value:.0f}{suffix}")
        for key, option in (
            ("yy_active", self.chk_yy),
            ("slide_cancel_active", self.chk_slide_cancel),
            ("auto_ping_active", self.chk_auto_ping),
            ("no_recoil_active", self.chk_norecoil),
            ("buffed_aim_active", self.chk_buffed),
        ):
            option.select() if getattr(self.cfg, key) else option.deselect()
        self._sync_recoil_profile_menu()
        for key in self._mapping_entries:
            self._refresh_mapping_entry(key)
        self._refresh_home_stats()
        self._save_cfg()

    # ── MAPPING ───────────────────────────────────────────────
    def _build_map(self):
        f = self.tabs["map"]
        ctk.CTkLabel(
            f, text="MAPEAMENTO DO CONTROLE",
            font=T.FONT_TITLE, text_color=T.TEXT_PRIMARY
        ).grid(row=0, column=0, padx=32, pady=(18, 10), sticky="w")

        f.grid_columnconfigure(0, weight=1)
        f.grid_rowconfigure(1, weight=1)

        content = ctk.CTkFrame(f, fg_color="transparent")
        content.grid(row=1, column=0, sticky="nsew", padx=24, pady=(0, 12))
        f.grid_rowconfigure(1, weight=1)
        card = ctk.CTkFrame(content, fg_color=T.BG_CARD, corner_radius=10)
        card.pack(fill="x", padx=4, pady=4)
        ctk.CTkLabel(
            card, text="MAPEAMENTO COMPLETO DO CONTROLE VIRTUAL",
            font=T.FONT_SECTION, text_color=T.ORANGE
        ).pack(anchor="w", padx=14, pady=(9, 4))

        mappings = [
            ("Botão A (Pular)", "vk_a"),
            ("Botão B (Agachar)", "vk_b"),
            ("Botão Y (Trocar arma)", "vk_y"),
            ("Left Shoulder (LB)", "vk_lb"),
            ("Right Shoulder (RB)", "vk_rb"),
            ("Left Thumb (LS Run)", "vk_ls"),
            ("Right Thumb (RS Melee)", "vk_rs"),
            ("Atalho Global (Ligar / Desligar)", "vk_toggle"),
            ("Atalho Slide Cancel", "vk_slide_cancel"),
            ("Atalho Macro YY", "vk_yy"),
        ]
        for label, config_key in mappings:
            row = ctk.CTkFrame(card, fg_color="transparent")
            row.pack(fill="x", padx=14, pady=2)
            ctk.CTkLabel(
                row, text=label, font=T.FONT_BODY, text_color=T.TEXT_PRIMARY,
                anchor="w",
            ).pack(side="left", fill="x", expand=True)

            entry = ctk.CTkEntry(
                row, width=170, height=27, justify="center",
                font=T.FONT_HUD, text_color=T.ORANGE,
                fg_color=T.BG_PANEL, border_color=T.BORDER,
            )
            entry.insert(0, self._vk_name(getattr(self.cfg, config_key)))
            entry.configure(state="readonly")
            entry.pack(side="right")
            entry.bind(
                "<Button-1>",
                lambda _event, key=config_key: self._begin_mapping_capture(key),
            )
            entry.bind(
                "<KeyPress>",
                lambda event, key=config_key: self._capture_mapping_key(event, key),
            )
            self._mapping_entries[config_key] = entry

        ctk.CTkLabel(
            card,
            text="Clique em um campo e pressione a nova tecla para remapear.",
            font=T.FONT_SMALL, text_color=T.TEXT_MUTED,
        ).pack(anchor="w", padx=14, pady=(6, 9))

        presets = ctk.CTkFrame(content, fg_color=T.BG_CARD, corner_radius=10)
        presets.pack(fill="x", padx=4, pady=(4, 0))
        ctk.CTkLabel(
            presets, text="PRESETS DE SENSIBILIDADE",
            font=T.FONT_SECTION, text_color=T.CYAN_HUD,
        ).pack(anchor="w", padx=14, pady=(7, 4))
        preset_row = ctk.CTkFrame(presets, fg_color="transparent")
        preset_row.pack(anchor="w", padx=10, pady=(0, 7))
        for name, values in [
            ("Default", (4453, 2.1, 0.7, 7250, 2.1, 0.7, 0.8, 4.5)),
            ("Aggressive", (9000, 3.5, 0.9, 11000, 3.5, 0.9, 1.1, 1.7)),
            ("Precision", (2800, 1.4, 0.55, 4200, 1.4, 0.55, 0.5, 1.0)),
        ]:
            ctk.CTkButton(
                preset_row, text=name, width=120, height=29,
                fg_color=T.BG_PANEL, hover_color=T.BG_CARD_HOVER,
                border_width=1, border_color=T.BORDER, text_color=T.TEXT_PRIMARY,
                command=lambda preset=values: self._apply_preset(*preset),
            ).pack(side="left", padx=4)

    # ── MACROS ────────────────────────────────────────────────
    def _build_macro(self):
        f = self.tabs["macro"]
        ctk.CTkLabel(
            f, text="MACROS E ASSISTÊNCIAS",
            font=T.FONT_TITLE, text_color=T.TEXT_PRIMARY
        ).grid(row=0, column=0, padx=32, pady=(18, 10), sticky="w")

        content = ctk.CTkFrame(f, fg_color="transparent")
        content.grid(row=1, column=0, padx=24, pady=(0, 12), sticky="nsew")
        f.grid_columnconfigure(0, weight=1)
        f.grid_rowconfigure(1, weight=1)
        grid = ctk.CTkFrame(content, fg_color="transparent")
        grid.pack(fill="both", expand=True, padx=4)
        grid.grid_columnconfigure((0, 1), weight=1)

        utilities = self._macro_card(grid, "MACRO UTILITÁRIOS", 0, 0)
        self.chk_yy = self._macro_checkbox(
            utilities, "Ativar YY", self.cfg.yy_active,
            lambda: self._set_macro_option("yy_active", self.chk_yy.get()),
        )
        self._add_macro_slider(
            utilities, "Intervalo YY", "yy_interval_ms",
            30, 500, self.cfg.yy_interval_ms, "ms",
        )

        slide = self._macro_card(grid, "SLIDE CANCEL", 0, 1)
        self.chk_slide_cancel = self._macro_checkbox(
            slide, "Ativar Slide Cancel", self.cfg.slide_cancel_active,
            lambda: self._set_macro_option(
                "slide_cancel_active", self.chk_slide_cancel.get()
            ),
        )

        ping = self._macro_card(grid, "AUTO PING", 1, 0)
        self.chk_auto_ping = self._macro_checkbox(
            ping, "Ativar Auto Ping", self.cfg.auto_ping_active,
            lambda: self._set_macro_option(
                "auto_ping_active", self.chk_auto_ping.get()
            ),
        )
        self._add_macro_slider(
            ping, "Intervalo Ping", "auto_ping_interval_ms",
            100, 2000, self.cfg.auto_ping_interval_ms, "ms",
        )

        recoil = self._macro_card(grid, "NO RECOIL", 1, 1)
        self.chk_norecoil = self._macro_checkbox(
            recoil, "Ativar compensação", self.cfg.no_recoil_active,
            self._on_norecoil,
        )
        ctk.CTkLabel(
            recoil, text="Padrão da arma",
            font=T.FONT_SMALL, text_color=T.TEXT_MUTED, anchor="w",
        ).pack(fill="x", padx=12, pady=(0, 0))
        profile_ids = list(self._recoil_profiles.keys())
        labels = [self._recoil_profiles[pid].name for pid in profile_ids]
        self._recoil_profile_ids = profile_ids
        self._recoil_profile_labels = labels
        self.recoil_profile_menu = ctk.CTkOptionMenu(
            recoil,
            values=labels,
            height=26,
            font=T.FONT_BODY,
            fg_color=T.BG_PANEL,
            button_color=T.BG_CARD_HOVER,
            button_hover_color=T.BORDER,
            text_color=T.TEXT_PRIMARY,
            command=self._on_recoil_profile,
        )
        self.recoil_profile_menu.pack(fill="x", padx=12, pady=(2, 2))
        self.lbl_recoil_hint = ctk.CTkLabel(
            recoil, text="", font=T.FONT_SMALL, text_color=T.TEXT_DIM, anchor="w",
        )
        self.lbl_recoil_hint.pack(fill="x", padx=12, pady=(0, 4))
        self._sync_recoil_profile_menu()
        self._add_macro_slider(
            recoil, "Compensação Vertical", "no_recoil_force_y",
            -5000, 5000, self.cfg.no_recoil_force_y, "",
        )
        self._add_macro_slider(
            recoil, "Ajuste Horizontal", "no_recoil_force_x",
            -5000, 5000, self.cfg.no_recoil_force_x, "",
        )

        rotation = self._macro_card(grid, "MACRO ROTACIONAL (LEFT STICK)", 2, 0, 2)
        self.chk_buffed = self._macro_checkbox(
            rotation, "Ativar suporte rotacional automático",
            self.cfg.buffed_aim_active, self._on_buffed_toggle,
        )
        self._add_macro_slider(
            rotation, "Intensidade de Ajuste Assistido",
            "buffed_aim_force", 0, 40, self.cfg.buffed_aim_force, "",
        )

    def _macro_card(self, parent, title, row, column, columnspan=1):
        card = ctk.CTkFrame(parent, fg_color=T.BG_CARD, corner_radius=10)
        card.grid(
            row=row, column=column, columnspan=columnspan,
            padx=4, pady=4, sticky="nsew",
        )
        ctk.CTkLabel(
            card, text=title, font=T.FONT_SECTION, text_color=T.GREEN_TACT
        ).pack(anchor="w", padx=12, pady=(8, 3))
        return card

    def _macro_checkbox(self, parent, text, selected, command):
        checkbox = ctk.CTkSwitch(
            parent, text=text, font=T.FONT_BODY, text_color=T.TEXT_PRIMARY,
            progress_color=T.ORANGE, button_color=T.TEXT_PRIMARY,
            button_hover_color=T.AMBER, command=command,
        )
        checkbox.pack(anchor="w", padx=12, pady=(2, 5))
        if selected:
            checkbox.select()
        return checkbox

    def _add_macro_slider(self, parent, label, key, minimum, maximum, value, suffix):
        value_label = ctk.CTkLabel(
            parent, text=f"{label}: {value:.0f}{suffix}",
            font=T.FONT_SMALL, text_color=T.TEXT_MUTED, anchor="w",
        )
        value_label.pack(fill="x", padx=12, pady=(2, 0))
        steps = 10000 if key in ("no_recoil_force_x", "no_recoil_force_y") else 200
        slider = ctk.CTkSlider(
            parent, from_=minimum, to=maximum, number_of_steps=steps,
            progress_color=T.ORANGE, button_color=T.ORANGE,
            button_hover_color=T.AMBER, fg_color=T.BORDER,
            command=lambda new_value, k=key, lbl=value_label, name=label, unit=suffix:
                self._on_macro_slider(k, name, unit, lbl, new_value),
        )
        slider.set(value)
        slider.pack(fill="x", padx=12, pady=(0, 7))
        self._macro_controls[key] = (slider, value_label, label, suffix)

    def _on_macro_slider(self, key, label, suffix, value_label, value):
        setattr(self.cfg, key, value)
        value_label.configure(text=f"{label}: {value:.0f}{suffix}")
        self.engine.update_config(self.cfg)
        self._schedule_config_save()

    def _set_macro_option(self, key, value):
        setattr(self.cfg, key, bool(value))
        self.engine.update_config(self.cfg)
        self._schedule_config_save()

    def _on_norecoil(self):
        self._set_macro_option("no_recoil_active", self.chk_norecoil.get())

    def _on_recoil_profile(self, label: str):
        for profile_id, name in zip(self._recoil_profile_ids, self._recoil_profile_labels):
            if name == label:
                self.cfg.recoil_profile = profile_id
                self.engine.update_config(self.cfg)
                self._schedule_config_save()
                self._refresh_recoil_hint()
                return

    def _sync_recoil_profile_menu(self):
        profile = self._recoil_profiles.get(self.cfg.recoil_profile)
        if profile is None:
            profile = self._recoil_profiles["constant"]
            self.cfg.recoil_profile = "constant"
        self.recoil_profile_menu.set(profile.name)
        self._refresh_recoil_hint()

    def _refresh_recoil_hint(self):
        profile = self._recoil_profiles.get(self.cfg.recoil_profile)
        if profile is None:
            self.lbl_recoil_hint.configure(text="Puxada constante")
            return
        if profile.id == "constant":
            self.lbl_recoil_hint.configure(text="Puxada constante (sem curva)")
        elif profile.rpm:
            self.lbl_recoil_hint.configure(
                text=f"{profile.name} · {int(profile.rpm)} RPM · {profile.mag} tiros"
            )
        else:
            self.lbl_recoil_hint.configure(text=profile.name)

    def _on_buffed_toggle(self):
        self._set_macro_option("buffed_aim_active", self.chk_buffed.get())

    def _begin_mapping_capture(self, config_key):
        self._mapping_capture = config_key
        entry = self._mapping_entries[config_key]
        entry.configure(state="normal")
        entry.delete(0, "end")
        entry.insert(0, "Pressione uma tecla")
        entry.configure(state="readonly")
        entry.focus_set()

    def _capture_mapping_key(self, event, config_key):
        if self._mapping_capture != config_key:
            return "break"
        if event.keysym == "Escape":
            self._mapping_capture = None
            self._refresh_mapping_entry(config_key)
            return "break"

        key_code = int(event.keycode)
        if not key_code:
            return "break"
        setattr(self.cfg, config_key, key_code)
        self._mapping_capture = None
        self._refresh_mapping_entry(config_key)
        self.engine.update_config(self.cfg)
        self.cfg.save()
        return "break"

    def _refresh_mapping_entry(self, config_key):
        entry = self._mapping_entries[config_key]
        entry.configure(state="normal")
        entry.delete(0, "end")
        entry.insert(0, self._vk_name(getattr(self.cfg, config_key)))
        entry.configure(state="readonly")

    def _start_global_hotkey_listener(self):
        if self._hotkey_listener is not None:
            return
        listener = keyboard.Listener(
            on_press=self._on_global_key_down,
            on_release=self._on_global_key_up,
        )
        try:
            listener.start()
        except Exception as exc:
            logger.exception("Failed to start the global toggle hotkey listener.")
            messagebox.showerror(
                "Atalho global indisponível",
                f"Não foi possível iniciar a captura global do teclado:\n{exc}",
                parent=self,
            )
            return
        self._hotkey_listener = listener

    def _on_global_key_down(self, key):
        vk = InputCapture._vk_from_key(key)
        if self._auxilio_ai_capture_target is not None:
            if vk == 0x1B:
                self.after(0, self._cancel_aux_ai_key_capture)
                return
            label = self._aux_ai_key_label(vk or 0)
            if label is not None:
                target = self._auxilio_ai_capture_target
                self.after(0, self._assign_aux_ai_key, target, label)
            return
        menu_vk = self._aux_ai_vkey(self._auxilio_ai_settings["menu_key"])
        if vk == menu_vk and not self._auxilio_ai_menu_key_down:
            self._auxilio_ai_menu_key_down = True
            target_tab = "home" if self._current_tab == "auxilio_ai" else "auxilio_ai"
            try:
                self.after(0, self._show_tab, target_tab)
            except RuntimeError:
                logger.debug("Ignoring Auxilio-AI menu hotkey after UI shutdown.")
            return
        if vk != self.cfg.vk_toggle or self._toggle_key_down:
            return
        self._toggle_key_down = True
        if self._mapping_capture is None:
            try:
                self.after(0, self._toggle_engine)
            except RuntimeError:
                logger.debug("Ignoring toggle input after the UI event loop stopped.")

    def _on_global_key_up(self, key):
        vk = InputCapture._vk_from_key(key)
        if vk == self.cfg.vk_toggle:
            self._toggle_key_down = False
        if vk == self._aux_ai_vkey(self._auxilio_ai_settings["menu_key"]):
            self._auxilio_ai_menu_key_down = False

    def _cancel_aux_ai_key_capture(self):
        self._auxilio_ai_capture_target = None
        self._restore_aux_ai_key_labels()
        self._aux_ai_message.configure(text="Captura de tecla cancelada")

    @staticmethod
    def _vk_name(vk):
        named = {
            0x01: "Mouse 1", 0x02: "Mouse 2", 0x09: "Tab",
            0x0D: "Enter", 0x10: "Shift", 0x11: "Ctrl",
            0x12: "Alt", 0x14: "Caps Lock", 0x1B: "Esc",
            0x20: "Space", 0x21: "PageUp", 0x22: "PageDown",
            0x23: "End", 0x24: "Home", 0x25: "Left",
            0x26: "Up", 0x27: "Right", 0x28: "Down",
            0x2D: "Insert", 0x2E: "Delete",
            0x5B: "Win", 0x5C: "Win",
        }
        if vk in named:
            return named[vk]
        if 0x30 <= vk <= 0x39 or 0x41 <= vk <= 0x5A:
            return chr(vk)
        if 0x70 <= vk <= 0x87:
            return f"F{vk - 0x6F}"
        return f"VK {vk:02X}"

    def _apply_preset(self, sx, fx, cx, sy, fy, cy, accel, gain):
        values = {
            "sens_x": sx, "filter_x": fx, "curve_x": cx,
            "sens_y": sy, "filter_y": fy, "curve_y": cy,
            "acceleration": accel, "hardware_gain": gain,
        }
        for key, value in values.items():
            self._sliders[key].set(value)
            self._on_slider(key, value)
        self.cfg.save()
        self.engine.update_config(self.cfg)

    # ══════════════════════════════════════════════════════════
    # ENGINE CONTROL
    # ══════════════════════════════════════════════════════════
    def _toggle_engine(self):
        if self._engine_running:
            self._stop_engine()
        else:
            self._start_engine()

    def _start_engine(self):
        self.engine.update_config(self.cfg)
        if sys.platform == "win32" and not self.engine.virtual_pad_available:
            reason = self.engine.virtual_pad_error or "Motivo desconhecido."
            if messagebox.askyesno(
                "Controle virtual indisponível",
                "O BioSync não conseguiu inicializar o controle virtual.\n\n"
                f"Detalhe: {reason}\n\n"
                "Se o ViGEmBus não estiver instalado, deseja abrir a página oficial "
                "para baixá-lo?",
                parent=self,
            ):
                webbrowser.open("https://github.com/nefarius/ViGEmBus/releases")
            return
        self.capture = InputCapture(
            on_mouse_delta=self.engine.inject_raw_delta,
            on_key=self.engine.set_key,
            window_handle=self.winfo_id(),
        )
        try:
            self.capture.start()
            self.engine.start()
        except Exception as exc:
            if self.capture:
                self.capture.stop()
                self.capture = None
            self.engine.stop()
            messagebox.showerror("Não foi possível iniciar", str(exc), parent=self)
            return
        self._engine_running = True
        self.lbl_status.configure(text="● ARMED", text_color=T.GREEN_TACT)
        self.btn_toggle.configure(text="DISARM", fg_color=T.RED_ALERT, hover_color="#B02A37")
        self._stat_engine._value_lbl.configure(text="ARMED", text_color=T.GREEN_TACT)

    def _stop_engine(self):
        if self.capture:
            self.capture.stop()
            self.capture = None
        self.engine.stop()
        self._engine_running = False
        self.lbl_status.configure(text="● STANDBY", text_color=T.TEXT_DIM)
        self.btn_toggle.configure(text="ARM ENGINE", fg_color=T.GOLD, hover_color=T.GOLD_DIM)
        self._stat_engine._value_lbl.configure(text="STANDBY", text_color=T.TEXT_DIM)

    def _refresh_home_stats(self):
        if hasattr(self, "_stat_sens"):
            self._stat_sens._value_lbl.configure(
                text=f"{self.cfg.sens_x:.0f}  /  {self.cfg.sens_y:.0f}"
            )

    def _on_close(self):
        if self._auxilio_ai_setup_poll_id is not None:
            self.after_cancel(self._auxilio_ai_setup_poll_id)
            self._auxilio_ai_setup_poll_id = None
        if (
            self._auxilio_ai_setup_process is not None
            and self._auxilio_ai_setup_process.poll() is None
        ):
            self._auxilio_ai_setup_process.terminate()
            try:
                self._auxilio_ai_setup_process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self._auxilio_ai_setup_process.kill()
                self._auxilio_ai_setup_process.wait()
        self._auxilio_ai_setup_process = None
        self._auxilio_ai_setup_stage = None
        if self._auxilio_ai_poll_id is not None:
            self.after_cancel(self._auxilio_ai_poll_id)
            self._auxilio_ai_poll_id = None
        if self._auxilio_ai_process is not None:
            if self._auxilio_ai_process.poll() is None:
                if self._auxilio_ai_process.stdin is not None:
                    try:
                        self._auxilio_ai_process.stdin.write("STOP\n")
                        self._auxilio_ai_process.stdin.flush()
                    except OSError:
                        logger.exception("Could not send Auxilio-AI shutdown command.")
                try:
                    self._auxilio_ai_process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    self._auxilio_ai_process.terminate()
                    try:
                        self._auxilio_ai_process.wait(timeout=2)
                    except subprocess.TimeoutExpired:
                        self._auxilio_ai_process.kill()
                        self._auxilio_ai_process.wait()
            self._auxilio_ai_process = None
        self._stop_engine()
        if self._hotkey_listener:
            self._hotkey_listener.stop()
            self._hotkey_listener = None
        self._save_cfg()
        self.destroy()
