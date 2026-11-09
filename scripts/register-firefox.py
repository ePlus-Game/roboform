"""Try RoboForm registration through the official Firefox add-on.

Requires Firefox privacy_consent to remain checked in workflow_dispatch.
Never attempts to solve or bypass CAPTCHA / Turnstile. Never logs credentials.
Records only an exact email match on RoboForm's visible success screen.
"""
from __future__ import annotations

import csv
import getpass
import os
from pathlib import Path
import re
import subprocess
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


def interactive_mode() -> bool:
    """Only explicitly opted-in local runs launch a visible Firefox window."""
    return os.getenv("FIREFOX_INTERACTIVE", "").strip().lower() in {"1", "true", "yes"}


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


def human_verification_present(driver) -> bool:
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

    The Firefox add-on may display a challenge in a different tab/window.
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


def sanitized_post_submit_state(state: dict) -> dict:
    return {key: value for key, value in state.items() if key != "confirmed_email"}


def await_confirmation(driver, email: str, interactive: bool = False) -> None:
    started = time.monotonic()
    deadline = 600 if interactive else 90
    alerted_challenge = False
    alerted_error = False
    state = None
    while time.monotonic() - started < deadline:
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
        if interactive:
            if state["windows"] == 0:
                raise RegistrationBlocked("Firefox was closed before signup could be confirmed. No record written.")
            if state["challenge"] != "none" and not alerted_challenge:
                print("FIREFOX_MANUAL_VERIFICATION: Please complete the human verification in the visible Firefox window. Selenium will only observe the official success screen.")
                alerted_challenge = True
            if state["visible_errors"] > 0 and not alerted_error:
                print("FIREFOX_MANUAL_REVIEW: RoboForm shows an error. Review it directly in Firefox; sensitive message content is not logged.")
                alerted_error = True
        else:
            if elapsed >= 5 and state["challenge"] != "none":
                print("FIREFOX_POST_SUBMIT_STATE:", sanitized_post_submit_state(state))
                raise RegistrationBlocked(
                    "RoboForm displayed " + state["challenge"] +
                    " human verification after Create Account. A person must complete "
                    "this challenge in the official interactive browser; no record was written."
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
        f"within {deadline} seconds. No account was recorded."
    )


def wait_for_manual_pre_submit_verification(driver, timeout: int = 600) -> None:
    """Allow a person to finish an already-displayed challenge without automation."""
    print("FIREFOX_MANUAL_VERIFICATION: Complete RoboForm's verification in Firefox; do not click Create Account yourself. Selenium will click it when enabled.")
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        submit = find_submit_button(driver)
        if submit is not None and submit.is_enabled():
            return
        if not driver.window_handles:
            raise RegistrationBlocked("Firefox was closed before human verification finished.")
        time.sleep(1)
    raise RegistrationBlocked("Manual verification did not enable Create Account within 10 minutes. No signup submitted.")


def run() -> None:
    interactive = interactive_mode()
    if os.getenv("FIREFOX_PRIVACY_CONSENT", "").lower() != "true":
        raise RegistrationBlocked(
            "Firefox Privacy consent is required. Review the agreement; keep the privacy_consent option checked if you agree."
        )
    email = normalize_email(os.getenv("REGISTRATION_EMAIL", ""))
    full_name = os.getenv("REGISTRATION_FULL_NAME", "David Nguyen").strip()
    password = os.getenv("ROBOFORM_MASTER_PASSWORD", "")
    if interactive and not password and os.isatty(0):
        # Avoid saving the Master Password in shell history or the environment.
        password = getpass.getpass("RoboForm Master Password (input hidden): ")
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
        else:
            print("FIREFOX_INTERACTIVE: Visible Firefox session started; use this machine's browser for any human security verification.")
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
            submit = find_submit_button(driver)
            if submit is None:
                raise RegistrationBlocked("Firefox signup Create Account button is missing; no submission attempted.")
            if not submit.is_enabled():
                if interactive:
                    wait_for_manual_pre_submit_verification(driver)
                    submit = find_submit_button(driver)
                    if submit is None or not submit.is_enabled():
                        raise RegistrationBlocked("Create Account did not become enabled after human verification.")
                elif human_verification_present(driver):
                    raise RegistrationBlocked(
                        "RoboForm requires human CAPTCHA/Turnstile verification before enabling Create Account. "
                        "Unattended GitHub Actions cannot complete this; no account was recorded."
                    )
                else:
                    raise RegistrationBlocked(
                        "Create Account stays disabled. Check RoboForm Firefox password rules and form validation; no account recorded."
                    )
            submit.click()
            print("FIREFOX_SIGNUP_SUBMITTED: awaiting official confirmation; success not assumed.")
            await_confirmation(driver, email, interactive=interactive)
            print("FIREFOX_SIGNUP_CONFIRMED: RoboForm success screen verified and registration recorded.")
        finally:
            driver.quit()


if __name__ == "__main__":
    try:
        run()
    except RegistrationBlocked as error:
        print("REGISTRATION_NOT_CONFIRMED_FIREFOX:", str(error))
        raise SystemExit(1) from None
    except Exception as error:
        # Never display raw Selenium/HTTP exceptions that might expose
        # form contents, URLs, tokens, or credential fields.
        print("REGISTRATION_NOT_CONFIRMED_FIREFOX: unexpected", type(error).__name__,
              "(redacted; no verified receipt)")
        raise SystemExit(1) from None
