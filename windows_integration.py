from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Any

try:
    import winreg
except ImportError:  # pragma: no cover - StickyDot targets Windows
    winreg = None  # type: ignore[assignment]


class WindowsStartup:
    """Manage StickyDot's per-user Windows sign-in launch entry."""

    RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
    VALUE_NAME = "StickyDot"

    @staticmethod
    def command() -> str:
        if getattr(sys, "frozen", False):
            arguments = [str(Path(sys.executable).resolve())]
        else:
            arguments = [str(Path(sys.executable).resolve()), str(Path(__file__).with_name("notes_widget.py").resolve())]
        return subprocess.list2cmdline(arguments)

    @classmethod
    def is_enabled(cls) -> bool:
        if sys.platform != "win32" or winreg is None:
            return False
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, cls.RUN_KEY, 0, winreg.KEY_READ) as key:
                value, value_type = winreg.QueryValueEx(key, cls.VALUE_NAME)
        except (FileNotFoundError, OSError):
            return False
        return value_type in (winreg.REG_SZ, winreg.REG_EXPAND_SZ) and bool(str(value).strip())

    @classmethod
    def set_enabled(cls, enabled: bool) -> None:
        if sys.platform != "win32" or winreg is None:
            raise RuntimeError("Start with Windows is available only on Windows")
        if enabled:
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, cls.RUN_KEY) as key:
                winreg.SetValueEx(key, cls.VALUE_NAME, 0, winreg.REG_SZ, cls.command())
            return
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, cls.RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
                winreg.DeleteValue(key, cls.VALUE_NAME)
        except FileNotFoundError:
            pass
