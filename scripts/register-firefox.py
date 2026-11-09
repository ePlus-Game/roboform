"""Try RoboForm registration through the official Firefox add-on.

Requires Firefox privacy_consent to remain checked in workflow_dispatch.
Never logs credentials.
Records only an exact email match on RoboForm's visible success screen.
"""
from __future__ import annotations

import argparse
import csv
import getpass
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.support.ui import WebDriverWait

from firefox_support import download_signed_addon, open_roboform_start_page


class RegistrationBlocked(Exception):
    """Known, safe-to-report failure that does not contain credentials."""


def normalize_email(raw: str) -> str:
    email = raw.strip().lower()
    if len(email) > 254 or ".." in email or not re.fullmatch(
        r"[a-z0-9][a-z0-9._%+\-]*@[a-z0-9](?:[a-z0-9.\-]*[a-z0-9])?\.[a-z]{2,63}", email
    ):
        raise RegistrationBlocked("Invalid registration email.")
    return email


def check_already_verified(email: str) -> None:
    path = Path("data/registrations.csv")
    if not path.exists():
        return
    with path.open(encoding="utf-8", newline="") as reader:
        for row in csv.DictReader(reader):
            if row.get("email", "").lower() == email and row.get("verification_method") != "unverified":
                raise RegistrationBlocked("Email already has a verified registration record. No duplicate registration attempted.")


def visible_controls(driver, selector: str):
    return [element for element in driver.find_elements(By.CSS_SELECTOR, selector)
            if element.is_displayed()]


def click_exact_control(driver, label: str) -> bool:
    for element in visible_controls(driver, "button, input[type=button], input[type=submit], a, [role=button]"):
        text = (element.get_attribute("aria-label") or
                element.get_attribute("value") or element.text or "").strip()
        if text.casefold() == label.casefold() and element.is_enabled():
            element.click()
            return True
    return False


def body_text(driver) -> str:
    return driver.find_element(By.TAG_NAME, "body").text


def switch_to_signup(driver) -> bool:
    for handle in driver.window_handles:
        driver.switch_to.window(handle)
        try:
            body = body_text(driver)
        except Exception:
            continue
        if "Sign Up" in body or "Create Account" in body:
            return True
    return False


def enter_signup_form(driver) -> None:
    try:
        WebDriverWait(driver, 30).until(lambda d: switch_to_signup(d))
    except Exception as error:
        raise RegistrationBlocked("Firefox extension did not show Sign Up after Privacy acceptance.") from error
    if "Create Account" in body_text(driver) and len(visible_controls(driver, "input[type=password]")) >= 2:
        return
    if not click_exact_control(driver, "Sign Up"):
        raise RegistrationBlocked("Could not find a clickable Sign Up control in the Firefox add-on.")
    try:
        WebDriverWait(driver, 30).until(
            lambda d: len(visible_controls(d, "input[type=password]")) >= 2 and
            len(visible_controls(d, "input[type=text], input[type=email]")) >= 2
        )
    except Exception as error:
        raise RegistrationBlocked("RoboForm Firefox signup form did not appear after choosing Sign Up.") from error


def verification_present(driver) -> bool:
    selectors = (
        ".verify-human-cloudflare-turnstile-v0, .verify-human-captcha, "
        ".captcha-container, .cf-turnstile, .g-recaptcha, "
        "iframe[src*='challenges.cloudflare.com'], iframe[src*='captcha'], "
        "iframe[src*='turnstile']"
    )
    return bool(driver.find_elements(By.CSS_SELECTOR, selectors))


def find_submit_button(driver):
    for element in visible_controls(driver, "button, input[type=button], input[type=submit]"):
        text = (element.get_attribute("value") or element.text or "").strip()
        if text.casefold() == "create account":
            return element
    return None


