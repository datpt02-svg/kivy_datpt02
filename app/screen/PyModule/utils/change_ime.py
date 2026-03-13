"""
Windows Keyboard IME Utility
============================

This module provides a lightweight utility class `WindowsKeyboardIME`
for managing Windows Input Method Editor (IME) layouts programmatically.

It allows switching between different keyboard layouts (e.g., English, Japanese)
and querying the currently active IME layout of the foreground window.

Typical use cases:
- Automatically set IME to English before starting text input.
- Detect or restore user's previous IME layout when switching windows.
"""

import ctypes
from app.env import ENGLISH_IME_CODE

WM_INPUTLANGCHANGEREQUEST = 0x50

class WindowsKeyboardIME:
    """
    A helper class for managing Windows Input Method Editor (IME) layouts.

    This class uses `ctypes` to interface directly with `user32.dll` and
    provides methods to switch and read the current keyboard input language.

    Attributes:
        user32 (ctypes.WinDLL): Handle to the Windows user32.dll.
        WM_INPUTLANGCHANGEREQUEST (int): Windows message constant for IME change.
    """

    def __init__(self):
        # Load user32.dll
        self.user32 = ctypes.WinDLL("user32", use_last_error=True)

    def set_ime(self, hkl_code: int = ENGLISH_IME_CODE):
        """
        Thiết lập bàn phím Windows IME theo mã layout (hkl_code).
        Ví dụ:
            - English (US): 0x04090409
            - Japanese IME: 0x04110411
        """
        hwnd = self.user32.GetForegroundWindow()
        if not hwnd:
            raise RuntimeError("Không tìm thấy cửa sổ foreground")

        self.user32.ActivateKeyboardLayout(hkl_code, 0)
        self.user32.PostMessageW(
            hwnd, WM_INPUTLANGCHANGEREQUEST, 0, hkl_code
        )

    def get_current_ime(self) -> int:
        """
        Lấy mã bàn phím Windows IME hiện tại (HKL) của foreground window.
        Trả về None nếu không thể lấy được.
        """
        hwnd = self.user32.GetForegroundWindow()
        if not hwnd:
            hwnd = self.user32.GetActiveWindow()
            if not hwnd:
                # Fallback: Get current thread's keyboard layout
                try:
                    current_thread_id = self.user32.GetCurrentThreadId()
                    layout_id = self.user32.GetKeyboardLayout(current_thread_id)
                    return layout_id if layout_id else None
                except Exception:
                    return None

        try:
            thread_id = self.user32.GetWindowThreadProcessId(hwnd, 0)
            layout_id = self.user32.GetKeyboardLayout(thread_id)
            return layout_id if layout_id else None
        except Exception:
            return None
