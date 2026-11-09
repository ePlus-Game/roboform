"""Safe Firefox/RoboForm extension smoke test.

No real signup, passwords, account tokens, screenshots, HAR or CAPTCHA solving.
The only downloaded add-on comes from Mozilla Add-ons' own API.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
import time
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from zipfile import ZipFile

from selenium import webdriver
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait

AMO_API = "https://addons.mozilla.org/api/v5/addons/addon/roboform/"
ALLOWED_DOWNLOAD_HOSTS = {"addons.mozilla.org", "addons.cdn.mozilla.net"}
MAX_XPI_BYTES = 25 * 1024 * 1024
MOZ_URL = re.compile(r"moz-extension://([a-f0-9-]{30,50})/", re.I)


def fetch(url: str) -> bytes:
    req = Request(url, headers={"User-Agent": "ePlus-roboform-firefox-smoke/1.0", "Accept": "*/*"})
    with urlopen(req, timeout=60) as response:
        if response.geturl() != AMO_API:
            host = urlparse(response.geturl()).hostname
            if host not in ALLOWED_DOWNLOAD_HOSTS:
                raise RuntimeError("Add-on download redirected outside official Mozilla hosts")
        data = response.read(MAX_XPI_BYTES + 1)
    if len(data) > MAX_XPI_BYTES:
        raise RuntimeError("Official Mozilla add-on exceeds the size limit")
    return data


def download_signed_addon(path: Path) -> tuple[str, set[str]]:
    info = json.loads(fetch(AMO_API))
    if info.get("slug") != "roboform":
        raise RuntimeError("Mozilla returned a different extension")
    version = info.get("current_version") or {}
    file = version.get("file") or {}
    url = file.get("url", "")
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname not in ALLOWED_DOWNLOAD_HOSTS:
        raise RuntimeError("Mozilla add-on download host not recognized")
    if not parsed.path.endswith(".xpi"):
        raise RuntimeError("Mozilla did not supply a signed XPI download")
    data = fetch(url)
    digest = file.get("hash", "")
    if digest and digest.startswith("sha256:"):
        if hashlib.sha256(data).hexdigest() != digest.split(":", 1)[1]:
            raise RuntimeError("Downloaded Firefox add-on SHA-256 mismatch")
    path.write_bytes(data)
    with ZipFile(path) as archive:
        names = set(archive.namelist())
        manifest = json.loads(archive.read("manifest.json"))
    if not manifest.get("name") or not manifest.get("version"):
        raise RuntimeError("Downloaded XPI does not contain a valid extension manifest")
    print("FIREFOX_ADDON_DOWNLOADED: official RoboForm signed XPI version", manifest["version"])
    return manifest["version"], names


def discover_uuid(driver, addon_id: str) -> str | None:
    # Firefox WebDriver forbids navigation to about:debugging. Inspect only
    # the isolated ephemeral browser profile for its public extension UUID.
    # Never read or log cookies, storage files or authentication values.
    profile = driver.capabilities.get("moz:profile", "")
    if not profile:
        return None
    pref_path = Path(profile) / "prefs.js"
    for _ in range(8):
        time.sleep(1)
        if not pref_path.is_file():
            continue
        raw = pref_path.read_text(encoding="utf-8", errors="replace")
        match = re.search(r'user_pref\("extensions\.webextensions\.uuids", (".*?")\);', raw)
        if match:
            try:
                mapping = json.loads(json.loads(match.group(1)))
                if isinstance(mapping, dict) and addon_id in mapping:
                    return mapping[addon_id]
            except (ValueError, TypeError):
                pass
    print("FIREFOX_LIMITATION: Firefox WebDriver does not expose the runtime extension UUID")
    return None

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
            addon_id = driver.install_addon(str(xpi), temporary=True)
            if not addon_id:
                raise RuntimeError("Firefox did not report a loaded RoboForm extension")
            print("FIREFOX_ADDON_INSTALLED: Selenium loaded official RoboForm XPI")
            if "start-page.html" not in files:
                print("FIREFOX_LIMITATION: XPI has no start-page.html, so Chromium navigation cannot be reused")
                return
            uuid = discover_uuid(driver, addon_id)
            if not uuid:
                print("FIREFOX_LIMITATION: installed XPI but cannot resolve internal moz-extension origin")
                return
            target = f"moz-extension://{uuid}/start-page.html"
            # Firefox 153+ blocks direct WebDriver GET for privileged URLs.
            # Open the extension's own page via Firefox's browser UI context
            # with a system principal, then return to normal web context.
            existing = set(driver.window_handles)
            driver.set_context(driver.CONTEXT_CHROME)
            try:
                driver.execute_script("""
                    const win = Services.wm.getMostRecentWindow("navigator:browser");
                    if (!win || !win.gBrowser) throw new Error("Firefox browser window not found");
                    const tab = win.gBrowser.addTab(arguments[0], {
                        triggeringPrincipal: Services.scriptSecurityManager.getSystemPrincipal()
                    });
                    win.gBrowser.selectedTab = tab;
                """, target)
            finally:
                driver.set_context(driver.CONTEXT_CONTENT)
            WebDriverWait(driver, 15).until(
                lambda d: len(set(d.window_handles) - existing) > 0
            )
            new_handles = list(set(driver.window_handles) - existing)
            driver.switch_to.window(new_handles[0])
            body = WebDriverWait(driver, 20).until(
                lambda d: d.find_element(By.TAG_NAME, "body").text
            )
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
