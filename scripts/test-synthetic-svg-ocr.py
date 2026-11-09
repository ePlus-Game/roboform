"""Smoke test: Tesseract OCR on a locally generated, non-security SVG.

This is an isolated example for generic SVG text recognition. It intentionally
does not load images from RoboForm, HAR captures, CAPTCHA challenges, or signup.
"""
from __future__ import annotations

from pathlib import Path
import re
import subprocess
import tempfile

import cairosvg

EXPECTED = "HELLO 2026"
SAMPLE_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="720" height="160">
<rect width="720" height="160" fill="white"/>
<text x="28" y="111" font-family="DejaVu Sans" font-size="78"
      fill="black">HELLO 2026</text>
</svg>"""


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="tesseract-synthetic-ocr-") as tmp:
        image = Path(tmp) / "plain-text.png"
        cairosvg.svg2png(bytestring=SAMPLE_SVG.encode("utf-8"), write_to=str(image))
        result = subprocess.run(
            ["tesseract", str(image), "stdout", "-l", "eng", "--psm", "7"],
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        )
        observed = re.sub(r"\\s+", " ", result.stdout).strip().upper()
        print("OCR_SAMPLE: synthetic, non-CAPTCHA SVG (text element)")
        print("OCR_EXPECTED:", EXPECTED)
        print("OCR_OBSERVED:", observed)
        if observed != EXPECTED:
            raise SystemExit("Tesseract baseline recognition mismatch")
        print("OCR_BASELINE_PASS")


if __name__ == "__main__":
    main()
