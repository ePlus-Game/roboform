"""Try RoboForm registration through the official Firefox add-on.

Requires explicit user privacy consent in workflow_dispatch.
Never attempts to solve or bypass CAPTCHA / Turnstile. Never logs credentials.
Records only an exact email match on RoboForm's visible success screen.
"""
from __future__ import annotations

import csv
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
    if not switch_to_signup(driver):
        raise RegistrationBlocked("Firefox extension did not show a Sign Up screen after Privacy acceptance.")
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


def await_confirmation(driver, email: str) -> None:
    try:
        confirmation = WebDriverWait(driver, 90).until(lambda d: next(
            (e for e in d.find_elements(By.CSS_SELECTOR, ".account-confirmation .credentials-section .email")
             if e.is_displayed()), None
        ))
    except Exception as error:
        if human_verification_present(driver):
            raise RegistrationBlocked("RoboForm requires a human security challenge after submission. No account was recorded.") from error
        raise RegistrationBlocked("RoboForm did not show its confirmed account creation screen. No record written.") from error
    returned = normalize_email(confirmation.text)
    if returned != email:
        raise RegistrationBlocked("Confirmed email does not match the requested account. No record written.")
    success = driver.find_elements(By.CSS_SELECTOR, ".account-confirmation .done-message .text")
    if not any(e.is_displayed() and "Account created successfully" in e.text for e in success):
        raise RegistrationBlocked("RoboForm confirmation did not include the expected success message.")
    # Only a confirmed browser response allows a verified CSV record.
    env = dict(os.environ)
    env["CONFIRMED_EMAIL"] = returned
    subprocess.run(["node", "scripts/record-firefox.mjs"], check=True, env=env)


def run() -> None:
    if os.getenv("FIREFOX_PRIVACY_CONSENT", "").lower() != "true":
        raise RegistrationBlocked(
            "Firefox Privacy consent is required. Review RoboForm's agreement and explicitly check the workflow consent option."
        )
    email = normalize_email(os.getenv("REGISTRATION_EMAIL", ""))
    full_name = os.getenv("REGISTRATION_FULL_NAME", "David Nguyen").strip()
    password = os.getenv("ROBOFORM_MASTER_PASSWORD", "")
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
        opts.add_argument("-headless")
        if binary := os.getenv("FIREFOX_BINARY"):
            opts.binary_location = binary
        # System-access is limited to this fresh isolated runner and used solely
        # to open the real add-on start page. Never touch user browser profiles.
        service = Service(service_args=["--allow-system-access"])
        driver = webdriver.Firefox(options=opts, service=service)
        driver.set_page_load_timeout(45)
        try:
            addon_id = driver.install_addon(str(xpi), temporary=True)
            if not addon_id:
                raise RegistrationBlocked("Firefox failed to install official RoboForm add-on.")
            open_roboform_start_page(driver, addon_id)
            body = body_text(driver)
            if "Privacy" in body and "your consent is required" in body:
                # User supplied an explicit privacy-consent checkbox in the
                # manually dispatched workflow. Never accept it implicitly.
                if not click_exact_control(driver, "Accept"):
                    raise RegistrationBlocked("RoboForm Privacy agreement needs manual acceptance; Accept control was not found.")
                print("FIREFOX_PRIVACY_ACCEPTED: only because workflow caller explicitly consented.")
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
                if human_verification_present(driver):
                    raise RegistrationBlocked(
                        "RoboForm requires human CAPTCHA/Turnstile verification before enabling Create Account. "
                        "Unattended GitHub Actions cannot complete this; no account was recorded."
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
