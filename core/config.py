"""
BioSync Engine Config — persistent JSON + runtime state.
Portado do EngineConfig.cs / config.txt original.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from core.paths import project_root, user_data_root


ROOT = project_root()
DATA_ROOT = user_data_root()
CONFIG_PATH = DATA_ROOT / "config" / "config.json"
PROFILES_PATH = DATA_ROOT / "config" / "profiles.json"


@dataclass
class EngineConfig:
    # Sensitivity pipeline (mirrors C#)
    sens_x: float = 4453.0
    sens_y: float = 7250.0
    filter_x: float = 2.1
    filter_y: float = 2.1
    curve_x: float = 0.7
    curve_y: float = 0.7
    acceleration: float = 0.8
    hardware_gain: float = 4.5
    friction: float = 0.12
    inverse_deadzone: int = 2400

    # Buffed Aim (orbital LS drift)
    buffed_aim_active: bool = False
    buffed_aim_force: float = 12.0

    # Macros / features
    no_recoil_active: bool = False
    no_recoil_force_y: float = 15.0
    no_recoil_force_x: float = 0.0
    recoil_profile: str = "voyak_kt3"
    slide_cancel_active: bool = False
    yy_active: bool = False
    yy_interval_ms: float = 80.0
    auto_ping_active: bool = False
    auto_ping_interval_ms: float = 500.0

    # Virtual key codes (Windows VK) — same defaults as C#
    vk_a: int = 0x20          # Space
    vk_b: int = 0x11          # Ctrl
    vk_y: int = 0x32          # M
    vk_lb: int = 0x51         # Q
    vk_rb: int = 0x45         # E
    vk_ls: int = 0x10         # Shift
    vk_rs: int = 0x56         # V
    vk_toggle: int = 0x2D     # Insert
    vk_slide_cancel: int = 0x43  # C
    vk_yy: int = 0x33         # 3

    def save(self) -> None:
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(asdict(self), f, indent=2)

    @classmethod
    def load(cls) -> "EngineConfig":
        if not CONFIG_PATH.exists():
            cfg = cls()
            bundled_config = ROOT / "config" / "config.json"
            if bundled_config.is_file():
                try:
                    with bundled_config.open("r", encoding="utf-8") as f:
                        data: dict[str, Any] = json.load(f)
                    known = {field.name for field in cls.__dataclass_fields__.values()}
                    cfg = cls(**{key: value for key, value in data.items() if key in known})
                except (OSError, json.JSONDecodeError, TypeError, ValueError):
                    cfg = cls()
            cfg.save()
            return cfg
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                data: dict[str, Any] = json.load(f)
            known = {f.name for f in cls.__dataclass_fields__.values()}  # type: ignore
            filtered = {k: v for k, v in data.items() if k in known}
            return cls(**filtered)
        except Exception:
            return cls()


def load_profiles(path: Path = PROFILES_PATH) -> dict[str, EngineConfig]:
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        raw: Any = json.load(f)
    if not isinstance(raw, dict):
        raise ValueError("O arquivo de perfis deve conter um objeto JSON.")

    known = {field.name for field in EngineConfig.__dataclass_fields__.values()}
    profiles: dict[str, EngineConfig] = {}
    for name, values in raw.items():
        if not isinstance(name, str) or not name.strip() or not isinstance(values, dict):
            raise ValueError("O arquivo contém um perfil inválido.")
        profiles[name] = EngineConfig(**{key: value for key, value in values.items() if key in known})
    return profiles


def save_profile(name: str, config: EngineConfig, path: Path = PROFILES_PATH) -> None:
    profile_name = name.strip()
    if not profile_name:
        raise ValueError("Informe um nome para o perfil.")

    profiles = load_profiles(path)
    profiles[profile_name] = config
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({key: asdict(value) for key, value in profiles.items()}, f, indent=2)
