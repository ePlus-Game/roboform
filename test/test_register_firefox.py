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

            def find_elements(self, _by, selector):
                if "credentials-section" in selector:
                    return [Element(self.returned_email)]
                if "done-message" in selector:
                    return [Element("Account created successfully")]
                return []

        class FakeWait:
            def __init__(self, driver, _timeout):
                self.driver = driver

            def until(self, predicate):
                return predicate(self.driver)

        with patch.object(registration, "WebDriverWait", FakeWait), patch.object(
            registration.subprocess, "run"
        ) as record:
            with patch.dict(os.environ, {"REGISTRATION_EMAIL": "expected@example.com"}):
                registration.await_confirmation(FakeDriver("expected@example.com"), "expected@example.com")
                record.assert_called_once()
                record.reset_mock()
                with self.assertRaisesRegex(registration.RegistrationBlocked, "does not match"):
                    registration.await_confirmation(FakeDriver("wrong@example.com"), "expected@example.com")
                record.assert_not_called()

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
