import json
import re
import sys
import tkinter as tk
from pathlib import Path

import customtkinter as ctk
import win32api

from gui.settings_menu import AIM_LABELS, COLOR_VALUES, HOTKEY_CODES, MENU_HOTKEY_CODES, MOUSE_HOTKEY_CODES
from gui.view_settings import merge_view_settings

KEYSYM_ALIASES = {
    "Shift_L": "Shift",
    "Shift_R": "Shift",
    "Control_L": "Ctrl",
    "Control_R": "Ctrl",
    "Alt_L": "Alt",
    "Alt_R": "Alt",
    "Return": "Enter",
    "space": "Space",
    "BackSpace": "Backspace",
    "Prior": "Page Up",
    "Next": "Page Down",
    "Caps_Lock": "Caps Lock",
}
MOUSE_BUTTONS = {1: "Left mouse", 2: "Middle mouse", 3: "Right mouse"}
MOUSE_KEY_LABELS = {
    "Left mouse": "Botao esquerdo",
    "Right mouse": "Botao direito",
    "Middle mouse": "Botao central",
    "Mouse 4": "Botao lateral 1",
    "Mouse 5": "Botao lateral 2",
}
MOUSE_LABEL_KEYS = {label: key for key, label in MOUSE_KEY_LABELS.items()}


class SafeCTkToplevel(ctk.CTkToplevel):
    def destroy(self):
        commands = set(self._tclCommands or ())
        try:
            for after_id in self.tk.call("after", "info"):
                script = str(self.tk.call("after", "info", after_id)[0])
                if script in commands:
                    self.after_cancel(after_id)
        except tk.TclError:
            pass
        super().destroy()


