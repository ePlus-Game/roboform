"""Offline tests for the Firefox registration guardrails (no browser or network)."""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
spec = importlib.util.spec_from_file_location("register_firefox", ROOT / "scripts" / "register-firefox.py")
registration = importlib.util.module_from_spec(spec)
spec.loader.exec_module(registration)


class RegistrationGuards(unittest.TestCase):
    def test_normalize_email(self):
        self.assertEqual(registration.normalize_email(" Test+User@Example.COM "), "test+user@example.com")
        for value in ("missing-at", "a..b@example.com", "=HACK@example.com", "test@"):
            with self.subTest(value=value), self.assertRaises(registration.RegistrationBlocked):
                registration.normalize_email(value)

    def test_explicit_privacy_consent_is_required_before_browser(self):
        with patch.dict(os.environ, {"FIREFOX_PRIVACY_CONSENT": "false"}, clear=True):
            with self.assertRaisesRegex(registration.RegistrationBlocked, "consent"):
                registration.run()

    def test_duplicate_verified_account_is_rejected_but_unverified_not_blocked(self):
        original = Path.cwd()
        with tempfile.TemporaryDirectory() as directory:
            try:
                os.chdir(directory)
                Path("data").mkdir()
                Path("data/registrations.csv").write_text(
                    "email,registered_at_utc,registered_date_vn,verification_method\n"
                    "confirmed@example.com,2026-11-09T00:00:00Z,2026-11-09,signup_ui_success\n"
                    "old@example.com,2026-11-09T00:00:00Z,2026-11-09,unverified\n",
                    encoding="utf-8",
                )
                with self.assertRaisesRegex(registration.RegistrationBlocked, "already"):
                    registration.check_already_verified("confirmed@example.com")
                registration.check_already_verified("old@example.com")
            finally:
                os.chdir(original)

    def test_receipt_only_after_matching_visible_success(self):
        class Element:
            def __init__(self, text):
                self.text = text

            def is_displayed(self):
                return True

        class FakeDriver:
            def __init__(self, returned_email):
                self.returned_email = returned_email
                self.window_handles = ["original", "confirmation"]
                self.current_window_handle = "original"
                self.switch_to = self

            def window(self, handle):
                self.current_window_handle = handle

            def find_elements(self, _by, selector):
                if self.current_window_handle != "confirmation":
                    return []
                if "credentials-section" in selector:
                    return [Element(self.returned_email)]
                if "done-message" in selector:
                    return [Element("Account created successfully")]
                return []

        with patch.object(registration.subprocess, "run") as record:
            with patch.dict(os.environ, {"REGISTRATION_EMAIL": "expected@example.com"}):
                registration.await_confirmation(FakeDriver("expected@example.com"), "expected@example.com")
                record.assert_called_once()
                record.reset_mock()
                with self.assertRaisesRegex(registration.RegistrationBlocked, "does not match"):
                    registration.await_confirmation(FakeDriver("wrong@example.com"), "expected@example.com")
                record.assert_not_called()

    def test_sanitized_state_never_includes_email_or_password(self):
        state = {"windows": 1, "confirmed_email": "private@example.com",
                 "challenge": "image-code", "visible_errors": 0}
        safe = registration.sanitized_post_submit_state(state)
        self.assertNotIn("confirmed_email", safe)
        self.assertNotIn("private@example.com", str(safe))
        self.assertEqual(safe["challenge"], "image-code")

    def test_visible_verification_in_second_window(self):
        class Element:
            text = ""

            def is_displayed(self):
                return True

        class FakeDriver:
            window_handles = ["signup", "challenge"]
            current_window_handle = "signup"

            def __init__(self):
                self.switch_to = self

            def window(self, handle):
                self.current_window_handle = handle

            def find_elements(self, _by, selector):
                if self.current_window_handle == "challenge" and ".verify-human-code-image" in selector:
                    return [Element()]
                return []

        driver = FakeDriver()
        state = registration.inspect_post_submit(driver)
        self.assertEqual(state["windows"], 2)
        self.assertEqual(state["challenge"], "image-code")
        self.assertFalse(state["success_screen"])
        self.assertEqual(driver.current_window_handle, "signup")

    def test_local_interactive_mode_must_be_explicitly_enabled(self):
        with patch.dict(os.environ, {"FIREFOX_INTERACTIVE": "true"}):
            self.assertTrue(registration.interactive_mode())
        with patch.dict(os.environ, {"FIREFOX_INTERACTIVE": "false"}):
            self.assertFalse(registration.interactive_mode())
        with patch.dict(os.environ, {}, clear=True):
            self.assertFalse(registration.interactive_mode())

    def test_interactive_challenge_waits_for_human_then_checks_real_success(self):
        challenge = {"windows": 2, "signup_form_visible": False,
                     "success_screen": False, "challenge": "image-code",
                     "visible_errors": 0, "submit_enabled": False,
                     "confirmed_email": None}
        success = dict(challenge, success_screen=True,
                       challenge="none", confirmed_email="expected@example.com")
        with patch.object(registration, "inspect_post_submit", side_effect=[challenge, success]) as inspect, \
             patch.object(registration.time, "sleep"), \
             patch.object(registration.subprocess, "run") as record:
            with patch.dict(os.environ, {"REGISTRATION_EMAIL": "expected@example.com"}):
                registration.await_confirmation(object(), "expected@example.com", interactive=True)
            self.assertEqual(inspect.call_count, 2)
            record.assert_called_once()

    def test_headless_challenge_still_fails_without_recording(self):
        challenge = {"windows": 2, "signup_form_visible": False,
                     "success_screen": False, "challenge": "image-code",
                     "visible_errors": 0, "submit_enabled": False,
                     "confirmed_email": None}
        with patch.object(registration, "inspect_post_submit", return_value=challenge), \
             patch.object(registration.time, "monotonic", side_effect=[0, 1, 7]), \
             patch.object(registration.time, "sleep"), \
             patch.object(registration.subprocess, "run") as record:
            with self.assertRaisesRegex(registration.RegistrationBlocked, "image-code"):
                registration.await_confirmation(object(), "expected@example.com")
            record.assert_not_called()

    def test_manual_pre_submit_waits_until_button_enabled(self):
        class Button:
            def __init__(self, enabled):
                self.enabled = enabled

            def is_enabled(self):
                return self.enabled

        class FakeDriver:
            window_handles = ["signup"]

        with patch.object(registration, "find_submit_button",
                          side_effect=[Button(False), Button(True)]) as finder, \
             patch.object(registration.time, "sleep"):
            registration.wait_for_manual_pre_submit_verification(FakeDriver(), timeout=30)
            self.assertEqual(finder.call_count, 2)

    def test_security_widget_detection(self):
        class FakeDriver:
            def __init__(self, elements):
                self.elements = elements

            def find_elements(self, by, selector):
                self.selector = selector
                return self.elements

        self.assertFalse(registration.human_verification_present(FakeDriver([])))
        self.assertTrue(registration.human_verification_present(FakeDriver([object()])))


if __name__ == "__main__":
    unittest.main()
