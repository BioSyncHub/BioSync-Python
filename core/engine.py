"""
BioSync Input Engine — Python port of the C# math pipeline.

Target: ~500-1000 Hz soft loop (relaxed latency vs C# GC-free path).
Uses vgamepad (ViGEm on Windows / uinput on Linux).
"""
from __future__ import annotations

import math
import logging
import threading
import time
from typing import Optional

try:
    import vgamepad as vg
    vg_import_error: Optional[str] = None
except Exception as exc:
    # Linux sem libevdev / Windows sem ViGEmBus → dry-run
    vg = None  # type: ignore
    vg_import_error = f"{type(exc).__name__}: {exc}"

from core.config import EngineConfig
from core.recoil import sample_recoil

logger = logging.getLogger(__name__)


class InputEngine:
    """
    Hot path:
      InjectRawMouseDelta → accumulate
      ClockLoop @ ~1 kHz → ProcessInputFrame → vgamepad.Xbox360 report
    """

    def __init__(self, config: Optional[EngineConfig] = None):
        self.cfg = config or EngineConfig()
        self._lock = threading.Lock()
        self._active = False
        self._thread: Optional[threading.Thread] = None

        # Accumulated raw deltas
        self._raw_x = 0
        self._raw_y = 0

        # Filtered state
        self._target_x = 0.0
        self._target_y = 0.0
        self._smoothed_x = 0.0
        self._smoothed_y = 0.0
        self._orbital_angle = 0.0
        self._was_slide_cancel_down = False
        self._slide_cancel_started: Optional[float] = None
        self._yy_pulse_until = 0.0
        self._next_yy_pulse = 0.0
        self._auto_ping_until = 0.0
        self._next_auto_ping = 0.0
        self._was_shooting = False
        self._fire_started_at: Optional[float] = None
        self._report_error_logged = False

        # Virtual pad
        self._pad = None
        self.virtual_pad_error = vg_import_error
        if vg is not None:
            try:
                self._pad = vg.VX360Gamepad()
                self.virtual_pad_error = None
            except Exception as exc:
                self.virtual_pad_error = f"{type(exc).__name__}: {exc}"
                logger.exception("vgamepad controller initialization failed: %s", exc)

        # Simple key state (updated from outside or pynput)
        self._keys_down: set[int] = set()

    # ------------------------------------------------------------------ API
    def start(self) -> None:
        with self._lock:
            if self._active:
                return
            self._active = True
            self._thread = threading.Thread(
                target=self._clock_loop,
                name="BioSync-Engine",
                daemon=True,
            )
            self._thread.start()

    def stop(self) -> None:
        with self._lock:
            self._active = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=0.3)
        with self._lock:
            self._raw_x = 0
            self._raw_y = 0
            self._target_x = 0.0
            self._target_y = 0.0
            self._smoothed_x = 0.0
            self._smoothed_y = 0.0
            self._keys_down.clear()
            self._orbital_angle = 0.0
            self._was_slide_cancel_down = False
            self._slide_cancel_started = None
            self._yy_pulse_until = 0.0
            self._next_yy_pulse = 0.0
            self._auto_ping_until = 0.0
            self._next_auto_ping = 0.0
            self._was_shooting = False
            self._fire_started_at = None
        self._reset_pad()

    def inject_raw_delta(self, dx: int, dy: int) -> None:
        with self._lock:
            self._raw_x += dx
            self._raw_y += dy

    def set_key(self, vk: int, down: bool) -> None:
        with self._lock:
            if down:
                self._keys_down.add(vk)
            else:
                self._keys_down.discard(vk)

    def is_key_down(self, vk: int) -> bool:
        with self._lock:
            return vk in self._keys_down

    def update_config(self, cfg: EngineConfig) -> None:
        with self._lock:
            self.cfg = cfg

    @property
    def virtual_pad_available(self) -> bool:
        return self._pad is not None

    # ------------------------------------------------------------- clock
    def _clock_loop(self) -> None:
        last = time.perf_counter()
        target_dt = 0.001  # 1000 Hz soft target
        while True:
            with self._lock:
                if not self._active:
                    break
            now = time.perf_counter()
            dt = max(now - last, 1e-4)
            last = now
            self._process_frame(dt)
            # Soft sleep — not spin-wait (latency relaxed)
            elapsed = time.perf_counter() - now
            sleep_t = target_dt - elapsed
            if sleep_t > 0.0002:
                time.sleep(sleep_t)

    def _process_frame(self, dt: float) -> None:
        cfg = self.cfg
        dt_ms = min(max(dt * 1000.0, 0.001), 8.0)
        with self._lock:
            dx, dy = self._raw_x, self._raw_y
            self._raw_x = 0
            self._raw_y = 0

        if dx != 0 or dy != 0:
            norm_x = (dx / dt_ms) * cfg.hardware_gain * cfg.filter_x * cfg.sens_x
            norm_y = (-dy / dt_ms) * cfg.hardware_gain * cfg.filter_y * cfg.sens_y
            norm_x *= cfg.curve_x
            norm_y *= cfg.curve_y

            mag = math.sqrt(norm_x * norm_x + norm_y * norm_y)
            if mag > 0.0:
                factor = (mag / 500_000.0) ** cfg.acceleration
                self._target_x = (norm_x / mag) * factor * 32767.0
                self._target_y = (norm_y / mag) * factor * 32767.0
        else:
            friction = min(cfg.friction, 0.95) ** dt_ms
            self._target_x *= friction
            self._target_y *= friction
            if abs(self._target_x) < 1.0:
                self._target_x = 0.0
            if abs(self._target_y) < 1.0:
                self._target_y = 0.0

        # Exponential smoothing
        alpha = max(0.15, min(1.0, dt_ms * 0.45))
        self._smoothed_x += (self._target_x - self._smoothed_x) * alpha
        self._smoothed_y += (self._target_y - self._smoothed_y) * alpha
        if math.hypot(self._smoothed_x, self._smoothed_y) < 1.0:
            self._smoothed_x = 0.0
            self._smoothed_y = 0.0

        fx, fy = self._smoothed_x, self._smoothed_y
        magnitude = math.sqrt(fx * fx + fy * fy)
        if magnitude > 32767.0 and magnitude > 0.0:
            fx = fx / magnitude * 32767.0
            fy = fy / magnitude * 32767.0
        if magnitude > 0.0:
            angle = math.atan2(fy, fx)
            fx += math.cos(angle) * cfg.inverse_deadzone
            fy += math.sin(angle) * cfg.inverse_deadzone

        fire_down = self.is_key_down(0x01)
        now = time.perf_counter()
        if cfg.no_recoil_active and fire_down:
            if self._fire_started_at is None:
                self._fire_started_at = now
            elapsed_ms = (now - self._fire_started_at) * 1000.0
            recoil_x, recoil_y = sample_recoil(
                cfg.recoil_profile,
                elapsed_ms,
                cfg.no_recoil_force_x,
                cfg.no_recoil_force_y,
            )
            fy -= recoil_y
            fx += recoil_x
        else:
            self._fire_started_at = None

        rx = int(max(-32767, min(32767, fx)))
        ry = int(max(-32767, min(32767, fy)))

        # Left stick from WASD
        lx = 0
        ly = 0
        if self.is_key_down(0x57):  # W
            ly = 32767
        elif self.is_key_down(0x53):  # S
            ly = -32767
        if self.is_key_down(0x44):  # D
            lx = 32767
        elif self.is_key_down(0x41):  # A
            lx = -32767

        macro_y, macro_a, macro_b, macro_ls, auto_ping = self._process_macros(
            cfg, now, fire_down
        )

        if cfg.buffed_aim_active:
            self._orbital_angle = (
                self._orbital_angle + dt_ms * 0.012
            ) % (2.0 * math.pi)
            drift = cfg.buffed_aim_force * 120.0
            lx = int(max(-32767, min(32767, lx + math.cos(self._orbital_angle) * drift)))
            ly = int(max(-32767, min(32767, ly + math.sin(self._orbital_angle) * drift)))

        self._apply_report(
            rx, ry, lx, ly,
            macro_y=macro_y,
            macro_a=macro_a,
            macro_b=macro_b,
            macro_ls=macro_ls,
            auto_ping=auto_ping,
        )

    def _process_macros(self, cfg, now, fire_down):
        yy_down = cfg.yy_active and self.is_key_down(cfg.vk_yy)
        if yy_down:
            if now >= self._yy_pulse_until and now >= self._next_yy_pulse:
                self._yy_pulse_until = now + 0.025
                self._next_yy_pulse = now + max(0.0, cfg.yy_interval_ms) / 1000.0
        else:
            self._yy_pulse_until = 0.0
            self._next_yy_pulse = now
        macro_y = yy_down and now < self._yy_pulse_until

        slide_down = cfg.slide_cancel_active and self.is_key_down(cfg.vk_slide_cancel)
        if slide_down and not self._was_slide_cancel_down:
            self._slide_cancel_started = now
        self._was_slide_cancel_down = slide_down

        macro_a = False
        macro_b = False
        macro_ls = False
        if self._slide_cancel_started is not None:
            elapsed_ms = (now - self._slide_cancel_started) * 1000.0
            if elapsed_ms < 10.0:
                macro_b = True
            elif elapsed_ms < 85.0:
                pass
            elif elapsed_ms < 95.0:
                macro_a = True
            elif elapsed_ms < 120.0:
                macro_ls = True
            else:
                self._slide_cancel_started = None

        if cfg.auto_ping_active and fire_down:
            if not self._was_shooting or now >= self._next_auto_ping:
                self._auto_ping_until = now + 0.025
                self._next_auto_ping = (
                    now + max(0.0, cfg.auto_ping_interval_ms) / 1000.0
                )
        else:
            self._auto_ping_until = 0.0
            self._next_auto_ping = now
        self._was_shooting = fire_down

        return (
            macro_y,
            macro_a,
            macro_b,
            macro_ls,
            cfg.auto_ping_active and now < self._auto_ping_until,
        )

    def _apply_report(
        self,
        rx: int,
        ry: int,
        lx: int,
        ly: int,
        *,
        macro_y: bool = False,
        macro_a: bool = False,
        macro_b: bool = False,
        macro_ls: bool = False,
        auto_ping: bool = False,
    ) -> None:
        if self._pad is None:
            return
        cfg = self.cfg
        try:
            self._pad.right_joystick(x_value=rx, y_value=ry)
            self._pad.left_joystick(x_value=lx, y_value=ly)

            # Triggers
            self._pad.left_trigger(value=255 if self.is_key_down(0x02) else 0)   # RMB
            self._pad.right_trigger(value=255 if self.is_key_down(0x01) else 0)  # LMB

            if vg is None:
                self._pad.update()
                self._report_error_logged = False
                return

            # Buttons
            def btn(vk: int, button, macro_down: bool = False):
                if macro_down or self.is_key_down(vk):
                    self._pad.press_button(button=button)
                else:
                    self._pad.release_button(button=button)

            btn(cfg.vk_a, vg.XUSB_BUTTON.XUSB_GAMEPAD_A, macro_a)
            btn(cfg.vk_b, vg.XUSB_BUTTON.XUSB_GAMEPAD_B, macro_b)
            btn(cfg.vk_y, vg.XUSB_BUTTON.XUSB_GAMEPAD_Y, macro_y)
            btn(cfg.vk_lb, vg.XUSB_BUTTON.XUSB_GAMEPAD_LEFT_SHOULDER)
            btn(cfg.vk_rb, vg.XUSB_BUTTON.XUSB_GAMEPAD_RIGHT_SHOULDER)
            btn(cfg.vk_ls, vg.XUSB_BUTTON.XUSB_GAMEPAD_LEFT_THUMB, macro_ls)
            btn(cfg.vk_rs, vg.XUSB_BUTTON.XUSB_GAMEPAD_RIGHT_THUMB)
            btn(
                0,
                vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_UP,
                auto_ping,
            )

            self._pad.update()
            self._report_error_logged = False
        except Exception:
            if not self._report_error_logged:
                logger.exception("Failed to submit a virtual controller report.")
                self._report_error_logged = True

    def _reset_pad(self) -> None:
        if self._pad is None:
            return
        try:
            self._pad.reset()
            self._pad.update()
        except Exception:
            logger.exception("Failed to reset the virtual controller.")

    def dispose(self) -> None:
        self.stop()
        self._pad = None
