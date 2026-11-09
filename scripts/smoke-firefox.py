"""Anonymous Firefox RoboForm smoke test. Never submit or accept Privacy terms."""
import json
import os
from pathlib import Path
import tempfile
import time
from selenium import webdriver
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.common.by import By
from firefox_support import download_signed_addon, open_roboform_start_page

def main() -> None:
    with tempfile.TemporaryDirectory(prefix="rf-firefox-") as tmp:
        xpi = Path(tmp) / "roboform-firefox.xpi"
        _, files = download_signed_addon(xpi)
        options = webdriver.FirefoxOptions()
        options.add_argument("-headless")
        if binary := os.getenv("FIREFOX_BINARY"):
            options.binary_location = binary
        # No RoboForm credentials or private user data are passed into Firefox.
        # GeckoDriver 0.37+ requires this for Firefox extension UI testing.
        # Safe only in this isolated CI job: no account secrets are provided.
        service = Service(service_args=["--allow-system-access"])
        driver = webdriver.Firefox(options=options, service=service)
        driver.set_page_load_timeout(45)
        try:
            addon_id = driver.install_web_extension(str(xpi), permanent=False).id
            if not addon_id:
                raise RuntimeError("Firefox did not report a loaded RoboForm extension")
            print("FIREFOX_ADDON_INSTALLED: Selenium loaded official RoboForm XPI")
            if "start-page.html" not in files:
                print("FIREFOX_LIMITATION: XPI has no start-page.html, so Chromium navigation cannot be reused")
                return
            open_roboform_start_page(driver, addon_id)
            body = driver.find_element(By.TAG_NAME, "body").text
            if "Sign Up" not in body and "Create Account" not in body:
                # Firefox extension initialization differs from Chromium.
                # Keep diagnostics limited to text labels in this fresh blank profile.
                time.sleep(6)
                body = driver.find_element(By.TAG_NAME, "body").text
            if "Sign Up" in body or "Create Account" in body:
                print("FIREFOX_SIGNUP_UI_READY: official extension signup entrypoint is available")
            elif "Privacy" in body and "your consent is required" in body:
                labels = []
                for control in driver.find_elements(By.CSS_SELECTOR, "button, input[type=button], input[type=submit], a, [role=button]"):
                    if control.is_displayed():
                        label = (control.get_attribute("aria-label") or control.get_attribute("value") or control.text or "").strip()[:60]
                        if label:
                            labels.append(label)
                print("FIREFOX_PRIVACY_CONTROLS:", json.dumps(labels[:15]))
                print("FIREFOX_PRIVACY_CONSENT_REQUIRED: RoboForm Firefox onboarding requires user acceptance before signup. The smoke test does not accept privacy terms on the user's behalf.")
            else:
                print("FIREFOX_LIMITATION: extension startup UI not recognized; check onboarding in an interactive Firefox session")
            print("NO_REGISTRATION_ATTEMPTED: no real data submitted, no privacy consent given, no CAPTCHA bypass")
        finally:
            driver.quit()


if __name__ == "__main__":
    main()