def inspect_post_submit(driver) -> dict:
    """Inspect all browser tabs; never collect or log values, URLs or page HTML.

    The Firefox add-on may use a separate window.
    Log only whitelisted UI states so Master Password and tokens stay private.
    """
    state = {
        "windows": 0,
        "signup_form_visible": False,
        "success_screen": False,
        "challenge": "none",
        "visible_errors": 0,
        "submit_enabled": False,
        "confirmed_email": None,
    }
    try:
        original = driver.current_window_handle
    except Exception:
        original = None
    priority = {"none": 0, "unknown-verification": 1, "image-code": 2,
                "recaptcha": 3, "turnstile": 4}
    selectors = (
        ("turnstile", ".verify-human-cloudflare-turnstile-v0, .cf-turnstile, iframe[src*='challenges.cloudflare.com'], iframe[src*='turnstile']"),
        ("recaptcha", ".verify-human-google-recaptcha-v2, .g-recaptcha, iframe[src*='recaptcha']"),
        ("image-code", ".verify-human-code-image, .verify-human-captcha, iframe[src*='captcha']"),
        ("unknown-verification", ".questions-view .verify-human, .captcha-container"),
    )
    handles = list(driver.window_handles)
    state["windows"] = len(handles)
    try:
        for handle in handles:
            try:
                driver.switch_to.window(handle)
                def visible(selector):
                    return [e for e in driver.find_elements(By.CSS_SELECTOR, selector)
                            if e.is_displayed()]

                state["signup_form_visible"] |= bool(visible(".create-new-account"))
                for kind, selector in selectors:
                    if visible(selector) and priority[kind] > priority[state["challenge"]]:
                        state["challenge"] = kind

                errors = visible(".error-text:not(.hidden), .error-balloon:not(.hidden), [role='alert']")
                state["visible_errors"] += sum(bool(e.text.strip()) for e in errors)
                for button in visible("button, input[type=button], input[type=submit]"):
                    label = (button.get_attribute("value") or button.text or "").strip()
                    if label.casefold() == "create account" and button.is_enabled():
                        state["submit_enabled"] = True

                # Confirmation is valid only when BOTH title and email are visible
                # in the same window. Never log the email itself.
                titles = visible(".account-confirmation .done-message .text")
                addresses = visible(".account-confirmation .credentials-section .email")
                if titles and addresses and any(
                    "Account created successfully" in item.text for item in titles
                ):
                    state["success_screen"] = True
                    state["confirmed_email"] = addresses[0].text.strip()
                    break
            except Exception:
                # A popup may close while enumerating; inspect remaining windows.
                continue
    finally:
        if original and original in driver.window_handles:
            driver.switch_to.window(original)
    return state


def capture_verification_image(driver, output: Path = Path("dist/firefox-verification-image.png")) -> bool:
    """Capture an isolated image element without surrounding form content."""
    try:
        original = driver.current_window_handle
    except Exception:
        original = None
    try:
        for handle in list(driver.window_handles):
            try:
                driver.switch_to.window(handle)
                # Prefer the image itself; never screenshot a containing form.
                selectors = (
                    ".verify-human-code-image svg",
                    ".verify-human-code-image img",
                    ".verify-human-code-image canvas",
                    "img.verify-human-code-image",
                    "svg.verify-human-code-image",
                    ".verify-human-code-image",
                )
                for selector in selectors:
                    for element in driver.find_elements(By.CSS_SELECTOR, selector):
                        if not element.is_displayed():
                            continue
                        # Reject unexpectedly large elements, which might include
                        # account fields or the whole browser viewport.
                        size = element.size
                        if not (30 <= size["width"] <= 640 and
                                18 <= size["height"] <= 240):
                            continue
                        # A container is safe only when it has no form controls.
                        if element.find_elements(By.CSS_SELECTOR, "input, textarea, button, select"):
                            continue
                        output.parent.mkdir(parents=True, exist_ok=True)
                        if element.screenshot(str(output)):
                            # Guard against empty/incorrect image artifacts.
                            if (output.exists() and output.stat().st_size >= 8 and
                                    output.read_bytes()[:8] == bytes((137, 80, 78, 71, 13, 10, 26, 10))):
                                print("FIREFOX_VERIFICATION_IMAGE_CAPTURED: isolated image saved.")
                                return True
                            output.unlink(missing_ok=True)
            except Exception:
                # The window may close or the image may be unavailable.
                continue
    finally:
        if original and original in driver.window_handles:
            driver.switch_to.window(original)
    print("FIREFOX_VERIFICATION_IMAGE_UNAVAILABLE: no visible image element.")
    return False


