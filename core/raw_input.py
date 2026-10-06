"""Windows Raw Input mouse capture attached to the application window."""
from __future__ import annotations

import ctypes
import logging
from ctypes import wintypes
from typing import Callable, Optional

logger = logging.getLogger(__name__)


class WindowsRawInputCapture:
    WM_INPUT = 0x00FF
    RID_INPUT = 0x10000003
    RIDEV_INPUTSINK = 0x00000100
    RIDEV_REMOVE = 0x00000001

    def __init__(self, on_delta: Callable[[int, int], None]):
        self._on_delta = on_delta
        self._hwnd: Optional[int] = None
        self._callback = None
        self._subclass_id = id(self) & 0xFFFFFFFF
        self._user32 = None
        self._comctl32 = None
        self._device = None
        self._input_header = None
        self._raw_input = None
        self._subclass_proc_type = None

    def start(self, hwnd: int) -> None:
        if self._hwnd is not None:
            return

        if not hwnd:
            raise ValueError("A janela do app precisa estar criada para iniciar Raw Input.")

        self._user32 = ctypes.WinDLL("user32", use_last_error=True)
        self._comctl32 = ctypes.WinDLL("comctl32", use_last_error=True)
        self._define_structures()
        self._configure_api()

        self._hwnd = hwnd
        self._callback = self._subclass_proc_type(self._handle_message)
        if not self._comctl32.SetWindowSubclass(
            ctypes.c_void_p(hwnd),
            self._callback,
            self._subclass_id,
            0,
        ):
            self._hwnd = None
            raise ctypes.WinError(ctypes.get_last_error())

        device = self._device()
        device.usUsagePage = 0x01
        device.usUsage = 0x02
        device.dwFlags = self.RIDEV_INPUTSINK
        device.hwndTarget = ctypes.c_void_p(hwnd)
        if not self._user32.RegisterRawInputDevices(
            ctypes.byref(device), 1, ctypes.sizeof(self._device)
        ):
            error = ctypes.WinError(ctypes.get_last_error())
            self._comctl32.RemoveWindowSubclass(
                ctypes.c_void_p(hwnd), self._callback, self._subclass_id
            )
            self._hwnd = None
            self._callback = None
            raise error

    def stop(self) -> None:
        if self._hwnd is None:
            return

        hwnd = self._hwnd
        if self._user32 is not None:
            device = self._device()
            device.usUsagePage = 0x01
            device.usUsage = 0x02
            device.dwFlags = self.RIDEV_REMOVE
            device.hwndTarget = None
            if not self._user32.RegisterRawInputDevices(
                ctypes.byref(device), 1, ctypes.sizeof(self._device)
            ):
                logger.error(
                    "Raw Input unregister failed: %s",
                    ctypes.WinError(ctypes.get_last_error()),
                )

        if self._comctl32 is not None and self._callback is not None:
            if not self._comctl32.RemoveWindowSubclass(
                ctypes.c_void_p(hwnd), self._callback, self._subclass_id
            ):
                logger.error("Could not remove the Raw Input window subclass.")

        self._hwnd = None
        self._callback = None

    def _define_structures(self) -> None:
        class RawInputDevice(ctypes.Structure):
            _fields_ = [
                ("usUsagePage", wintypes.USHORT),
                ("usUsage", wintypes.USHORT),
                ("dwFlags", wintypes.DWORD),
                ("hwndTarget", wintypes.HWND),
            ]

        class RawInputHeader(ctypes.Structure):
            _fields_ = [
                ("dwType", wintypes.DWORD),
                ("dwSize", wintypes.DWORD),
                ("hDevice", wintypes.HANDLE),
                ("wParam", wintypes.WPARAM),
            ]

        class RawMouse(ctypes.Structure):
            _fields_ = [
                ("usFlags", wintypes.USHORT),
                ("ulButtons", wintypes.ULONG),
                ("ulRawButtons", wintypes.ULONG),
                ("lLastX", wintypes.LONG),
                ("lLastY", wintypes.LONG),
                ("ulExtraInformation", wintypes.ULONG),
            ]

        class RawInput(ctypes.Structure):
            _fields_ = [
                ("header", RawInputHeader),
                ("mouse", RawMouse),
            ]

        self._device = RawInputDevice
        self._input_header = RawInputHeader
        self._raw_input = RawInput
        self._subclass_proc_type = ctypes.WINFUNCTYPE(
            wintypes.LPARAM,
            wintypes.HWND,
            wintypes.UINT,
            wintypes.WPARAM,
            wintypes.LPARAM,
            ctypes.c_size_t,
            ctypes.c_size_t,
        )

    def _configure_api(self) -> None:
        self._user32.RegisterRawInputDevices.argtypes = [
            ctypes.POINTER(self._device), wintypes.UINT, wintypes.UINT
        ]
        self._user32.RegisterRawInputDevices.restype = wintypes.BOOL
        self._user32.GetRawInputData.argtypes = [
            wintypes.HANDLE,
            wintypes.UINT,
            ctypes.c_void_p,
            ctypes.POINTER(wintypes.UINT),
            wintypes.UINT,
        ]
        self._user32.GetRawInputData.restype = wintypes.UINT
        self._comctl32.SetWindowSubclass.argtypes = [
            wintypes.HWND, self._subclass_proc_type, ctypes.c_size_t, ctypes.c_size_t
        ]
        self._comctl32.SetWindowSubclass.restype = wintypes.BOOL
        self._comctl32.RemoveWindowSubclass.argtypes = [
            wintypes.HWND, self._subclass_proc_type, ctypes.c_size_t
        ]
        self._comctl32.RemoveWindowSubclass.restype = wintypes.BOOL
        self._comctl32.DefSubclassProc.argtypes = [
            wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM
        ]
        self._comctl32.DefSubclassProc.restype = wintypes.LPARAM

    def _handle_message(self, hwnd, message, wparam, lparam, subclass_id, ref_data):
        if message == self.WM_INPUT:
            try:
                self._read_mouse_delta(lparam)
            except Exception:
                logger.exception("Failed to read a Windows Raw Input mouse report.")

        return self._comctl32.DefSubclassProc(hwnd, message, wparam, lparam)

    def _read_mouse_delta(self, raw_input_handle: int) -> None:
        size = wintypes.UINT(0)
        header_size = ctypes.sizeof(self._input_header)
        result = self._user32.GetRawInputData(
            wintypes.HANDLE(raw_input_handle),
            self.RID_INPUT,
            None,
            ctypes.byref(size),
            header_size,
        )
        if result == 0xFFFFFFFF or size.value < ctypes.sizeof(self._raw_input):
            return

        buffer = ctypes.create_string_buffer(size.value)
        result = self._user32.GetRawInputData(
            wintypes.HANDLE(raw_input_handle),
            self.RID_INPUT,
            ctypes.cast(buffer, ctypes.c_void_p),
            ctypes.byref(size),
            header_size,
        )
        if result != size.value:
            raise ctypes.WinError(ctypes.get_last_error())

        raw = self._raw_input.from_buffer_copy(buffer.raw[:size.value])
        if raw.header.dwType == 0 and (raw.mouse.lLastX or raw.mouse.lLastY):
            self._on_delta(raw.mouse.lLastX, raw.mouse.lLastY)
