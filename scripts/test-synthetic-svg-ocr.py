"""Offline Tesseract OCR comparison: generated text and one uploaded SVG.

No RoboForm interaction, account creation, HTTP requests, or CAPTCHA submission.
Recognized characters from the uploaded SVG are observational; there is no
claimed ground-truth label for that image.
"""
from __future__ import annotations

from io import BytesIO
from pathlib import Path
import re
import subprocess
import tempfile

import cairosvg
from PIL import Image

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
        observed = re.sub(r"\s+", " ", result.stdout).strip().upper()
        print("OCR_SAMPLE: synthetic, non-CAPTCHA SVG (text element)")
        print("OCR_EXPECTED:", EXPECTED)
        print("OCR_OBSERVED:", observed)
        if observed != EXPECTED:
            raise SystemExit("Tesseract baseline recognition mismatch")
        print("OCR_BASELINE_PASS")

        # Read ONLY the checked-in SVG asset supplied for standalone OCR testing.
        # Keep it entirely separate from browser signup and CAPTCHA challenges.
        fixture = Path(__file__).resolve().parents[1] / "test/fixtures/user-provided-ocr.svg"
        if not fixture.is_file():
            raise SystemExit("User-provided SVG fixture missing.")
        svg = fixture.read_bytes()
        if len(svg) > 100_000:
            raise SystemExit("User-provided SVG is unexpectedly large.")
        raster = Image.open(BytesIO(cairosvg.svg2png(bytestring=svg))).convert("RGBA")
        background = Image.new("RGBA", raster.size, "white")
        flattened = Image.alpha_composite(background, raster).convert("RGB")
        scaled = flattened.resize((flattened.width * 6, flattened.height * 6),
                                  Image.Resampling.LANCZOS)
        user_png = Path(tmp) / "uploaded-svg.png"
        scaled.save(user_png)
        user_result = subprocess.run(
            ["tesseract", str(user_png), "stdout", "-l", "eng", "--psm", "7"],
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        )
        observed_user = re.sub(r"\s+", " ", user_result.stdout).strip()
        print("OCR_USER_IMAGE_SOURCE: test/fixtures/user-provided-ocr.svg")
        print("OCR_USER_IMAGE_OUTPUT:", observed_user if observed_user else "[no text detected]")
        print("OCR_USER_IMAGE_NOTE: raw OCR output only; no known ground truth, no RoboForm submission")



if __name__ == "__main__":
    main()