def inspect_captured_verification_image(image: Path = Path("dist/firefox-verification-image.png")) -> None:
    """Run the current image through the read-only OCR diagnostics."""
    try:
        safe_env = {key: os.environ[key] for key in (
            "PATH", "HOME", "LANG", "GITHUB_STEP_SUMMARY"
        ) if key in os.environ}
        completed = subprocess.run(
            [sys.executable, "scripts/analyze-verification-image.py", str(image)],
            check=False,
            timeout=25,
            env=safe_env,
        )
        if completed.returncode:
            print("FIREFOX_IMAGE_CODE_OCR_FAILED: image inspection unsuccessful.")
    except (OSError, subprocess.TimeoutExpired):
        print("FIREFOX_IMAGE_CODE_OCR_FAILED: image inspection unavailable.")


def sanitized_post_submit_state(state: dict) -> dict:
    return {key: value for key, value in state.items() if key != "confirmed_email"}


def await_confirmation(driver, email: str) -> None:
    started = time.monotonic()
    state = None
    while time.monotonic() - started < 90:
        state = inspect_post_submit(driver)
        if state["success_screen"]:
            returned = normalize_email(state["confirmed_email"])
            if returned != email:
                raise RegistrationBlocked("Confirmed email does not match the requested account. No record written.")
            # Only a verified success screen + matching email can create a CSV.
            env = dict(os.environ)
            env["CONFIRMED_EMAIL"] = returned
            subprocess.run(["node", "scripts/record-firefox.mjs"], check=True, env=env)
            return

        elapsed = time.monotonic() - started
        if elapsed >= 5 and state["challenge"] != "none":
            if state["challenge"] == "image-code":
                if capture_verification_image(driver):
                    inspect_captured_verification_image()
            print("FIREFOX_POST_SUBMIT_STATE:", sanitized_post_submit_state(state))
            raise RegistrationBlocked(
                "RoboForm displayed " + state["challenge"] +
                " verification after Create Account; registration not confirmed."
            )
        if elapsed >= 8 and state["visible_errors"] > 0:
            print("FIREFOX_POST_SUBMIT_STATE:", sanitized_post_submit_state(state))
            raise RegistrationBlocked(
                "RoboForm displayed a validation/server error after Create Account. "
                "The message was intentionally not copied into CI logs to protect account data; no record written."
            )
        time.sleep(1)

    print("FIREFOX_POST_SUBMIT_STATE:", sanitized_post_submit_state(state or {}))
    raise RegistrationBlocked(
        "RoboForm did not show the verified success screen in any Firefox window "
        "within 90 seconds. Inspect the sanitized UI state above; no record written."
    )


