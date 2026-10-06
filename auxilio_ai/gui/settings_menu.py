import json
import re
import tkinter as tk
from pathlib import Path
from tkinter import ttk

from gui.view_settings import merge_view_settings


HOTKEY_CODES = {
    "Left mouse": 0x01,
    "Right mouse": 0x02,
    "Middle mouse": 0x04,
    "Mouse 4": 0x05,
    "Mouse 5": 0x06,
    "Shift": 0x10,
    "Ctrl": 0x11,
    "Alt": 0x12,
}
KEYBOARD_HOTKEY_CODES = {
    **{chr(code): code for code in range(ord("A"), ord("Z") + 1)},
    **{str(number): ord(str(number)) for number in range(10)},
    **{f"F{number}": 0x70 + number - 1 for number in range(1, 13)},
    "Space": 0x20,
    "Tab": 0x09,
    "Enter": 0x0D,
    "Backspace": 0x08,
    "Caps Lock": 0x14,
    "Insert": 0x2D,
    "Delete": 0x2E,
    "Home": 0x24,
    "End": 0x23,
    "Page Up": 0x21,
    "Page Down": 0x22,
}
HOTKEY_CODES.update(KEYBOARD_HOTKEY_CODES)
MOUSE_HOTKEY_CODES = {
    key: HOTKEY_CODES[key]
    for key in ("Left mouse", "Middle mouse", "Right mouse", "Mouse 4", "Mouse 5")
}
MENU_HOTKEY_CODES = {
    **KEYBOARD_HOTKEY_CODES,
    **MOUSE_HOTKEY_CODES,
}

AIM_LABELS = {"Cabeca": "head", "Peito": "chest", "Barriga": "belly"}
COLOR_VALUES = {
    "Verde": "#32D7A0",
    "Ciano": "#32C7D7",
    "Amarelo": "#F2C94C",
    "Vermelho": "#F06464",
    "Branco": "#E8EEF2",
}


