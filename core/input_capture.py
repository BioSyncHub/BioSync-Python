"""
Mouse / keyboard capture for the prototype.
Uses pynput (cross-platform). On Windows production path,
prefer Raw Input via ctypes for lower latency.
"""
from __future__ import annotations

import sys
from typing import Callable, Optional

from pynput import mouse, keyboard

from core.raw_input import WindowsRawInputCapture


class InputCapture:
    def __init__(
        self,
        on_mouse_delta: Callable[[int, int], None],
        on_key: Callable[[int, bool], None],
        window_handle: Optional[int] = None,
    ):
        self._on_delta = on_mouse_delta
        self._on_key = on_key
        self._window_handle = window_handle
        self._mouse_listener: Optional[mouse.Listener] = None
        self._kb_listener: Optional[keyboard.Listener] = None
        self._last_x: Optional[int] = None
        self._last_y: Optional[int] = None
        self._running = False
        self._raw_capture: Optional[WindowsRawInputCapture] = None

    def start(self) -> None:
        if self._running:
            return
        use_raw_input = sys.platform == "win32" and self._window_handle is not None

        def on_move(x, y):
            if self._last_x is not None and self._last_y is not None:
                dx = int(x - self._last_x)
                dy = int(y - self._last_y)
                if dx or dy:
                    self._on_delta(dx, dy)
            self._last_x = x
            self._last_y = y

        def on_click(x, y, button, pressed):
            # Map mouse buttons to synthetic VKs used by engine
            if button == mouse.Button.left:
                self._on_key(0x01, pressed)
            elif button == mouse.Button.right:
                self._on_key(0x02, pressed)

        def on_press(key):
            vk = self._vk_from_key(key)
            if vk is not None:
                self._on_key(vk, True)

        def on_release(key):
            vk = self._vk_from_key(key)
            if vk is not None:
                self._on_key(vk, False)

        if use_raw_input:
            self._raw_capture = WindowsRawInputCapture(self._on_delta)
            self._raw_capture.start(self._window_handle)

        self._running = True
        self._mouse_listener = mouse.Listener(
            on_move=None if use_raw_input else on_move,
            on_click=on_click,
        )
        self._kb_listener = keyboard.Listener(on_press=on_press, on_release=on_release)
        try:
            self._mouse_listener.start()
            self._kb_listener.start()
        except Exception:
            self.stop()
            raise

    def stop(self) -> None:
        self._running = False
        if self._raw_capture:
            self._raw_capture.stop()
            self._raw_capture = None
        if self._mouse_listener:
            self._mouse_listener.stop()
            self._mouse_listener = None
        if self._kb_listener:
            self._kb_listener.stop()
            self._kb_listener = None
        self._last_x = self._last_y = None

    @staticmethod
    def _vk_from_key(key) -> Optional[int]:
        """Best-effort VK mapping for common keys used by BioSync."""
        try:
            if isinstance(key, keyboard.KeyCode) and key.vk is not None:
                return key.vk
            # Named keys
            mapping = {
                keyboard.Key.space: 0x20,
                keyboard.Key.ctrl_l: 0x11,
                keyboard.Key.ctrl_r: 0x11,
                keyboard.Key.shift: 0x10,
                keyboard.Key.shift_l: 0x10,
                keyboard.Key.shift_r: 0x10,
                keyboard.Key.insert: 0x2D,
                keyboard.Key.page_up: 0x21,
                keyboard.Key.page_down: 0x22,
                keyboard.Key.end: 0x23,
                keyboard.Key.home: 0x24,
                keyboard.Key.left: 0x25,
                keyboard.Key.up: 0x26,
                keyboard.Key.right: 0x27,
                keyboard.Key.down: 0x28,
                keyboard.Key.delete: 0x2E,
                keyboard.Key.tab: 0x09,
                keyboard.Key.enter: 0x0D,
                keyboard.Key.esc: 0x1B,
                keyboard.Key.alt_l: 0x12,
                keyboard.Key.alt_r: 0x12,
            }
            for index in range(1, 13):
                function_key = getattr(keyboard.Key, f"f{index}", None)
                if function_key is not None:
                    mapping[function_key] = 0x6F + index
            return mapping.get(key)
        except Exception:
            return None
