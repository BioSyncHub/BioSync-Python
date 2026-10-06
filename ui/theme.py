"""
MW / Warzone GUI theme — derived from official Times Square key art.

Reference signals:
  - Night asphalt / sky     → near-black cool greys
  - Neon billboards         → muted steel-blue
  - MW geometric logo       → pure white
  - Brush stroke character  → #FFCF00 golden yellow (primary accent)
  - Title font              → MODERN WARFARE.otf
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# ── Surfaces (Times Square night) ─────────────────────────────
BG_DEEP       = "#0A0A0F"      # (10,10,15) deep night
BG_PANEL      = "#1A191E"      # (26,25,30) sidebar / elevated panel
BG_CARD       = "#2E2D33"      # (46-ish) card surface from asphalt greys
BG_CARD_HOVER = "#3C3B42"
BORDER        = "#3E3D44"      # (62,61,66) cold grey edge
BORDER_GLOW   = "#50545C"

# ── Accents from key art ──────────────────────────────────────
GOLD          = "#FFCF00"      # (255,207,0) brush stroke — PRIMARY
GOLD_DIM      = "#C9A300"      # pressed / hover
GOLD_SOFT     = "#FFE566"      # highlight
WHITE_LOGO    = "#FFFFFF"      # MW mark
STEEL_BLUE    = "#303C54"      # (48,60,84) neon sign cool
CYAN_HUD      = "#5B8DEF"      # soft neon blue from boards
GREEN_TACT    = "#2EE60F"      # armed status (kept functional)
RED_ALERT     = "#E63946"

# Legacy aliases so existing app.py keeps working
ORANGE        = GOLD
ORANGE_DIM    = GOLD_DIM
AMBER         = GOLD_SOFT

# ── Typography colors ─────────────────────────────────────────
TEXT_PRIMARY  = "#F2F2F5"      # near-white, high contrast on night bg
TEXT_MUTED    = "#9A9AA3"      # (cold grey from asphalt)
TEXT_DIM      = "#5C5C66"


def _project_root() -> Path:
    if getattr(sys, "frozen", False):
        if hasattr(sys, "_MEIPASS"):
            return Path(sys._MEIPASS).resolve()
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


# ── Font paths / names ────────────────────────────────────────
_ROOT = _project_root()
FONT_MW_PATH  = _ROOT / "assets" / "fonts" / "MODERN WARFARE.otf"
FONT_MW_FAMILY = "MODERN WARFARE"   # internal name from the OTF

# Fallbacks if custom font fails to register
FONT_TITLE    = ("Segoe UI", 20, "bold")
FONT_SECTION  = ("Segoe UI", 13, "bold")
FONT_BODY     = ("Segoe UI", 11)
FONT_SMALL    = ("Segoe UI", 9)
FONT_MONO     = ("Consolas", 10)
FONT_HUD      = ("Segoe UI", 10, "bold")
FONT_BRAND    = (FONT_MW_FAMILY, 18, "bold")  # BioSync | MENU

# CTk base
APPEARANCE    = "dark"
COLOR_THEME   = "dark-blue"

_font_loaded = False


def load_mw_font() -> bool:
    """
    Register MODERN WARFARE.otf so Tk/CTk can resolve family name.
    Windows: AddFontResourceExW
    Linux:   copy is enough if fontconfig picks it up; also try fc-cache path
    Returns True if file exists (best-effort registration).
    """
    global _font_loaded
    if _font_loaded:
        return True
    if not FONT_MW_PATH.is_file():
        print(f"[theme] MW font missing: {FONT_MW_PATH}")
        return False

    path = str(FONT_MW_PATH.resolve())

    if sys.platform == "win32":
        try:
            import ctypes
            FR_PRIVATE = 0x10
            # AddFontResourceExW makes font available to this process only
            ctypes.windll.gdi32.AddFontResourceExW(path, FR_PRIVATE, 0)
            _font_loaded = True
            return True
        except Exception as e:
            print(f"[theme] AddFontResourceExW failed: {e}")

    # Linux / other — process-local via fontconfig is limited;
    # CTk will fall back to default if family not found.
    # Still mark as available so we attempt family name.
    _font_loaded = True
    return True


def brand_font(size: int = 18):
    """CTkFont for title using MODERN WARFARE, with Segoe UI fallback."""
    import customtkinter as ctk
    load_mw_font()
    try:
        return ctk.CTkFont(family=FONT_MW_FAMILY, size=size, weight="bold")
    except Exception:
        return ctk.CTkFont(family="Segoe UI", size=size, weight="bold")