class SettingsMenu:
    def __init__(self, root, settings, on_apply, on_force_close=None):
        ctk.set_appearance_mode("Dark")
        self.host_root = root
        root.bind("<Destroy>", self._on_root_destroy, add="+")
        self.on_apply = on_apply
        self.on_force_close = on_force_close or root.destroy
        self.colors = {
            "window": "#12141D",
            "sidebar": "#0C0D12",
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
        self.window = SafeCTkToplevel(root, fg_color=self.colors["window"])
        icon_root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
        icon_path = icon_root / "BioSync_AI-ico.ico"
        if icon_path.is_file():
            self.window.iconbitmap(str(icon_path))
        self.window.title("BS | HUB - BioSync AI")
        self.window.geometry("1000x680+42+42")
        self.window.minsize(900, 620)
        self.window.resizable(True, True)
        self.window.attributes("-topmost", True)
        self.window.protocol("WM_DELETE_WINDOW", self.hide)
        self.window.bind("<KeyPress>", self._on_key_press)
        self.window.bind("<ButtonPress>", self._on_mouse_press)

        self._capture_target = None
        self._mouse_capture_after_id = None
        self.fov_var = tk.DoubleVar(master=self.window, value=settings["fov"])
        self.smoothing_var = tk.DoubleVar(master=self.window, value=settings["smoothing"])
        self.humanizer_speed_var = tk.DoubleVar(
            master=self.window,
            value=settings.get("humanizer_speed", 2000),
        )
        self.aim_var = tk.StringVar(master=self.window, value=self._aim_label(settings["aim_point"]))
        aim_key = settings.get("aim_key", "Right mouse")
        self.hotkey_var = tk.StringVar(master=self.window, value=aim_key if aim_key in HOTKEY_CODES else "Right mouse")
        self.mouse_aim_key_var = tk.StringVar(
            master=self.window,
            value=MOUSE_KEY_LABELS.get(self.hotkey_var.get(), "Selecione..."),
        )
        menu_key = settings.get("menu_key", "X")
        self.menu_hotkey_var = tk.StringVar(master=self.window, value=menu_key if menu_key in MENU_HOTKEY_CODES else "X")
        self.show_fov_var = tk.BooleanVar(master=self.window, value=settings["show_fov"])
        self.color_var = tk.StringVar(master=self.window, value=self._color_label(settings["fov_color"]))
        self.fov_hex_var = tk.StringVar(master=self.window, value=settings["fov_color"])
        self.opacity_var = tk.DoubleVar(master=self.window, value=settings["overlay_opacity"])
        self.view_values = merge_view_settings(settings)
        self.view_vars = {}
        self.view_sliders = {}
        self.view_suffixes = {}
        for key, value in self.view_values.items():
            if key in ("min_distance", "max_distance"):
                value = float(value) * 100
            variable_type = tk.BooleanVar if isinstance(value, bool) else (
                tk.StringVar if isinstance(value, str) else tk.DoubleVar
            )
            self.view_vars[key] = variable_type(master=self.window, value=value)
        self.view_vars["show_fov"] = self.show_fov_var
        self.view_vars["overlay_opacity"] = self.opacity_var
        self.view_vars["fov_color"] = self.fov_hex_var
        self.view_labels = {}
        self.profile_name_var = tk.StringVar(master=self.window, value="default")
        self.profile_choice_var = tk.StringVar(master=self.window, value="")
        self.status_var = tk.StringVar(master=self.window, value="Pronto")
        self.fov_value_var = tk.StringVar(master=self.window)
        self.smoothing_value_var = tk.StringVar(master=self.window)
        self.humanizer_speed_value_var = tk.StringVar(master=self.window)
        self.opacity_value_var = tk.StringVar(master=self.window)
        self.show_fov_value_var = tk.StringVar(master=self.window)
        self.title_var = tk.StringVar(master=self.window)
        self.subtitle_var = tk.StringVar(master=self.window)
        self.aim_preview_label_var = tk.StringVar(master=self.window, value=self.aim_var.get().upper())
        self.profile_summary = tk.StringVar(master=self.window)
        self._update_value_labels()
        self.show_fov_value_var.set("ON" if self.show_fov_var.get() else "OFF")

        self.window.grid_rowconfigure(0, weight=1)
        self.window.grid_columnconfigure(1, weight=1)
        self._build_sidebar()
        self._build_main_area()
        self.show_page("aim")
        self.refresh_profiles()
        self.window.deiconify()
        self.window.lift()

    def _build_sidebar(self):
        sidebar = ctk.CTkFrame(self.window, width=205, corner_radius=0, fg_color=self.colors["sidebar"])
        sidebar.grid(row=0, column=0, sticky="nsew")
        sidebar.grid_propagate(False)
        sidebar.grid_columnconfigure(0, weight=1)
        sidebar.grid_rowconfigure(5, weight=1)

        ctk.CTkLabel(
            sidebar,
            text="BS | HUB",
            font=("Segoe UI", 23, "bold"),
            text_color=self.colors["cyan"],
        ).grid(row=0, column=0, sticky="w", padx=20, pady=(25, 0))
        ctk.CTkLabel(
            sidebar,
            text="BioSync | AI",
            font=("Segoe UI", 11, "bold"),
            text_color=self.colors["muted"],
        ).grid(row=1, column=0, sticky="w", padx=20, pady=(0, 20))
        ctk.CTkFrame(sidebar, height=2, fg_color=self.colors["accent"], corner_radius=0).grid(
            row=2, column=0, sticky="ew", padx=18, pady=(0, 18)
        )

        self.page_titles = {
            "aim": ("Configuracao", "FOV, resposta e atalhos"),
            "views": ("Views", "ESP, deteccoes e indicadores"),
            "profiles": ("Perfis", "Configuracoes salvas"),
        }
        self.page_buttons = {}
        for row, (page, label) in enumerate(
            (("aim", "CONFIGURACAO"), ("views", "VIEWS"), ("profiles", "PERFIS")),
            start=3,
        ):
            button = ctk.CTkButton(
                sidebar,
                text=label,
                anchor="w",
                height=42,
                corner_radius=7,
                fg_color="transparent",
                hover_color=self.colors["field"],
                text_color=self.colors["muted"],
                command=lambda selected=page: self.show_page(selected),
            )
            button.grid(row=row, column=0, sticky="ew", padx=12, pady=4)
            self.page_buttons[page] = button

        footer = ctk.CTkFrame(sidebar, fg_color="transparent")
        footer.grid(row=6, column=0, sticky="sew", padx=15, pady=18)
        ctk.CTkFrame(footer, height=1, fg_color=self.colors["line"], corner_radius=0).pack(fill="x", pady=(0, 12))
        status = ctk.CTkFrame(footer, fg_color=self.colors["panel"], corner_radius=7)
        status.pack(fill="x", pady=(0, 10))
        ctk.CTkLabel(status, text="●", text_color=self.colors["success"], font=("Segoe UI", 13)).pack(
            side="left", padx=(10, 6), pady=8
        )
        ctk.CTkLabel(status, text="MOTOR PRONTO", text_color=self.colors["text"], font=("Segoe UI", 10, "bold")).pack(
            side="left", pady=8
        )
        self.sidebar_hotkey_label = ctk.CTkLabel(
            footer,
            text=f"ATALHO DO MENU  {self.menu_hotkey_var.get()}",
            text_color=self.colors["muted"],
            font=("Segoe UI", 9),
        )
        self.sidebar_hotkey_label.pack(anchor="w")
        self.force_close_button = ctk.CTkButton(
            footer,
            text="FORCE CLOSE",
            height=36,
            corner_radius=6,
            fg_color="#572632",
            hover_color="#783344",
            text_color=self.colors["text"],
            command=self._confirm_force_close,
        )
        self.force_close_button.pack(fill="x", pady=(12, 0))

    def _confirm_force_close(self):
        dialog = SafeCTkToplevel(self.window, fg_color=self.colors["window"])
        dialog.title("Encerrar BioSync")
        dialog.geometry("380x180")
        dialog.resizable(False, False)
        dialog.attributes("-topmost", True)
        dialog.transient(self.window)
        dialog.grid_columnconfigure((0, 1), weight=1)
        ctk.CTkLabel(
            dialog,
            text="Fechar o BioSync completamente?",
            font=("Segoe UI", 15, "bold"),
            text_color=self.colors["text"],
        ).grid(row=0, column=0, columnspan=2, sticky="w", padx=22, pady=(25, 6))
        ctk.CTkLabel(
            dialog,
            text="A captura e todas as janelas serao encerradas.",
            font=("Segoe UI", 10),
            text_color=self.colors["muted"],
        ).grid(row=1, column=0, columnspan=2, sticky="w", padx=22)
        ctk.CTkButton(
            dialog,
            text="Cancelar",
            height=36,
            corner_radius=6,
            fg_color=self.colors["field"],
            hover_color=self.colors["line"],
            command=dialog.destroy,
        ).grid(row=2, column=0, sticky="ew", padx=(22, 6), pady=(22, 18))
        self.force_close_confirm_button = ctk.CTkButton(
            dialog,
            text="Fechar app",
            height=36,
            corner_radius=6,
            fg_color="#8B2F43",
            hover_color="#A43A52",
            command=self.on_force_close,
        )
        self.force_close_confirm_button.grid(row=2, column=1, sticky="ew", padx=(6, 22), pady=(22, 18))
        dialog.bind("<Escape>", lambda _event: dialog.destroy())
        dialog.grab_set()
        dialog.focus_force()

    def _build_main_area(self):
        main = ctk.CTkFrame(self.window, fg_color="transparent")
        main.grid(row=0, column=1, sticky="nsew", padx=(24, 24), pady=(20, 16))
        main.grid_columnconfigure(0, weight=1)
        main.grid_rowconfigure(2, weight=1)

        header = ctk.CTkFrame(main, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", pady=(0, 15))
        header.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            header,
            textvariable=self.title_var,
            font=("Segoe UI", 22, "bold"),
            text_color=self.colors["cyan"],
        ).grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(
            header,
            textvariable=self.subtitle_var,
            font=("Segoe UI", 10),
            text_color=self.colors["muted"],
        ).grid(row=1, column=0, sticky="w", pady=(3, 0))
        ctk.CTkButton(
            header,
            text="Ocultar",
            width=88,
            height=34,
            corner_radius=7,
            fg_color=self.colors["field"],
            hover_color=self.colors["line"],
            command=self.hide,
        ).grid(row=0, column=1, rowspan=2, sticky="e")
        ctk.CTkFrame(main, height=1, fg_color=self.colors["line"], corner_radius=0).grid(
            row=1, column=0, sticky="ew", pady=(0, 15)
        )

        self.page_host = ctk.CTkFrame(main, fg_color="transparent")
        self.page_host.grid(row=2, column=0, sticky="nsew")
        self.page_host.grid_columnconfigure(0, weight=1)
        self.page_host.grid_rowconfigure(0, weight=1)
        self.pages = {}
        self._build_aim_page()
        self._build_views_page()
        self._build_profiles_page()

        footer = ctk.CTkFrame(main, fg_color="transparent")
        footer.grid(row=3, column=0, sticky="ew", pady=(14, 0))
        footer.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(footer, textvariable=self.status_var, text_color=self.colors["muted"], font=("Segoe UI", 10)).grid(
            row=0, column=0, sticky="w"
        )
        ctk.CTkButton(
            footer,
            text="Salvar perfil",
            width=120,
            height=38,
            corner_radius=7,
            fg_color=self.colors["field"],
            hover_color=self.colors["line"],
            command=self.save_profile,
        ).grid(row=0, column=1, padx=(8, 0))
        ctk.CTkButton(
            footer,
            text="Aplicar",
            width=120,
            height=38,
            corner_radius=7,
            fg_color=self.colors["accent"],
            hover_color=self.colors["accent_hover"],
            command=self.apply,
        ).grid(row=0, column=2, padx=(8, 0))

    def _make_panel(self, parent, title, description):
        panel = ctk.CTkFrame(parent, fg_color=self.colors["panel"], corner_radius=8)
        panel.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(panel, text=title, font=("Segoe UI", 15, "bold"), text_color=self.colors["text"]).grid(
            row=0, column=0, columnspan=2, sticky="w", padx=18, pady=(17, 0)
        )
        ctk.CTkLabel(
            panel,
            text=description,
            font=("Segoe UI", 10),
            text_color=self.colors["muted"],
        ).grid(row=1, column=0, columnspan=2, sticky="w", padx=18, pady=(3, 14))
        return panel

    def _field_title(self, panel, row, title, value_var=None):
        ctk.CTkLabel(panel, text=title, font=("Segoe UI", 11, "bold"), text_color=self.colors["text"]).grid(
            row=row, column=0, sticky="w", padx=18, pady=(8, 5)
        )
        if value_var is not None:
            ctk.CTkLabel(
                panel,
                textvariable=value_var,
                font=("Segoe UI", 10, "bold"),
                text_color=self.colors["cyan"],
            ).grid(row=row, column=1, sticky="e", padx=18, pady=(8, 5))

    def _build_aim_page(self):
        page = ctk.CTkFrame(self.page_host, fg_color="transparent")
        page.grid_columnconfigure((0, 1), weight=1, uniform="aim")
        page.grid_rowconfigure(0, weight=1)
        self.pages["aim"] = page

        acquisition = self._make_panel(page, "Area de deteccao", "Defina o tamanho e o ponto de referencia")
        acquisition.grid(row=0, column=0, sticky="nsew", padx=(0, 7))
        response = self._make_panel(page, "Resposta e atalhos", "Configure controles de forma independente")
        response.grid(row=0, column=1, sticky="nsew", padx=(7, 0))

        self._field_title(acquisition, 2, "Tamanho do FOV", self.fov_value_var)
        self.fov_slider = ctk.CTkSlider(
            acquisition,
            from_=160,
            to=640,
            number_of_steps=30,
            command=self._on_fov_slider,
            fg_color=self.colors["field"],
            progress_color=self.colors["accent"],
            button_color=self.colors["cyan"],
            button_hover_color="#00B8CA",
        )
        self.fov_slider.grid(row=3, column=0, columnspan=2, sticky="ew", padx=18, pady=(2, 15))
        self.fov_slider.set(float(self.fov_var.get()))

        self._field_title(acquisition, 4, "Ponto de referencia")
        self.aim_selector = ctk.CTkSegmentedButton(
            acquisition,
            values=list(AIM_LABELS),
            command=self._on_aim_point,
            selected_color=self.colors["accent"],
            selected_hover_color=self.colors["accent_hover"],
            unselected_color=self.colors["field"],
            unselected_hover_color=self.colors["line"],
            text_color=self.colors["text"],
            corner_radius=6,
        )
        self.aim_selector.grid(row=5, column=0, columnspan=2, sticky="ew", padx=18, pady=(2, 14))
        self.aim_selector.set(self.aim_var.get())
        self._field_title(acquisition, 6, "Foco atual", self.aim_preview_label_var)
        acquisition.grid_rowconfigure(7, weight=1)
        self.aim_preview_canvas = tk.Canvas(acquisition, height=190, bg=self.colors["panel"], highlightthickness=0)
        self.aim_preview_canvas.grid(row=7, column=0, columnspan=2, sticky="nsew", padx=18, pady=(2, 14))
        self.aim_preview_canvas.bind("<Configure>", lambda _event: self._draw_aim_preview())
        self._draw_aim_preview()

        self._field_title(response, 2, "Tecla de ativacao")
        self.aim_key_button = self._key_button(response, self.hotkey_var.get(), "aim")
        self.aim_key_button.grid(row=2, column=1, sticky="e", padx=18, pady=(8, 5))
        ctk.CTkLabel(
            response,
            text="Botoes do mouse",
            text_color=self.colors["text"],
            font=("Segoe UI", 10, "bold"),
        ).grid(row=3, column=0, sticky="w", padx=18, pady=(2, 7))
        self.mouse_aim_key_option = ctk.CTkOptionMenu(
            response,
            values=["Selecione...", *MOUSE_LABEL_KEYS],
            variable=self.mouse_aim_key_var,
            command=self._on_activation_mouse_change,
            width=150,
            height=32,
            corner_radius=6,
            fg_color=self.colors["field"],
            button_color=self.colors["accent"],
            button_hover_color=self.colors["accent_hover"],
            dropdown_fg_color=self.colors["panel"],
            dropdown_hover_color=self.colors["field"],
        )
        self.mouse_aim_key_option.grid(row=3, column=1, sticky="e", padx=18, pady=(0, 5))
        ctk.CTkLabel(
            response,
            text="Ou capture uma tecla pelo botao acima",
            text_color=self.colors["muted"],
            font=("Segoe UI", 9),
        ).grid(row=4, column=0, columnspan=2, sticky="w", padx=18, pady=(0, 7))

        self._field_title(response, 5, "Atalho para abrir/fechar o menu")
        self.menu_key_button = self._key_button(response, self.menu_hotkey_var.get(), "menu")
        self.menu_key_button.grid(row=5, column=1, sticky="e", padx=18, pady=(8, 5))
        ctk.CTkLabel(
            response,
            text="Escolha uma tecla diferente da ativacao",
            text_color=self.colors["muted"],
            font=("Segoe UI", 9),
        ).grid(row=6, column=0, columnspan=2, sticky="w", padx=18, pady=(0, 6))

        self._field_title(response, 7, "Suavizacao da resposta", self.smoothing_value_var)
        self.smoothing_slider = ctk.CTkSlider(
            response,
            from_=0.05,
            to=1.0,
            number_of_steps=19,
            command=self._on_smoothing_slider,
            fg_color=self.colors["field"],
            progress_color=self.colors["accent"],
            button_color=self.colors["cyan"],
            button_hover_color="#00B8CA",
        )
        self.smoothing_slider.grid(row=8, column=0, columnspan=2, sticky="ew", padx=18, pady=(2, 13))
        self.smoothing_slider.set(float(self.smoothing_var.get()))
        self._field_title(
            response,
            9,
            "Humanizer · velocidade ate o alvo",
            self.humanizer_speed_value_var,
        )
        self.humanizer_speed_slider = ctk.CTkSlider(
            response,
            from_=200,
            to=4000,
            number_of_steps=38,
            command=self._on_humanizer_speed_slider,
            fg_color=self.colors["field"],
            progress_color=self.colors["accent"],
            button_color=self.colors["cyan"],
            button_hover_color="#00B8CA",
        )
        self.humanizer_speed_slider.grid(
            row=10, column=0, columnspan=2, sticky="ew",
            padx=18, pady=(2, 13),
        )
        self.humanizer_speed_slider.set(float(self.humanizer_speed_var.get()))

    def _key_button(self, parent, value, target):
        return ctk.CTkButton(
            parent,
            text=value,
            width=132,
            height=34,
            corner_radius=6,
            fg_color=self.colors["field"],
            hover_color=self.colors["line"],
            command=lambda: self._begin_key_capture(target),
        )

    def _build_views_page(self):
        page = ctk.CTkScrollableFrame(self.page_host, fg_color="transparent", corner_radius=0)
        page.grid_columnconfigure((0, 1), weight=1, uniform="views")
        self.pages["views"] = page

        cards = (
            ("ESP Box", "Caixa, estilo e cor", (
                ("switch", "esp_enabled", "Ativar boxes"),
                ("option", "esp_style", "Estilo", ["Normal", "Filled", "Corner"]),
                ("slider", "esp_thickness", "Espessura", 1, 8, 7, ""),
                ("entry", "esp_color", "Cor HEX"),
                ("slider", "esp_opacity", "Opacidade", 0, 100, 20, "%"),
            )),
            ("Distancia", "Area da caixa como proxy de proximidade", (
                ("switch", "distance_filter", "Filtrar por distancia"),
                ("slider", "min_distance", "Distancia minima (perto)", 0, 100, 100, "%"),
                ("slider", "max_distance", "Distancia maxima (longe)", 0, 100, 100, "%"),
            )),
            ("Filtro de falso positivo", "Limites de confianca e tamanho", (
                ("slider", "min_confidence", "Confidence minima", 0, 1, 100, ""),
                ("slider", "iou_threshold", "IOU", 0, 1, 100, ""),
                ("slider", "max_detections", "Maximo de deteccoes", 1, 100, 99, ""),
                ("switch", "ignore_small_targets", "Ignorar alvos muito pequenos"),
                ("slider", "min_box_area", "Area minima da caixa", 0, 25, 250, "%"),
                ("switch", "ignore_large_targets", "Ignorar alvos muito grandes"),
                ("slider", "max_box_area", "Area maxima da caixa", 0, 100, 100, "%"),
            )),
            ("Linhas e indicadores", "Marcacao do alvo selecionado", (
                ("switch", "snap_line", "Linha do centro ate o alvo"),
                ("entry", "snap_line_color", "Cor da linha HEX"),
                ("slider", "snap_line_thickness", "Espessura da linha", 1, 8, 7, ""),
                ("switch", "show_aim_marker", "Mostrar ponto de mira"),
                ("entry", "marker_color", "Cor do marcador HEX"),
            )),
            ("Skeleton / divisao corporal", "Zonas proporcionais dentro da caixa", (
                ("switch", "show_body_zones", "Desenhar zonas corporais"),
                ("entry", "head_color", "Cor da cabeca HEX"),
                ("entry", "chest_color", "Cor do peito HEX"),
                ("entry", "belly_color", "Cor da barriga HEX"),
            )),
            ("FOV visual", "Circulo guia do campo de visao", (
                ("switch", "show_fov", "Mostrar circulo FOV"),
                ("entry", "fov_color", "Cor do circulo HEX"),
                ("slider", "overlay_opacity", "Opacidade do overlay", 10, 100, 90, "%"),
            )),
        )
        for index, (title, description, controls) in enumerate(cards):
            card = self._make_panel(page, title, description)
            card.grid(row=index // 2, column=index % 2, sticky="new", padx=6, pady=6)
            row = 2
            for control in controls:
                self._add_view_control(card, row, control)
                row += 1
        page.grid_rowconfigure(3, weight=1)

    def _add_view_control(self, card, row, control):
        kind, key, label, *options = control
        ctk.CTkLabel(card, text=label, text_color=self.colors["text"], font=("Segoe UI", 10)).grid(
            row=row, column=0, sticky="w", padx=16, pady=5
        )
        variable = self.view_vars.get(key)
        if kind == "switch":
            widget = ctk.CTkSwitch(
                card, text="", variable=variable, onvalue=True, offvalue=False,
                progress_color=self.colors["accent"], button_color=self.colors["cyan"],
            )
            widget.grid(row=row, column=1, sticky="e", padx=16, pady=4)
        elif kind == "option":
            widget = ctk.CTkOptionMenu(
                card, variable=variable, values=options[0], width=110, height=30,
                fg_color=self.colors["field"], button_color=self.colors["accent"],
                dropdown_fg_color=self.colors["panel"],
            )
            widget.grid(row=row, column=1, sticky="e", padx=16, pady=4)
        elif kind == "entry":
            if key.endswith("_color"):
                color_controls = ctk.CTkFrame(card, fg_color="transparent")
                color_controls.grid(row=row, column=1, columnspan=2, sticky="e", padx=16, pady=4)
                preset_var = tk.StringVar(master=self.window, value=self._color_label(variable.get()))
                preset = ctk.CTkOptionMenu(
                    color_controls,
                    variable=preset_var,
                    values=list(COLOR_VALUES),
                    command=lambda choice, target=variable: target.set(COLOR_VALUES[choice]),
                    width=82,
                    height=30,
                    fg_color=self.colors["field"],
                    button_color=self.colors["accent"],
                    dropdown_fg_color=self.colors["panel"],
                )
                preset.pack(side="left", padx=(0, 5))
                widget = ctk.CTkEntry(
                    color_controls, textvariable=variable, width=94, height=30,
                    fg_color=self.colors["field"], border_color=self.colors["line"],
                )
                widget.pack(side="left")
            else:
                widget = ctk.CTkEntry(
                    card, textvariable=variable, width=110, height=30,
                    fg_color=self.colors["field"], border_color=self.colors["line"],
                )
                widget.grid(row=row, column=1, sticky="e", padx=16, pady=4)
        else:
            lower, upper, steps, suffix = options
            slider = ctk.CTkSlider(
                card, from_=lower, to=upper, number_of_steps=steps, width=130,
                fg_color=self.colors["field"], progress_color=self.colors["accent"],
                button_color=self.colors["cyan"],
                command=lambda value, k=key, s=suffix: self._on_view_slider(k, value, s),
            )
            slider.grid(row=row, column=1, sticky="e", padx=16, pady=4)
            slider_value = float(variable.get())
            if key in ("min_box_area", "max_box_area"):
                slider_value *= 100
            slider.set(slider_value)
            self.view_sliders[key] = slider
            self.view_suffixes[key] = suffix
            display_value = (
                float(variable.get()) * 100
                if key in ("min_box_area", "max_box_area")
                else variable.get()
            )
            self.view_labels[key] = ctk.CTkLabel(
                card, text=self._format_view_value(key, display_value, suffix),
                width=38, text_color=self.colors["cyan"], font=("Segoe UI", 9, "bold"),
            )
            self.view_labels[key].grid(row=row, column=2, sticky="e", padx=(0, 8))

    def _on_view_slider(self, key, value, suffix):
        setting_value = value / 100 if key in ("min_box_area", "max_box_area") else value
        self.view_vars[key].set(setting_value)
        if key == "overlay_opacity":
            self.opacity_var.set(value)
        if key in self.view_labels:
            self.view_labels[key].configure(text=self._format_view_value(key, value, suffix))
        self._draw_preview()

    @staticmethod
    def _format_view_value(key, value, suffix):
        if key in ("min_confidence", "iou_threshold"):
            return f"{float(value):.2f}"
        if key in ("min_box_area", "max_box_area"):
            return f"{float(value):.1f}{suffix}"
        if key in ("min_distance", "max_distance", "esp_opacity", "overlay_opacity"):
            return f"{int(round(float(value)))}{suffix}"
        return f"{int(round(float(value)))}{suffix}"

    def _build_profiles_page(self):
        page = ctk.CTkFrame(self.page_host, fg_color="transparent")
        page.grid_columnconfigure((0, 1), weight=1, uniform="profiles")
        page.grid_rowconfigure(0, weight=1)
        self.pages["profiles"] = page

        saved = self._make_panel(page, "Biblioteca de perfis", "Salve e recupere configuracoes")
        saved.grid(row=0, column=0, sticky="nsew", padx=(0, 7))
        current = self._make_panel(page, "Configuracao atual", "Resumo dos valores selecionados")
        current.grid(row=0, column=1, sticky="nsew", padx=(7, 0))

        ctk.CTkLabel(saved, text="Nome do perfil", text_color=self.colors["text"], font=("Segoe UI", 11, "bold")).grid(
            row=2, column=0, columnspan=2, sticky="w", padx=18, pady=(8, 4)
        )
        self.profile_name_entry = ctk.CTkEntry(
            saved,
            textvariable=self.profile_name_var,
            height=36,
            corner_radius=6,
            fg_color=self.colors["field"],
            border_color=self.colors["line"],
        )
        self.profile_name_entry.grid(row=3, column=0, columnspan=2, sticky="ew", padx=18)
        ctk.CTkLabel(saved, text="Perfis disponiveis", text_color=self.colors["text"], font=("Segoe UI", 11, "bold")).grid(
            row=4, column=0, columnspan=2, sticky="w", padx=18, pady=(18, 4)
        )
        self.profile_combo = ctk.CTkOptionMenu(
            saved,
            variable=self.profile_choice_var,
            values=["Sem perfis"],
            height=36,
            corner_radius=6,
            fg_color=self.colors["field"],
            button_color=self.colors["accent"],
            button_hover_color=self.colors["accent_hover"],
            dropdown_fg_color=self.colors["panel"],
            dropdown_hover_color=self.colors["field"],
        )
        self.profile_combo.grid(row=5, column=0, columnspan=2, sticky="ew", padx=18)
        ctk.CTkButton(
            saved,
            text="Carregar perfil",
            height=36,
            corner_radius=6,
            fg_color=self.colors["field"],
            hover_color=self.colors["line"],
            command=self.load_profile,
        ).grid(row=6, column=0, columnspan=2, sticky="e", padx=18, pady=(12, 0))

        self.profile_summary_label = ctk.CTkLabel(
            current,
            textvariable=self.profile_summary,
            justify="left",
            anchor="nw",
            text_color=self.colors["muted"],
            font=("Consolas", 12),
        )
        self.profile_summary_label.grid(row=2, column=0, columnspan=2, sticky="nw", padx=18, pady=(8, 0))
        for variable in (
            self.fov_var,
            self.smoothing_var,
            self.humanizer_speed_var,
            self.aim_var,
            self.hotkey_var,
            self.menu_hotkey_var,
            self.show_fov_var,
            self.color_var,
            self.opacity_var,
        ):
            variable.trace_add("write", lambda *_args: self._update_profile_summary())
        for variable in self.view_vars.values():
            variable.trace_add("write", lambda *_args: self._update_profile_summary())
        self._update_profile_summary()

    def _update_value_labels(self):
        self.fov_value_var.set(f"{int(round(float(self.fov_var.get())))} px")
        self.smoothing_value_var.set(f"{float(self.smoothing_var.get()):.2f}")
        self.humanizer_speed_value_var.set(
            f"{int(round(float(self.humanizer_speed_var.get())))} px/s"
        )
        self.opacity_value_var.set(f"{int(round(float(self.opacity_var.get())))}%")

    def _on_fov_slider(self, value):
        self.fov_var.set(int(round(float(value))))
        self.fov_value_var.set(f"{int(round(float(value)))} px")
        self._update_profile_summary()

    def _on_smoothing_slider(self, value):
        self.smoothing_var.set(round(float(value), 2))
        self.smoothing_value_var.set(f"{float(value):.2f}")
        self._update_profile_summary()

    def _on_humanizer_speed_slider(self, value):
        speed = int(round(float(value) / 100) * 100)
        self.humanizer_speed_var.set(speed)
        self.humanizer_speed_value_var.set(f"{speed} px/s")
        self._update_profile_summary()

    def _on_opacity_slider(self, value):
        self.opacity_var.set(int(round(float(value))))
        self.opacity_value_var.set(f"{int(round(float(value)))}%")
        self._update_profile_summary()

    def _on_aim_point(self, value):
        self.aim_var.set(value)
        self.aim_preview_label_var.set(value.upper())
        self._draw_aim_preview()
        self._update_profile_summary()

    def _on_activation_mouse_change(self, label):
        key = MOUSE_LABEL_KEYS.get(label)
        if key is None:
            return
        if key == self.menu_hotkey_var.get():
            self.mouse_aim_key_var.set(MOUSE_KEY_LABELS.get(self.hotkey_var.get(), "Selecione..."))
            self.status_var.set("A tecla de ativacao deve ser diferente do atalho do menu")
            return
        self.hotkey_var.set(key)
        self.aim_key_button.configure(text=key)
        self.status_var.set(f"Botao de ativacao: {label}. Clique em Aplicar para salvar.")
        self._update_profile_summary()

    def _on_show_fov_toggle(self):
        self.show_fov_value_var.set("ON" if self.show_fov_var.get() else "OFF")
        self._draw_preview()
        self._update_profile_summary()

    def _on_color_change(self, value):
        self.color_var.set(value)
        self.fov_hex_var.set(COLOR_VALUES[value])
        self._draw_preview()
        self._update_profile_summary()

    def _draw_preview(self):
        canvas = getattr(self, "preview_canvas", None)
        if canvas is None or not canvas.winfo_exists():
            return
        canvas.delete("all")
        width = max(canvas.winfo_width(), 160)
        height = max(canvas.winfo_height(), 120)
        if not self.show_fov_var.get():
            canvas.create_text(width / 2, height / 2, text="CIRCULO DESATIVADO", fill=self.colors["muted"], font=("Segoe UI", 10, "bold"))
            return
        radius = min(width * 0.31, height * 0.38)
        center_x, center_y = width / 2, height / 2
        color = self.fov_hex_var.get()
        if not re.fullmatch(r"#[0-9A-Fa-f]{6}", color):
            color = self.colors["cyan"]
        canvas.create_oval(center_x - radius, center_y - radius, center_x + radius, center_y + radius, outline=color, width=2)
        canvas.create_line(center_x - 9, center_y, center_x + 9, center_y, fill=self.colors["muted"])
        canvas.create_line(center_x, center_y - 9, center_x, center_y + 9, fill=self.colors["muted"])

    def _draw_aim_preview(self):
        canvas = getattr(self, "aim_preview_canvas", None)
        if canvas is None or not canvas.winfo_exists():
            return
        canvas.delete("all")
        width = max(canvas.winfo_width(), 300)
        height = max(canvas.winfo_height(), 190)
        center_x = width * 0.36
        head_y = height * 0.19
        head_radius = min(width * 0.065, height * 0.09)
        shoulder_y = height * 0.34
        waist_y = height * 0.56
        hip_y = height * 0.65
        body_color = "#343A4A"
        body_outline = "#697287"

        canvas.create_oval(
            center_x - head_radius,
            head_y - head_radius,
            center_x + head_radius,
            head_y + head_radius,
            fill=body_color,
            outline=body_outline,
            width=2,
        )
        canvas.create_polygon(
            center_x - width * 0.085, shoulder_y,
            center_x - width * 0.15, shoulder_y + height * 0.07,
            center_x - width * 0.105, waist_y,
            center_x - width * 0.08, hip_y,
            center_x + width * 0.08, hip_y,
            center_x + width * 0.105, waist_y,
            center_x + width * 0.15, shoulder_y + height * 0.07,
            center_x + width * 0.085, shoulder_y,
            fill=body_color,
            outline=body_outline,
            width=2,
        )
        for direction in (-1, 1):
            shoulder_x = center_x + direction * width * 0.12
            elbow_x = center_x + direction * width * 0.205
            hand_x = center_x + direction * width * 0.225
            canvas.create_line(
                shoulder_x, shoulder_y + height * 0.035,
                elbow_x, height * 0.49,
                hand_x, height * 0.59,
                fill=body_color,
                width=12,
                capstyle=tk.ROUND,
                joinstyle=tk.ROUND,
            )
            canvas.create_line(
                center_x + direction * width * 0.045, hip_y,
                center_x + direction * width * 0.075, height * 0.82,
                center_x + direction * width * 0.09, height * 0.95,
                fill=body_color,
                width=14,
                capstyle=tk.ROUND,
                joinstyle=tk.ROUND,
            )

        focus_y = {
            "Cabeca": head_y,
            "Peito": height * 0.43,
            "Barriga": height * 0.55,
        }.get(self.aim_var.get(), height * 0.43)
        for region, marker_y in (
            ("Cabeca", head_y),
            ("Peito", height * 0.43),
            ("Barriga", height * 0.55),
        ):
            selected = region == self.aim_var.get()
            radius = 11 if selected else 7
            marker_color = self.colors["cyan"] if selected else "#9AA2B4"
            canvas.create_oval(
                center_x - radius,
                marker_y - radius,
                center_x + radius,
                marker_y + radius,
                fill=marker_color if selected else self.colors["panel"],
                outline=marker_color,
                width=2,
            )
        callout_x = width * 0.66
        canvas.create_line(center_x + 15, focus_y, callout_x - 8, focus_y, fill=self.colors["cyan"], width=2)
        canvas.create_text(
            callout_x,
            focus_y - 10,
            text="FOCO ATUAL",
            anchor="w",
            fill=self.colors["muted"],
            font=("Segoe UI", 8, "bold"),
        )
        canvas.create_text(
            callout_x,
            focus_y + 9,
            text=self.aim_var.get().upper(),
            anchor="w",
            fill=self.colors["cyan"],
            font=("Segoe UI", 11, "bold"),
        )

    def _update_profile_summary(self):
        if not hasattr(self, "profile_summary"):
            return
        try:
            fov = int(round(float(self.fov_var.get())))
            smoothing = float(self.smoothing_var.get())
            humanizer_speed = int(round(float(self.humanizer_speed_var.get())))
            opacity = int(round(float(self.opacity_var.get())))
        except (tk.TclError, TypeError, ValueError):
            return
        self.profile_summary.set(
            f"FOV             {fov} px\n"
            f"RESPOSTA        {smoothing:.2f}\n"
            f"HUMANIZER       {humanizer_speed} px/s\n"
            f"PONTO           {self.aim_var.get()}\n"
            f"ATIVACAO        {self.hotkey_var.get()}\n"
            f"ATALHO MENU     {self.menu_hotkey_var.get()}\n"
            f"CIRCULO         {'ON' if self.show_fov_var.get() else 'OFF'}\n"
            f"OPACIDADE       {opacity}%\n"
            f"ESP BOX         {'ON' if self.view_vars['esp_enabled'].get() else 'OFF'}\n"
            f"CONFIDENCE      {float(self.view_vars['min_confidence'].get()):.2f}"
        )

    def _begin_key_capture(self, target):
        self._stop_mouse_capture_poll()
        self._capture_target = target
        button = self.aim_key_button if target == "aim" else self.menu_key_button
        button.configure(text="Pressione uma tecla...", fg_color=self.colors["accent"])
        self.status_var.set("Pressione a tecla desejada. Esc cancela a captura.")
        self.window.lift()
        self.window.focus_force()
        self._mouse_capture_after_id = self.window.after(40, self._poll_mouse_capture)

    def _stop_mouse_capture_poll(self):
        after_id = self._mouse_capture_after_id
        self._mouse_capture_after_id = None
        if after_id is not None:
            try:
                self.window.after_cancel(after_id)
            except tk.TclError:
                pass

    def _on_root_destroy(self, event):
        if event.widget is not self.host_root:
            return
        try:
            commands = set(self.host_root._tclCommands or ())
            for after_id in self.host_root.tk.call("after", "info"):
                script = str(self.host_root.tk.call("after", "info", after_id)[0])
                if script in commands:
                    self.host_root.after_cancel(after_id)
        except tk.TclError:
            pass
        self._mouse_capture_after_id = None

    def _poll_mouse_capture(self):
        self._mouse_capture_after_id = None
        if self._capture_target is None:
            return
        for value in MOUSE_HOTKEY_CODES:
            if win32api.GetAsyncKeyState(HOTKEY_CODES[value]) < 0:
                self._assign_hotkey(value)
                break
        if self._capture_target is not None and self.window.winfo_exists():
            self._mouse_capture_after_id = self.window.after(40, self._poll_mouse_capture)

    def _cancel_key_capture(self):
        target = self._capture_target
        self._capture_target = None
        self._stop_mouse_capture_poll()
        if target == "aim":
            self.aim_key_button.configure(text=self.hotkey_var.get(), fg_color=self.colors["field"])
        elif target == "menu":
            self.menu_key_button.configure(text=self.menu_hotkey_var.get(), fg_color=self.colors["field"])
        self.status_var.set("Captura cancelada")

    def _assign_hotkey(self, value):
        target = self._capture_target
        if target is None:
            return
        choices = MENU_HOTKEY_CODES if target == "menu" else HOTKEY_CODES
        if value not in choices:
            self.status_var.set("Essa tecla nao e suportada")
            return "break"
        other_value = self.hotkey_var.get() if target == "menu" else self.menu_hotkey_var.get()
        if value == other_value:
            self.status_var.set("Escolha uma tecla diferente do outro atalho")
            return "break"
        if target == "aim":
            self.hotkey_var.set(value)
            self.aim_key_button.configure(text=value, fg_color=self.colors["field"])
            self.mouse_aim_key_var.set(MOUSE_KEY_LABELS.get(value, "Selecione..."))
        else:
            self.menu_hotkey_var.set(value)
            self.menu_key_button.configure(text=value, fg_color=self.colors["field"])
            self.sidebar_hotkey_label.configure(text=f"ATALHO DO MENU  {value}")
        self._capture_target = None
        self._stop_mouse_capture_poll()
        self.status_var.set(f"Atalho definido: {value}. Clique em Aplicar para salvar.")
        self._update_profile_summary()
        return "break"

    def _on_key_press(self, event):
        if event.keysym == "Escape":
            if self._capture_target is not None:
                self._cancel_key_capture()
            else:
                self.hide()
            return "break"
        if self._capture_target is None:
            return None
        value = KEYSYM_ALIASES.get(event.keysym)
        if value is None and len(event.keysym) == 1 and event.keysym.isalnum():
            value = event.keysym.upper()
        if value is None and event.keysym.startswith("F") and event.keysym[1:].isdigit():
            value = event.keysym
        if value is None:
            self.status_var.set("Use letras, numeros, F1-F12 ou tecla de mouse")
            return "break"
        return self._assign_hotkey(value)

    def _on_mouse_press(self, event):
        if self._capture_target is None:
            return None
        value = MOUSE_BUTTONS.get(event.num)
        if value is None:
            return None
        return self._assign_hotkey(value)

    def show_page(self, page):
        for frame in self.pages.values():
            frame.grid_forget()
        self.pages[page].grid(row=0, column=0, sticky="nsew")
        title, subtitle = self.page_titles[page]
        self.title_var.set(title)
        self.subtitle_var.set(subtitle)
        for name, button in self.page_buttons.items():
            selected = name == page
            button.configure(
                fg_color=self.colors["accent"] if selected else "transparent",
                text_color=self.colors["text"] if selected else self.colors["muted"],
            )
        if page == "profiles":
            self.refresh_profiles()

    @staticmethod
    def _aim_label(value):
        return {value: label for label, value in AIM_LABELS.items()}.get(value, "Peito")

    @staticmethod
    def _color_label(value):
        return {value.lower(): label for label, value in COLOR_VALUES.items()}.get(value.lower(), "Verde")

    def values(self):
        menu_hotkey = self.menu_hotkey_var.get()
        if menu_hotkey not in MENU_HOTKEY_CODES:
            raise ValueError("Selecione uma tecla valida para abrir o menu")
        if menu_hotkey == self.hotkey_var.get():
            raise ValueError("A tecla do menu deve ser diferente da tecla de ativacao")
        values = {
            "fov": max(160, min(640, int(round(float(self.fov_var.get()) / 16) * 16))),
            "smoothing": max(0.05, min(1.0, round(float(self.smoothing_var.get()), 2))),
            "humanizer_speed": max(
                200, min(4000, int(round(float(self.humanizer_speed_var.get()))))
            ),
            "aim_point": AIM_LABELS[self.aim_var.get()],
            "aim_key": self.hotkey_var.get(),
            "menu_key": menu_hotkey,
        }
        for key, variable in self.view_vars.items():
            value = variable.get()
            if key.endswith("_color"):
                if not re.fullmatch(r"#[0-9A-Fa-f]{6}", str(value).strip()):
                    raise ValueError(f"Cor invalida em {key}; use o formato #RRGGBB")
                values[key] = str(value).strip().upper()
            elif isinstance(variable, tk.BooleanVar):
                values[key] = bool(value)
            elif key in ("esp_thickness", "esp_opacity", "snap_line_thickness", "overlay_opacity", "max_detections"):
                values[key] = int(round(float(value)))
            else:
                values[key] = float(value)
        values["overlay_opacity"] = max(10, min(100, values["overlay_opacity"]))
        values["esp_opacity"] = max(0, min(100, values["esp_opacity"]))
        values["esp_thickness"] = max(1, min(8, values["esp_thickness"]))
        values["snap_line_thickness"] = max(1, min(8, values["snap_line_thickness"]))
        values["max_detections"] = max(1, min(100, values["max_detections"]))
        values["min_confidence"] = max(0.0, min(1.0, values["min_confidence"]))
        values["iou_threshold"] = max(0.0, min(1.0, values["iou_threshold"]))
        values["min_distance"] = max(0.0, min(1.0, values["min_distance"] / 100))
        values["max_distance"] = max(values["min_distance"], min(1.0, values["max_distance"] / 100))
        values["min_box_area"] = max(0.0, min(0.25, values["min_box_area"]))
        values["max_box_area"] = max(values["min_box_area"], min(1.0, values["max_box_area"]))
        return values

    def set_values(self, values):
        values = merge_view_settings(values)
        self.fov_var.set(values["fov"])
        self.smoothing_var.set(values["smoothing"])
        self.humanizer_speed_var.set(
            max(200, min(4000, int(round(float(values.get("humanizer_speed", 2000))))))
        )
        self.aim_var.set(self._aim_label(values["aim_point"]))
        self.aim_selector.set(self.aim_var.get())
        aim_key = values.get("aim_key", "Right mouse")
        self.hotkey_var.set(aim_key if aim_key in HOTKEY_CODES else "Right mouse")
        self.aim_key_button.configure(text=self.hotkey_var.get())
        self.mouse_aim_key_var.set(MOUSE_KEY_LABELS.get(self.hotkey_var.get(), "Selecione..."))
        menu_key = values.get("menu_key", "X")
        self.menu_hotkey_var.set(menu_key if menu_key in MENU_HOTKEY_CODES else "X")
        self.menu_key_button.configure(text=self.menu_hotkey_var.get())
        self.sidebar_hotkey_label.configure(text=f"ATALHO DO MENU  {self.menu_hotkey_var.get()}")
        for key, variable in self.view_vars.items():
            value = values.get(key, variable.get())
            if key in ("min_distance", "max_distance"):
                value = float(value) * 100
            variable.set(value)
        self.show_fov_var.set(values["show_fov"])
        self.show_fov_value_var.set("ON" if self.show_fov_var.get() else "OFF")
        self.color_var.set(self._color_label(values["fov_color"]))
        self.opacity_var.set(values["overlay_opacity"])
        self.fov_slider.set(float(self.fov_var.get()))
        self.smoothing_slider.set(float(self.smoothing_var.get()))
        self.humanizer_speed_slider.set(float(self.humanizer_speed_var.get()))
        for key, slider in self.view_sliders.items():
            value = float(self.view_vars[key].get())
            if key in ("min_box_area", "max_box_area"):
                value *= 100
            slider.set(value)
            self.view_labels[key].configure(
                text=self._format_view_value(key, value, self.view_suffixes[key])
            )
        self._update_value_labels()
        self._draw_preview()
        self._update_profile_summary()

    def apply(self):
        try:
            values = self.values()
            self.on_apply(values)
            self.status_var.set("Configuracoes aplicadas e salvas")
        except Exception as exc:
            self.status_var.set(f"Erro: {exc}")

    def _profiles_dir(self):
        directory = Path("profiles")
        directory.mkdir(exist_ok=True)
        return directory

    def refresh_profiles(self):
        names = sorted(path.stem for path in self._profiles_dir().glob("*.json"))
        self.profile_combo.configure(values=names or ["Sem perfis"])
        if names and self.profile_choice_var.get() not in names:
            self.profile_choice_var.set(names[0])
        elif not names:
            self.profile_choice_var.set("Sem perfis")

    def save_profile(self):
        profile_name = re.sub(r"[^A-Za-z0-9_-]+", "_", self.profile_name_var.get()).strip("_")
        if not profile_name:
            self.status_var.set("Informe um nome para o perfil")
            return
        try:
            values = self.values()
            self.on_apply(values)
            path = self._profiles_dir() / f"{profile_name}.json"
            path.write_text(json.dumps(values, indent=2), encoding="utf-8")
            self.profile_choice_var.set(profile_name)
            self.refresh_profiles()
            self.status_var.set(f"Perfil salvo: {profile_name}")
        except Exception as exc:
            self.status_var.set(f"Erro: {exc}")

    def load_profile(self):
        profile_name = self.profile_choice_var.get()
        if not profile_name or profile_name == "Sem perfis":
            self.status_var.set("Selecione um perfil")
            return
        try:
            values = json.loads((self._profiles_dir() / f"{profile_name}.json").read_text(encoding="utf-8"))
            self.set_values(values)
            self.apply()
            self.status_var.set(f"Perfil carregado: {profile_name}")
        except (OSError, ValueError, KeyError, TypeError) as exc:
            self.status_var.set(f"Erro ao carregar perfil: {exc}")

    def toggle(self):
        if self.window.winfo_viewable():
            self.hide()
        else:
            self.show()

    def show(self):
        self.window.deiconify()
        self.window.lift()

    def hide(self):
        if self._capture_target is not None:
            self._cancel_key_capture()
        self.window.withdraw()
