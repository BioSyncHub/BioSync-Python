from __future__ import annotations

import os
import sys
from pathlib import Path


def project_root() -> Path:
    if getattr(sys, "frozen", False):
        bundle_root = getattr(sys, "_MEIPASS", None)
        if bundle_root:
            return Path(bundle_root).resolve()
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def user_data_root() -> Path:
    if not getattr(sys, "frozen", False):
        return project_root()
    local_app_data = os.environ.get("LOCALAPPDATA")
    base = Path(local_app_data) if local_app_data else Path.home() / "AppData" / "Local"
    return base / "BioSync"


def auxilio_ai_environment_root() -> Path:
    default_root = user_data_root() / ".venv-auxilio-ai"
    if not getattr(sys, "frozen", False):
        return default_root

    executable = Path(sys.executable).resolve()
    if len(executable.parents) > 2:
        adjacent_root = executable.parents[2] / ".venv-auxilio-ai"
        if (adjacent_root / "Scripts" / "python.exe").is_file():
            return adjacent_root
    return default_root
