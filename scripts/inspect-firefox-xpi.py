"""Static audit of the official RoboForm Firefox XPI. No account, secrets or network submission.

The XPI is downloaded by the same Mozilla Add-ons helper as the smoke test.
Only a few short, bounded code excerpts and file/selector metadata are logged.
Nothing from the package is redistributed or committed.
"""
from __future__ import annotations

from collections import defaultdict
import json
from pathlib import Path
import re
import tempfile
from zipfile import ZipFile

from firefox_support import download_signed_addon

PATTERNS = {
    "account-created-response": r"accountCreated",
    "unlocked-response": r"(?<![A-Za-z])unlocked",
    "success-text": r"Account created successfully",
    "success-container": r"account-confirmation",
    "success-message": r"done-message",
    "success-email": r"credentials-section",
    "signup-form": r"create-new-account",
    "create-button": r"Create Account",
    "signup-screen": r"Sign Up",
    "privacy-screen": r"your consent is required",
    "verification-image": r"verify-human-code-image",
    "turnstile": r"turnstile",
    "captcha": r"captcha",
    "account-auth-endpoint": r"/account/auth",
}
SAFE_PATH = re.compile(r"^[A-Za-z0-9_./!()@+ -]{1,180}$")
EXTS = (".js", ".html", ".htm", ".json", ".css")

def safe_context(text: str, pos: int) -> str:
    before = re.sub(r"\s+", " ", text[max(0, pos-75):pos]).strip()[-65:]
    after = re.sub(r"\s+", " ", text[pos:pos+125]).strip()[:110]
    return (before + " >>> " + after)[:185]

def main():
    with tempfile.TemporaryDirectory(prefix="roboform-xpi-audit-") as tmp:
        xpi = Path(tmp) / "roboform.xpi"
        version, _ = download_signed_addon(xpi)
        report = defaultdict(list)
        total_files = 0
        scanned_bytes = 0
        with ZipFile(xpi) as archive:
            names = archive.namelist()
            manifest = json.loads(archive.read("manifest.json"))
            print("XPI_MANIFEST", json.dumps({
                "version": version, "name": manifest.get("name"),
                "manifest_version": manifest.get("manifest_version"),
                "startup_page_exists": "start-page.html" in names,
                "background": bool(manifest.get("background")),
                "files_in_package": len(names),
            }))
            for info in archive.infolist():
                name = info.filename
                if not name.endswith(EXTS) or name.endswith(".map"):
                    continue
                if info.file_size > 10 * 1024 * 1024 or scanned_bytes + info.file_size > 85 * 1024 * 1024:
                    continue
                if not SAFE_PATH.fullmatch(name):
                    continue
                source = archive.read(info).decode("utf-8", "replace")
                total_files += 1
                scanned_bytes += info.file_size
                # Read-only, bounded component audit to identify nearby form-control
                # structure in the official extension. Do not print runtime form data.
                if name == "1.js":
                    for marker in ("verify-human-code-image", "question-text question-", "verify-human-code-refresh"):
                        positions = list(re.finditer(re.escape(marker), source))[:3]
                        for match in positions:
                            excerpt = re.sub(
                                r"\\s+", " ",
                                source[max(0, match.start() - 250):match.end() + 750]
                            )[:1050]
                            print("XPI_QUESTION_COMPONENT", json.dumps({
                                "marker": marker,
                                "excerpt": excerpt,
                            }, ensure_ascii=False))
                    # Identify element construction immediately before the code
                    # verification image. Emit only small input tag contexts.
                    image_markers = list(re.finditer("verify-human-code-image", source))
                    if len(image_markers) > 1:
                        pivot = image_markers[1].start()
                        nearby = source[max(0, pivot - 12000):pivot]
                        input_tags = list(re.finditer(r'(?:D|o)\\("input"', nearby))
                        for item in input_tags[-15:]:
                            left = max(0, item.start() - 110)
                            right = min(len(nearby), item.end() + 270)
                            print("XPI_INPUT_ELEMENT", json.dumps({
                                "excerpt": re.sub(r"\\s+", " ", nearby[left:right])[:380]
                            }, ensure_ascii=False))
                for key, regex in PATTERNS.items():
                    matches = list(re.finditer(regex, source, re.I))
                    if not matches:
                        continue
                    examples = [safe_context(source, m.start()) for m in matches[:2]]
                    report[key].append({"file": name, "occurrences": len(matches), "examples": examples})
        print("XPI_SCAN", json.dumps({"source_files": total_files, "scanned_bytes": scanned_bytes}))
        for key in PATTERNS:
            found = report.get(key, [])
            if not found:
                print("XPI_MATCH", json.dumps({"marker": key, "files": 0}))
                continue
            shown = sorted(found, key=lambda x: (-x["occurrences"], x["file"]))[:6]
            print("XPI_MATCH", json.dumps({
                "marker": key, "files": len(found),
                "total_occurrences": sum(x["occurrences"] for x in found),
                "matches": shown,
            }, ensure_ascii=False))
        print("XPI_AUDIT_COMPLETE: metadata only, no account request, no credentials.")


if __name__ == "__main__":
    main()