class SettingsMenu:
    def __init__(self, root, settings, on_apply):
        self.on_apply = on_apply
        self.window = tk.Toplevel(root)
        self.window.title("BS | HUB - BioSync AI")
        self.window.geometry("820x590+42+42")
        self.window.minsize(760, 540)
        self.window.resizable(True, True)
        self.window.attributes("-topmost", True)
        self.window.configure(bg="#12141D")
        self.window.protocol("WM_DELETE_WINDOW", self.hide)
        self.window.bind("<Escape>", lambda _event: self.hide())

        self.colors = {
            "window": "#12141D",
            "sidebar": "#0C0D12",
            "panel": "#181A26",
            "field": "#222431",
            "line": "#2B2D3B",
            "text": "#E1E1E6",
            "muted": "#777B8F",
            "accent": "#8A2BE2",
            "accent_hover": "#7022B8",
            "cyan": "#00D9EE",
            "success": "#00E566",
        }
        style = ttk.Style(self.window)
        style.theme_use("clam")
        style.configure("TFrame", background=self.colors["window"])
        style.configure("Sidebar.TFrame", background=self.colors["sidebar"])
        style.configure("Panel.TFrame", background=self.colors["panel"])
        style.configure("TLabel", background=self.colors["window"], foreground=self.colors["text"], font=("Segoe UI", 10))
        style.configure("Sidebar.TLabel", background=self.colors["sidebar"], foreground=self.colors["text"])
        style.configure("Muted.TLabel", foreground=self.colors["muted"], font=("Segoe UI", 9))
        style.configure("Title.TLabel", font=("Bahnschrift SemiBold", 20), foreground=self.colors["cyan"])
        style.configure("Section.TLabel", background=self.colors["panel"], font=("Segoe UI Semibold", 10), foreground=self.colors["cyan"])
        style.configure("PanelTitle.TLabel", background=self.colors["panel"], font=("Segoe UI Semibold", 12), foreground=self.colors["text"])
        style.configure("TCheckbutton", background=self.colors["panel"], foreground=self.colors["text"], font=("Segoe UI", 10))
        style.map("TCheckbutton", background=[("active", self.colors["panel"])], foreground=[("active", "#FFFFFF")])
        style.configure("TButton", padding=(11, 8), font=("Segoe UI Semibold", 9), background=self.colors["field"], foreground=self.colors["text"], borderwidth=0)
        style.map("TButton", background=[("active", "#303E4F")])
        style.configure("Nav.TButton", padding=(13, 11), anchor="w", background=self.colors["sidebar"], foreground=self.colors["muted"])
        style.map("Nav.TButton", background=[("active", "#202A37"), ("selected", self.colors["accent"])], foreground=[("active", self.colors["text"]), ("selected", "#FFFFFF")])
        style.configure("Accent.TButton", background=self.colors["accent"], foreground="#FFFFFF", padding=(15, 9))
        style.map("Accent.TButton", background=[("active", self.colors["accent_hover"])])
        style.configure("TCombobox", padding=6, fieldbackground=self.colors["field"], background=self.colors["field"], foreground=self.colors["text"], arrowcolor=self.colors["text"])
        style.map("TCombobox", fieldbackground=[("readonly", self.colors["field"])], foreground=[("readonly", self.colors["text"])])
        style.configure("TSpinbox", padding=5, fieldbackground=self.colors["field"], background=self.colors["field"], foreground=self.colors["text"], arrowcolor=self.colors["text"])
        style.configure("Horizontal.TScale", background=self.colors["panel"], troughcolor=self.colors["field"], sliderthickness=15)

        self.fov_var = tk.IntVar(value=settings["fov"])
        self.smoothing_var = tk.DoubleVar(value=settings["smoothing"])
        self.aim_var = tk.StringVar(value=self._aim_label(settings["aim_point"]))
        self.hotkey_var = tk.StringVar(value=settings["aim_key"])
        self.menu_hotkey_var = tk.StringVar(value=settings.get("menu_key", "X"))
        self.menu_hotkey_label_var = tk.StringVar(value=f"MENU HOTKEY     {self.menu_hotkey_var.get()}")
        self.menu_hotkey_var.trace_add("write", self._update_menu_hotkey_label)
        self.show_fov_var = tk.BooleanVar(value=settings["show_fov"])
        self.color_var = tk.StringVar(value=self._color_label(settings["fov_color"]))
        self.fov_hex_var = tk.StringVar(value=settings["fov_color"])
        self.opacity_var = tk.IntVar(value=settings["overlay_opacity"])
        self.view_values = merge_view_settings(settings)
        self.view_vars = {}
        self.view_sliders = {}
        for key, value in self.view_values.items():
            variable_type = tk.BooleanVar if isinstance(value, bool) else (
                tk.StringVar if isinstance(value, str) else tk.DoubleVar
            )
            self.view_vars[key] = variable_type(value=value)
        self.view_vars["show_fov"] = self.show_fov_var
        self.view_vars["overlay_opacity"] = self.opacity_var
        self.view_vars["fov_color"] = self.fov_hex_var
        self.profile_name_var = tk.StringVar(value="default")
        self.profile_choice_var = tk.StringVar()
        self.status_var = tk.StringVar(value="Pronto")

        shell = ttk.Frame(self.window)
        shell.pack(fill="both", expand=True)
        sidebar = ttk.Frame(shell, style="Sidebar.TFrame", width=174, padding=(14, 18))
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)

        brand = ttk.Frame(sidebar, style="Sidebar.TFrame")
        brand.pack(fill="x", pady=(0, 25))
        brand_text = ttk.Frame(brand, style="Sidebar.TFrame")
        brand_text.pack(side="left")
        tk.Label(brand_text, text="BS | HUB", bg=self.colors["sidebar"], fg=self.colors["cyan"], font=("Bahnschrift SemiBold", 19)).pack(anchor="w")
        tk.Label(brand_text, text="BioSync | AI", bg=self.colors["sidebar"], fg=self.colors["muted"], font=("Segoe UI", 9, "bold")).pack(anchor="w")
        tk.Frame(sidebar, bg=self.colors["line"], height=1).pack(fill="x", pady=(0, 15))

        self.page_titles = {
            "aim": ("Targeting", "Acquisition and response"),
            "views": ("Views", "ESP, detections and indicators"),
            "profiles": ("Profiles", "Saved configurations"),
        }
        self.page_buttons = {}
        for page, label in (("aim", "01   CONFIG"), ("views", "02   VIEWS"), ("profiles", "03   PROFILES")):
            button = ttk.Button(sidebar, text=label, style="Nav.TButton", command=lambda selected=page: self.show_page(selected))
            button.pack(fill="x", pady=3)
            self.page_buttons[page] = button

        sidebar_footer = ttk.Frame(sidebar, style="Sidebar.TFrame")
        sidebar_footer.pack(side="bottom", fill="x")
        status_card = tk.Frame(sidebar_footer, bg=self.colors["panel"], padx=10, pady=8)
        status_card.pack(fill="x", pady=(0, 12))
        tk.Label(status_card, text="●", bg=self.colors["panel"], fg=self.colors["success"], font=("Segoe UI", 12)).pack(side="left", padx=(0, 7))
        tk.Label(status_card, text="ENGINE READY", bg=self.colors["panel"], fg=self.colors["text"], font=("Segoe UI Semibold", 9)).pack(side="left")
        tk.Frame(sidebar_footer, bg=self.colors["line"], height=1).pack(fill="x", pady=(0, 11))
        ttk.Label(sidebar_footer, textvariable=self.menu_hotkey_label_var, style="Sidebar.TLabel", font=("Segoe UI", 8)).pack(anchor="w")

        main = ttk.Frame(shell, padding=(25, 19, 25, 17))
        main.pack(side="left", fill="both", expand=True)
        header = ttk.Frame(main)
        header.pack(fill="x", pady=(0, 17))
        title_block = ttk.Frame(header)
        title_block.pack(side="left", fill="x", expand=True)
        self.title_var = tk.StringVar()
        self.subtitle_var = tk.StringVar()
        ttk.Label(title_block, textvariable=self.title_var, style="Title.TLabel").pack(anchor="w")
        ttk.Label(title_block, textvariable=self.subtitle_var, style="Muted.TLabel").pack(anchor="w", pady=(2, 0))
        ttk.Button(header, text="Hide", command=self.hide).pack(side="right", anchor="n")
        tk.Frame(main, bg=self.colors["line"], height=1).pack(fill="x", pady=(0, 15))

        self.page_host = ttk.Frame(main)
        self.page_host.pack(fill="both", expand=True)
        self.pages = {}
        self._build_aim_page()
        self._build_views_page()
        self._build_profiles_page()

        footer = ttk.Frame(main)
        footer.pack(fill="x", pady=(15, 0))
        self.status_label = tk.Label(footer, textvariable=self.status_var, bg=self.colors["window"], fg=self.colors["muted"], font=("Segoe UI", 9))
        self.status_label.pack(side="left")
        ttk.Button(footer, text="Save profile", command=self.save_profile).pack(side="right", padx=(8, 0))
        ttk.Button(footer, text="Apply", style="Accent.TButton", command=self.apply).pack(side="right")

        self.refresh_profiles()
        self.show_page("aim")

    def _make_panel(self, parent, title, description=None):
        panel = ttk.Frame(parent, style="Panel.TFrame", padding=(17, 15))
        ttk.Label(panel, text=title, style="PanelTitle.TLabel").pack(anchor="w")
        if description:
            ttk.Label(panel, text=description, style="Muted.TLabel").pack(anchor="w", pady=(3, 12))
        else:
            ttk.Label(panel, text=" ", style="Muted.TLabel").pack(anchor="w", pady=(3, 5))
        return panel

    def _labeled_control(self, parent, label, widget, detail=None):
        row = ttk.Frame(parent, style="Panel.TFrame")
        row.pack(fill="x", pady=7)
        text = ttk.Frame(row, style="Panel.TFrame")
        text.pack(side="left", fill="x", expand=True)
        ttk.Label(text, text=label, background=self.colors["panel"]).pack(anchor="w")
        if detail:
            ttk.Label(text, text=detail, style="Muted.TLabel", background=self.colors["panel"]).pack(anchor="w", pady=(2, 0))
        widget.pack(side="right")

    def _build_aim_page(self):
        page = ttk.Frame(self.page_host)
        self.pages["aim"] = page
        columns = ttk.Frame(page)
        columns.pack(fill="both", expand=True)
        acquisition = self._make_panel(columns, "Acquisition", "Detection region and target point")
        acquisition.pack(side="left", fill="both", expand=True, padx=(0, 7))
        response = self._make_panel(columns, "Response", "Input behavior while the trigger is held")
        response.pack(side="left", fill="both", expand=True, padx=(7, 0))

        fov = ttk.Spinbox(acquisition, from_=160, to=640, increment=16, textvariable=self.fov_var, width=9, justify="center")
        self._labeled_control(acquisition, "Detection FOV", fov, "Square capture around screen center")
        aim = ttk.Combobox(acquisition, textvariable=self.aim_var, values=tuple(AIM_LABELS), state="readonly", width=12)
        self._labeled_control(acquisition, "Aim point", aim)

        hotkey = ttk.Combobox(response, textvariable=self.hotkey_var, values=tuple(HOTKEY_CODES), state="readonly", width=13)
        self._labeled_control(response, "Activation key", hotkey, "Hold to engage target tracking")
        menu_hotkey = ttk.Combobox(response, textvariable=self.menu_hotkey_var, values=tuple(MENU_HOTKEY_CODES), state="readonly", width=13)
        self._labeled_control(response, "Menu toggle key", menu_hotkey, "Press to show or hide this menu")
        smoothing = ttk.Spinbox(response, from_=0.05, to=1.0, increment=0.05, textvariable=self.smoothing_var, width=9, format="%.2f", justify="center")
        self._labeled_control(response, "Smoothing", smoothing, "Lower values move faster")
        ttk.Label(response, text="CONTROL STATE", style="Section.TLabel").pack(anchor="w", pady=(20, 5))
        tk.Label(response, text="READY   /   PROFILE ACTIVE", bg=self.colors["field"], fg=self.colors["cyan"], font=("Segoe UI Semibold", 9), padx=10, pady=9, anchor="w").pack(fill="x")

    def _build_views_page(self):
        page = ttk.Frame(self.page_host)
        self.pages["views"] = page
        canvas = tk.Canvas(page, bg=self.colors["window"], highlightthickness=0)
        scrollbar = ttk.Scrollbar(page, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        content = ttk.Frame(canvas)
        content_window = canvas.create_window((0, 0), window=content, anchor="nw")
        content.bind("<Configure>", lambda _event: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda event: canvas.itemconfigure(content_window, width=event.width))

        cards = (
            ("ESP Box", "Box style, thickness and color", (
                ("switch", "esp_enabled", "Enable boxes"),
                ("option", "esp_style", "Style", ["Normal", "Filled", "Corner"]),
                ("slider", "esp_thickness", "Line thickness", 1, 8),
                ("entry", "esp_color", "Custom color HEX"),
                ("slider", "esp_opacity", "Box opacity", 0, 100),
            )),
            ("Distance (near / far)", "Box area is used as a distance proxy", (
                ("switch", "distance_filter", "Filter by distance"),
                ("slider", "min_distance", "Minimum distance (near)", 0, 100),
                ("slider", "max_distance", "Maximum distance (far)", 0, 100),
            )),
            ("False-positive filter", "Confidence, IOU and box area", (
                ("slider", "min_confidence", "Minimum confidence", 0, 1),
                ("slider", "iou_threshold", "IOU", 0, 1),
                ("slider", "max_detections", "Max detections", 1, 100),
                ("switch", "ignore_small_targets", "Ignore very small targets"),
                ("slider", "min_box_area", "Minimum box area (%)", 0, 25),
                ("switch", "ignore_large_targets", "Ignore very large targets"),
                ("slider", "max_box_area", "Maximum box area (%)", 0, 100),
            )),
            ("Lines and indicators", "Selected-target display", (
                ("switch", "snap_line", "Crosshair snap line"),
                ("entry", "snap_line_color", "Line color HEX"),
                ("slider", "snap_line_thickness", "Line thickness", 1, 8),
                ("switch", "show_aim_marker", "Show aim point"),
                ("entry", "marker_color", "Marker color HEX"),
            )),
            ("Skeleton / body zones", "Color-coded head, chest and belly guides", (
                ("switch", "show_body_zones", "Draw body zones"),
                ("entry", "head_color", "Head color HEX"),
                ("entry", "chest_color", "Chest color HEX"),
                ("entry", "belly_color", "Belly color HEX"),
            )),
            ("FOV visual", "Field-of-view guide circle", (
                ("switch", "show_fov", "Show FOV circle"),
                ("entry", "fov_color", "Circle color HEX"),
                ("slider", "overlay_opacity", "Overlay opacity (%)", 10, 100),
            )),
        )
        for title, description, controls in cards:
            card = self._make_panel(content, title, description)
            card.pack(fill="x", pady=6)
            for control in controls:
                self._add_view_control(card, control)

    def _add_view_control(self, card, control):
        kind, key, label, *options = control
        if kind == "switch":
            widget = ttk.Checkbutton(card, text=label, variable=self.view_vars[key])
            widget.pack(anchor="w", pady=5)
            return
        if kind == "entry":
            if key.endswith("_color"):
                controls = ttk.Frame(card, style="Panel.TFrame")
                preset_var = tk.StringVar(value=self._color_label(self.view_vars[key].get()))
                preset = ttk.Combobox(
                    controls, textvariable=preset_var, values=tuple(COLOR_VALUES),
                    state="readonly", width=10,
                )
                preset.pack(side="left", padx=(0, 5))
                preset.bind(
                    "<<ComboboxSelected>>",
                    lambda _event, selected=preset_var, target=self.view_vars[key]:
                    target.set(COLOR_VALUES[selected.get()]),
                )
                entry = ttk.Entry(controls, textvariable=self.view_vars[key], width=10)
                entry.pack(side="left")
                self._labeled_control(card, label, controls)
            else:
                entry = ttk.Entry(card, textvariable=self.view_vars[key], width=13)
                self._labeled_control(card, label, entry)
            return
        if kind == "option":
            widget = ttk.Combobox(
                card, textvariable=self.view_vars[key], values=options[0],
                state="readonly", width=12,
            )
            self._labeled_control(card, label, widget)
            return

        lower, upper = options
        variable = self.view_vars[key]
        initial = float(variable.get())
        if key in ("min_distance", "max_distance"):
            initial *= 100
        elif key in ("min_box_area", "max_box_area"):
            initial *= 100
        slider_var = tk.DoubleVar(value=initial)
        row = ttk.Frame(card, style="Panel.TFrame")
        row.pack(fill="x", pady=4)
        ttk.Label(row, text=label, background=self.colors["panel"]).pack(anchor="w")
        scale = ttk.Scale(
            row, from_=lower, to=upper, variable=slider_var, orient="horizontal",
            command=lambda value, k=key: self._on_view_scale(k, value),
        )
        self.view_sliders[key] = slider_var
        scale.pack(fill="x", pady=(2, 0))

    def _on_view_scale(self, key, value):
        if key in ("min_distance", "max_distance", "min_box_area", "max_box_area"):
            self.view_vars[key].set(float(value) / 100)
        else:
            self.view_vars[key].set(float(value))
        if key == "overlay_opacity":
            self.opacity_var.set(int(float(value)))

    def _build_profiles_page(self):
        page = ttk.Frame(self.page_host)
        self.pages["profiles"] = page
        columns = ttk.Frame(page)
        columns.pack(fill="both", expand=True)
        saved = self._make_panel(columns, "Profile library", "Save and load local configuration sets")
        saved.pack(side="left", fill="both", expand=True, padx=(0, 7))
        current = self._make_panel(columns, "Current setup", "Values applied to this session")
        current.pack(side="left", fill="both", expand=True, padx=(7, 0))

        ttk.Label(saved, text="Profile name", background=self.colors["panel"]).pack(anchor="w", pady=(8, 3))
        ttk.Entry(saved, textvariable=self.profile_name_var).pack(fill="x", ipady=5)
        ttk.Label(saved, text="Available profiles", background=self.colors["panel"]).pack(anchor="w", pady=(16, 3))
        self.profile_combo = ttk.Combobox(saved, textvariable=self.profile_choice_var, state="readonly")
        self.profile_combo.pack(fill="x", ipady=3)
        ttk.Button(saved, text="Load selected", command=self.load_profile).pack(anchor="e", pady=(12, 0))

        self.profile_summary = tk.StringVar()
        ttk.Label(current, textvariable=self.profile_summary, style="Muted.TLabel", background=self.colors["panel"], justify="left").pack(anchor="w", pady=(8, 0))
        for variable in (self.fov_var, self.smoothing_var, self.aim_var, self.hotkey_var, self.menu_hotkey_var, self.show_fov_var, self.color_var, self.opacity_var):
            variable.trace_add("write", lambda *_args: self._update_profile_summary())
        for variable in self.view_vars.values():
            variable.trace_add("write", lambda *_args: self._update_profile_summary())
        self._update_profile_summary()

    def _draw_preview(self):
        canvas = getattr(self, "preview_canvas", None)
        if canvas is None or not canvas.winfo_exists():
            return
        canvas.delete("all")
        if not self.show_fov_var.get():
            canvas.create_text(120, 90, text="FOV CIRCLE HIDDEN", fill=self.colors["muted"], font=("Segoe UI Semibold", 9))
            return
        width = max(canvas.winfo_width(), 160)
        height = max(canvas.winfo_height(), 100)
        radius = min(width * 0.31, height * 0.39)
        cx, cy = width / 2, height / 2
        color = COLOR_VALUES.get(self.color_var.get(), self.colors["accent"])
        canvas.create_oval(cx - radius, cy - radius, cx + radius, cy + radius, outline=color, width=2)
        canvas.create_line(cx - 9, cy, cx + 9, cy, fill=self.colors["muted"])
        canvas.create_line(cx, cy - 9, cx, cy + 9, fill=self.colors["muted"])

    def _update_profile_summary(self):
        if not hasattr(self, "profile_summary"):
            return
        try:
            fov = int(self.fov_var.get())
            smoothing = float(self.smoothing_var.get())
            opacity = int(float(self.opacity_var.get()))
        except (tk.TclError, TypeError, ValueError):
            return
        self.profile_summary.set(
            f"FOV       {fov} px\n"
            f"SMOOTHING {smoothing:.2f}\n"
            f"AIM POINT {self.aim_var.get()}\n"
            f"HOTKEY    {self.hotkey_var.get()}\n"
            f"MENU KEY  {self.menu_hotkey_var.get()}\n"
            f"FOV CIRCLE {'ON' if self.show_fov_var.get() else 'OFF'}\n"
            f"OPACITY   {opacity}%\n"
            f"ESP BOX   {'ON' if self.view_vars['esp_enabled'].get() else 'OFF'}\n"
            f"CONF      {float(self.view_vars['min_confidence'].get()):.2f}"
        )

    def show_page(self, page):
        for frame in self.pages.values():
            frame.pack_forget()
        self.pages[page].pack(fill="both", expand=True)
        title, subtitle = self.page_titles[page]
        self.title_var.set(title)
        self.subtitle_var.set(subtitle)
        for name, button in self.page_buttons.items():
            button.state(["selected"] if name == page else ["!selected"])
        if page == "profiles":
            self.refresh_profiles()

    @staticmethod
    def _section(parent, text, pady=(0, 7)):
        ttk.Label(parent, text=text, style="Section.TLabel").pack(anchor="w", pady=pady)

    @staticmethod
    def _row(parent, label, widget):
        row = ttk.Frame(parent)
        row.pack(fill="x", pady=4)
        ttk.Label(row, text=label).pack(side="left", fill="x", expand=True)
        widget.pack(side="right")

    @staticmethod
    def _aim_label(value):
        return {value: label for label, value in AIM_LABELS.items()}.get(value, "Peito")

    @staticmethod
    def _color_label(value):
        return {value.lower(): label for label, value in COLOR_VALUES.items()}.get(value.lower(), "Verde")

    def _update_menu_hotkey_label(self, *_args):
        self.menu_hotkey_label_var.set(f"MENU HOTKEY     {self.menu_hotkey_var.get()}")

    def values(self):
        menu_hotkey = self.menu_hotkey_var.get()
        if menu_hotkey not in MENU_HOTKEY_CODES:
            raise ValueError("Selecione uma tecla válida para abrir o menu")
        if menu_hotkey == self.hotkey_var.get():
            raise ValueError("A tecla do menu deve ser diferente da tecla de ativação")
        values = {
            "fov": max(160, min(640, int(self.fov_var.get()))),
            "smoothing": max(0.05, min(1.0, float(self.smoothing_var.get()))),
            "aim_point": AIM_LABELS[self.aim_var.get()],
            "aim_key": self.hotkey_var.get(),
            "menu_key": menu_hotkey,
        }
        for key, variable in self.view_vars.items():
            value = variable.get()
            if key.endswith("_color"):
                if not re.fullmatch(r"#[0-9A-Fa-f]{6}", str(value).strip()):
                    raise ValueError(f"Invalid color for {key}; use #RRGGBB")
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
        values["min_distance"] = max(0.0, min(1.0, values["min_distance"]))
        values["max_distance"] = max(values["min_distance"], min(1.0, values["max_distance"]))
        values["min_box_area"] = max(0.0, min(0.25, values["min_box_area"]))
        values["max_box_area"] = max(values["min_box_area"], min(1.0, values["max_box_area"]))
        return values

    def set_values(self, values):
        values = merge_view_settings(values)
        self.fov_var.set(values["fov"])
        self.smoothing_var.set(values["smoothing"])
        self.aim_var.set(self._aim_label(values["aim_point"]))
        self.hotkey_var.set(values["aim_key"])
        self.menu_hotkey_var.set(values.get("menu_key", "X"))
        for key, variable in self.view_vars.items():
            variable.set(values.get(key, variable.get()))
        self.show_fov_var.set(values["show_fov"])
        self.fov_hex_var.set(values["fov_color"])
        self.color_var.set(self._color_label(values["fov_color"]))
        self.opacity_var.set(values["overlay_opacity"])
        for key, slider_var in self.view_sliders.items():
            value = float(self.view_vars[key].get())
            if key in ("min_distance", "max_distance", "min_box_area", "max_box_area"):
                value *= 100
            slider_var.set(value)

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
        directory = self._profiles_dir()
        names = sorted(path.stem for path in directory.glob("*.json"))
        self.profile_combo["values"] = names
        if names and self.profile_choice_var.get() not in names:
            self.profile_choice_var.set(names[0])

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
        if not profile_name:
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
        self.window.withdraw()
