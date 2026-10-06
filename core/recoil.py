"""Time-indexed recoil compensation for BioSync No Recoil.

Patterns are authored from mag-dump footage as stick-space keypoints:
  x > 0 → look right (counter left recoil)
  y > 0 → look down (counter upward recoil)

Values are normalized (x in [-1, 1], y in [0, 1]) and scaled by the
user's no_recoil_force sliders every engine tick.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Sequence

PROFILES_PATH = Path(__file__).resolve().parent.parent / "config" / "recoil_profiles.json"

# Fallback if the JSON is missing — VOYAK KT-3 from the wall-spray video.
_VOYAK_KT3_KEYPOINTS: tuple[tuple[float, float, float], ...] = (
    (0, 0.00, 0.00),
    (18, 0.02, 0.58),
    (46, 0.01, 0.72),
    (92, 0.00, 0.80),
    (184, 0.02, 0.86),
    (276, 0.00, 0.90),
    (368, -0.03, 0.92),
    (460, -0.05, 0.93),
    (552, -0.08, 0.94),
    (644, -0.16, 0.95),
    (736, -0.28, 0.95),
    (828, -0.42, 0.94),
    (920, -0.56, 0.93),
    (1012, -0.68, 0.91),
    (1104, -0.78, 0.89),
    (1196, -0.86, 0.87),
    (1288, -0.91, 0.85),
    (1380, -0.94, 0.83),
    (1472, -0.96, 0.81),
    (1564, -0.97, 0.79),
    (1656, -0.94, 0.77),
    (1748, -0.90, 0.75),
    (1840, -0.84, 0.73),
    (1932, -0.76, 0.71),
    (2024, -0.66, 0.68),
    (2116, -0.54, 0.66),
    (2208, -0.42, 0.63),
    (2300, -0.28, 0.60),
    (2392, -0.12, 0.56),
    (2484, 0.04, 0.52),
    (2576, 0.16, 0.49),
    (2668, 0.22, 0.46),
    (2760, 0.10, 0.44),
    (2852, -0.10, 0.42),
    (2944, 0.14, 0.40),
    (3036, 0.18, 0.38),
    (3128, -0.12, 0.36),
    (3220, 0.08, 0.34),
    (3312, 0.12, 0.32),
    (3404, -0.08, 0.30),
    (3496, 0.04, 0.28),
    (3588, 0.00, 0.26),
    (3800, 0.00, 0.22),
)


@dataclass(frozen=True)
class RecoilProfile:
    id: str
    name: str
    rpm: float
    mag: int
    horizontal_scale: float
    keypoints: tuple[tuple[float, float, float], ...]  # (t_ms, x, y)

    @property
    def label(self) -> str:
        if self.rpm > 0:
            return f"{self.name}  ·  {int(self.rpm)} RPM"
        return self.name


def _builtin_profiles() -> dict[str, RecoilProfile]:
    return {
        "constant": RecoilProfile(
            id="constant",
            name="Constante",
            rpm=0,
            mag=0,
            horizontal_scale=0.0,
            keypoints=((0.0, 0.0, 1.0),),
        ),
        "voyak_kt3": RecoilProfile(
            id="voyak_kt3",
            name="VOYAK KT-3",
            rpm=652,
            mag=40,
            horizontal_scale=0.72,
            keypoints=_VOYAK_KT3_KEYPOINTS,
        ),
    }


@lru_cache(maxsize=1)
def load_recoil_profiles(path: Path | None = None) -> dict[str, RecoilProfile]:
    profiles = _builtin_profiles()
    target = path or PROFILES_PATH
    if not target.exists():
        return profiles
    try:
        raw = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return profiles
    if not isinstance(raw, dict):
        return profiles
    for key, value in raw.items():
        if not isinstance(value, dict):
            continue
        points = value.get("keypoints") or []
        parsed: list[tuple[float, float, float]] = []
        for item in points:
            if isinstance(item, (list, tuple)) and len(item) >= 3:
                parsed.append((float(item[0]), float(item[1]), float(item[2])))
        if not parsed:
            continue
        parsed.sort(key=lambda p: p[0])
        profiles[str(key)] = RecoilProfile(
            id=str(value.get("id") or key),
            name=str(value.get("name") or key),
            rpm=float(value.get("rpm") or 0),
            mag=int(value.get("mag") or 0),
            horizontal_scale=float(value.get("horizontal_scale") or 0.72),
            keypoints=tuple(parsed),
        )
    return profiles


def get_profile(profile_id: str | None) -> RecoilProfile:
    profiles = load_recoil_profiles()
    if profile_id and profile_id in profiles:
        return profiles[profile_id]
    return profiles["constant"]


def interpolate_pattern(
    keypoints: Sequence[tuple[float, float, float]], elapsed_ms: float
) -> tuple[float, float]:
    """Return normalized (x, y) at elapsed_ms. Holds the last point past the end."""
    if not keypoints:
        return 0.0, 1.0
    if elapsed_ms <= keypoints[0][0]:
        return keypoints[0][1], keypoints[0][2]
    if elapsed_ms >= keypoints[-1][0]:
        return keypoints[-1][1], keypoints[-1][2]
    for i in range(1, len(keypoints)):
        t1, x1, y1 = keypoints[i]
        if elapsed_ms <= t1:
            t0, x0, y0 = keypoints[i - 1]
            span = t1 - t0
            if span <= 1e-9:
                return x1, y1
            u = (elapsed_ms - t0) / span
            return x0 + (x1 - x0) * u, y0 + (y1 - y0) * u
    return keypoints[-1][1], keypoints[-1][2]


def sample_recoil(
    profile_id: str | None,
    elapsed_ms: float,
    force_x: float,
    force_y: float,
) -> tuple[float, float]:
    """Stick-space compensation: (+x look right, +y look down). Clamped ±5000."""
    profile = get_profile(profile_id)
    nx, ny = interpolate_pattern(profile.keypoints, max(0.0, elapsed_ms))
    scale_y = max(-5000.0, min(5000.0, force_y))
    scale_x = abs(scale_y) * profile.horizontal_scale
    trim_x = max(-5000.0, min(5000.0, force_x))
    recoil_x = max(-5000.0, min(5000.0, nx * scale_x + trim_x))
    recoil_y = max(-5000.0, min(5000.0, ny * scale_y))
    return recoil_x, recoil_y