def run(*, interactive: bool = False) -> None:
    if interactive and (os.getenv("GITHUB_ACTIONS", "").lower() == "true" or not sys.stdin.isatty()):
        raise RegistrationBlocked(
            "Manual verification requires a local interactive terminal and visible Firefox; "
            "it is not available in headless GitHub Actions."
        )
    consent = os.getenv("FIREFOX_PRIVACY_CONSENT", "").lower()
    if interactive and not consent:
        response = input("Do you agree to the RoboForm Firefox Privacy terms? [yes/N]: ")
        consent = "true" if response.strip().lower() == "yes" else "false"
    if consent != "true":
        raise RegistrationBlocked(
            "Firefox Privacy consent is required. Review the agreement; keep the privacy_consent option checked if you agree."
        )
    email_value = os.getenv("REGISTRATION_EMAIL", "")
    if interactive and not email_value:
        email_value = input("RoboForm signup email: ")
    email = normalize_email(email_value)
    full_name = os.getenv("REGISTRATION_FULL_NAME", "David Nguyen").strip()
    password = os.getenv("ROBOFORM_MASTER_PASSWORD", "")
    if interactive and not password:
        password = getpass.getpass("RoboForm master password (hidden): ")
    if not 2 <= len(full_name) <= 80 or re.search(r'[\*?"<>|\\/]', full_name):
        raise RegistrationBlocked("Invalid full name.")
    if not password.strip() or len(password) < 16:
        raise RegistrationBlocked("ROBOFORM_MASTER_PASSWORD repository secret must contain 16+ characters.")
    check_already_verified(email)

    with tempfile.TemporaryDirectory(prefix="roboform-firefox-register-") as tmp:
        xpi = Path(tmp) / "roboform-firefox.xpi"
        _, files = download_signed_addon(xpi)
        if "start-page.html" not in files:
            raise RegistrationBlocked("Official RoboForm Firefox add-on does not have the expected start page.")
        opts = webdriver.FirefoxOptions()
        if not interactive:
            opts.add_argument("-headless")
        if binary := os.getenv("FIREFOX_BINARY"):
            opts.binary_location = binary
        # System-access is limited to this fresh isolated runner and used solely
        # to open the real add-on start page. Never touch user browser profiles.
        service = Service(service_args=["--allow-system-access"])
        driver = webdriver.Firefox(options=opts, service=service)
        driver.set_page_load_timeout(45)
        try:
            addon_id = driver.install_web_extension(str(xpi), permanent=False).id
            if not addon_id:
                raise RegistrationBlocked("Firefox failed to install official RoboForm add-on.")
            open_roboform_start_page(driver, addon_id)
            body = body_text(driver)
            if "Privacy" in body and "your consent is required" in body:
                # The manually dispatched workflow preselects privacy_consent.
                # Respect the submitted value; a false value stops before launch.
                if not click_exact_control(driver, "Accept"):
                    raise RegistrationBlocked("RoboForm Privacy agreement needs manual acceptance; Accept control was not found.")
                print("FIREFOX_PRIVACY_ACCEPTED: workflow privacy_consent input was true.")
                time.sleep(2)
            enter_signup_form(driver)
            text_fields = visible_controls(driver, "input[type=text], input[type=email]")
            pass_fields = visible_controls(driver, "input[type=password]")
            if len(text_fields) != 2 or len(pass_fields) != 2:
                raise RegistrationBlocked("Unexpected Firefox signup form fields; inspect extension version, no submission attempted.")
            text_fields[0].send_keys(email)
            pass_fields[0].send_keys(password)
            pass_fields[1].send_keys(password)
            text_fields[1].send_keys(full_name)
            text_fields[1].send_keys(Keys.TAB)
            time.sleep(2)
            if interactive:
                print(
                    "FIREFOX_MANUAL_VERIFICATION_READY: Firefox is open with the signup form. "
                    "Use that Firefox window to click Create Account and complete any verification "
                    "yourself. Do not close the browser."
                )
                input("After RoboForm shows the account-created success screen, press Enter here to verify: ")
                print("FIREFOX_MANUAL_VERIFICATION_CHECK: checking RoboForm success screen.")
                await_confirmation(driver, email)
                print("FIREFOX_SIGNUP_CONFIRMED: RoboForm success screen verified and registration recorded.")
                return
            submit = find_submit_button(driver)
            if submit is None:
                raise RegistrationBlocked("Firefox signup Create Account button is missing; no submission attempted.")
            if not submit.is_enabled():
                if verification_present(driver):
                    raise RegistrationBlocked(
                        "RoboForm verification is pending before Create Account can be enabled; no account was recorded."
                    )
                raise RegistrationBlocked(
                    "Create Account stays disabled. Check RoboForm Firefox password rules and form validation; no account recorded."
                )
            submit.click()
            print("FIREFOX_SIGNUP_SUBMITTED: awaiting official confirmation; success not assumed.")
            await_confirmation(driver, email)
            print("FIREFOX_SIGNUP_CONFIRMED: RoboForm success screen verified and registration recorded.")
        finally:
            driver.quit()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="RoboForm Firefox registration.")
    parser.add_argument(
        "--interactive", action="store_true",
        help="Open visible local Firefox for a human to complete verification and submit the signup."
    )
    arguments = parser.parse_args()
    try:
        run(interactive=arguments.interactive)
    except (EOFError, KeyboardInterrupt):
        print("REGISTRATION_NOT_CONFIRMED_FIREFOX: local interactive session cancelled.")
        raise SystemExit(1) from None
    except RegistrationBlocked as error:
        print("REGISTRATION_NOT_CONFIRMED_FIREFOX:", str(error))
        raise SystemExit(1) from None
    except Exception as error:
        # Never display raw Selenium/HTTP exceptions that might expose
        # form contents, URLs, tokens, or credential fields.
        print("REGISTRATION_NOT_CONFIRMED_FIREFOX: unexpected", type(error).__name__,
              "(redacted; no verified receipt)")
        raise SystemExit(1) from None
