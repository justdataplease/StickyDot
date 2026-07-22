from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import windows_integration
from windows_integration import WindowsStartup


def fake_winreg() -> MagicMock:
    registry = MagicMock()
    registry.HKEY_CURRENT_USER = object()
    registry.KEY_READ = 1
    registry.KEY_SET_VALUE = 2
    registry.REG_SZ = 3
    registry.REG_EXPAND_SZ = 4
    return registry


class WindowsStartupTests(unittest.TestCase):
    def test_frozen_command_quotes_executable_path(self) -> None:
        executable = r"C:\Program Files\StickyDot\StickyDot.exe"
        with patch.object(windows_integration.sys, "frozen", True, create=True), patch.object(
            windows_integration.sys, "executable", executable
        ):
            self.assertEqual(subprocess.list2cmdline([str(Path(executable).resolve())]), WindowsStartup.command())

    def test_source_command_includes_python_and_entry_script(self) -> None:
        with patch.object(windows_integration.sys, "frozen", False, create=True):
            command = WindowsStartup.command()
        self.assertIn(Path(sys.executable).name, command)
        self.assertIn("notes_widget.py", command)

    def test_is_enabled_reads_current_user_run_value(self) -> None:
        registry = fake_winreg()
        key = object()
        registry.OpenKey.return_value.__enter__.return_value = key
        registry.QueryValueEx.return_value = (r'"C:\Apps\StickyDot.exe"', registry.REG_SZ)
        with patch.object(windows_integration, "winreg", registry), patch.object(
            windows_integration.sys, "platform", "win32"
        ):
            self.assertTrue(WindowsStartup.is_enabled())
        registry.QueryValueEx.assert_called_once_with(key, "StickyDot")

    def test_is_enabled_handles_missing_value(self) -> None:
        registry = fake_winreg()
        registry.OpenKey.side_effect = FileNotFoundError
        with patch.object(windows_integration, "winreg", registry), patch.object(
            windows_integration.sys, "platform", "win32"
        ):
            self.assertFalse(WindowsStartup.is_enabled())

    def test_enable_writes_current_executable_command(self) -> None:
        registry = fake_winreg()
        key = object()
        registry.CreateKey.return_value.__enter__.return_value = key
        with patch.object(windows_integration, "winreg", registry), patch.object(
            windows_integration.sys, "platform", "win32"
        ), patch.object(WindowsStartup, "command", return_value=r'"C:\Apps\StickyDot.exe"'):
            WindowsStartup.set_enabled(True)
        registry.SetValueEx.assert_called_once_with(
            key, "StickyDot", 0, registry.REG_SZ, r'"C:\Apps\StickyDot.exe"'
        )

    def test_disable_deletes_value_and_missing_value_is_safe(self) -> None:
        registry = fake_winreg()
        key = object()
        registry.OpenKey.return_value.__enter__.return_value = key
        with patch.object(windows_integration, "winreg", registry), patch.object(
            windows_integration.sys, "platform", "win32"
        ):
            WindowsStartup.set_enabled(False)
        registry.DeleteValue.assert_called_once_with(key, "StickyDot")

        registry.OpenKey.side_effect = FileNotFoundError
        with patch.object(windows_integration, "winreg", registry), patch.object(
            windows_integration.sys, "platform", "win32"
        ):
            WindowsStartup.set_enabled(False)

    def test_non_windows_platform_is_safe(self) -> None:
        with patch.object(windows_integration.sys, "platform", "linux"):
            self.assertFalse(WindowsStartup.is_enabled())
            with self.assertRaisesRegex(RuntimeError, "only on Windows"):
                WindowsStartup.set_enabled(True)


if __name__ == "__main__":
    unittest.main()
