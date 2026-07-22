from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import token_flow


class FakeProcess:
    def __init__(self) -> None:
        self.terminated = False

    def poll(self) -> None:
        return None

    def wait(self, timeout: int) -> None:
        return None

    def terminate(self) -> None:
        self.terminated = True


class TokenFlowTests(unittest.TestCase):
    def test_find_chrome_checks_standard_locations(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            chrome = Path(temporary) / "Google" / "Chrome" / "Application" / "chrome.exe"
            chrome.parent.mkdir(parents=True)
            chrome.touch()
            with patch.dict(
                os.environ,
                {"PROGRAMFILES": temporary, "PROGRAMFILES(X86)": "", "LOCALAPPDATA": ""},
                clear=False,
            ):
                self.assertEqual(chrome, token_flow.find_chrome())

    def test_detect_google_email_reads_chrome_preferences(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            profile = Path(temporary) / "Google" / "Chrome" / "User Data" / "Default"
            profile.mkdir(parents=True)
            (profile / "Preferences").write_text(
                json.dumps({"account_info": [{"email": "person@example.com"}]}),
                encoding="utf-8",
            )
            with patch.dict(os.environ, {"LOCALAPPDATA": temporary}):
                self.assertEqual("person@example.com", token_flow.detect_google_email())

    def test_detect_google_email_ignores_invalid_preferences(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            profile = Path(temporary) / "Google" / "Chrome" / "User Data" / "Default"
            profile.mkdir(parents=True)
            (profile / "Preferences").write_text("not json", encoding="utf-8")
            with patch.dict(os.environ, {"LOCALAPPDATA": temporary}):
                self.assertEqual("", token_flow.detect_google_email())

    def test_oauth_cookie_reads_only_debug_targets(self) -> None:
        targets = [
            {"type": "other"},
            {"type": "page", "webSocketDebuggerUrl": "ws://local"},
        ]
        result = {
            "cookies": [
                {"name": "unrelated", "value": "ignore"},
                {"name": "oauth_token", "value": "cookie-value"},
            ]
        }
        with patch.object(token_flow, "_json_endpoint", return_value=targets), patch.object(
            token_flow, "_cdp_command", return_value=result
        ):
            self.assertEqual("cookie-value", token_flow._oauth_cookie(9222))

    def test_obtain_master_token_is_fully_mockable_offline(self) -> None:
        process = FakeProcess()
        with tempfile.TemporaryDirectory() as temporary:
            auth_folder = Path(temporary) / "auth"
            with (
                patch.object(token_flow, "find_chrome", return_value=Path("chrome.exe")),
                patch.object(token_flow, "_free_port", return_value=9222),
                patch.object(token_flow.tempfile, "mkdtemp", return_value=str(auth_folder)),
                patch.object(token_flow.subprocess, "Popen", return_value=process) as popen,
                patch.object(token_flow, "_oauth_cookie", return_value="browser-cookie"),
                patch.object(token_flow.gpsoauth, "exchange_token", return_value={"Token": "master-token"}) as exchange,
                patch.object(token_flow, "_close_browser") as close,
                patch.object(token_flow.time, "sleep"),
            ):
                token, device_id = token_flow.obtain_master_token(" person@example.com ", timeout_seconds=1)

        self.assertEqual("master-token", token)
        self.assertRegex(device_id, r"^[0-9a-f]{16}$")
        exchange.assert_called_once_with("person@example.com", "browser-cookie", device_id)
        popen.assert_called_once()
        close.assert_called_once_with(9222, process)

    def test_obtain_master_token_validates_requirements(self) -> None:
        with patch.object(token_flow, "find_chrome", return_value=None):
            with self.assertRaisesRegex(RuntimeError, "Chrome is required"):
                token_flow.obtain_master_token("person@example.com")

        with patch.object(token_flow, "find_chrome", return_value=Path("chrome.exe")):
            with self.assertRaisesRegex(RuntimeError, "email first"):
                token_flow.obtain_master_token("not-an-email")

    def test_google_exchange_error_is_reported_and_cleaned_up(self) -> None:
        process = FakeProcess()
        with (
            patch.object(token_flow, "find_chrome", return_value=Path("chrome.exe")),
            patch.object(token_flow.subprocess, "Popen", return_value=process),
            patch.object(token_flow, "_oauth_cookie", return_value="browser-cookie"),
            patch.object(token_flow.gpsoauth, "exchange_token", return_value={"Error": "BadAuthentication"}),
            patch.object(token_flow, "_close_browser") as close,
            patch.object(token_flow.time, "sleep"),
        ):
            with self.assertRaisesRegex(RuntimeError, "BadAuthentication"):
                token_flow.obtain_master_token("person@example.com", timeout_seconds=1)
        close.assert_called_once()


if __name__ == "__main__":
    unittest.main()
