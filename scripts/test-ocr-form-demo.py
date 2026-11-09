"""End-to-end OCR-to-form demonstration on a local HTML page only.

CI creates the sample SVG and form. It never contacts RoboForm or submits a
CAPTCHA on any real website. All data remains inside a temporary directory.
"""
from __future__ import annotations

import base64
from io import BytesIO
from pathlib import Path
import re
import subprocess
import tempfile

import cairosvg
from PIL import Image
from selenium import webdriver
from selenium.webdriver.common.by import By

EXPECTED = "HELLO2026"
SVG_SAMPLE = """<svg xmlns="http://www.w3.org/2000/svg" width="720" height="160">
<rect width="720" height="160" fill="white"/>
<text x="28" y="111" font-family="DejaVu Sans" font-size="78"
      fill="black">HELLO2026</text>
</svg>"""


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="ocr-form-demo-") as tmp:
        root = Path(tmp)
        embedded = base64.b64encode(SVG_SAMPLE.encode("utf-8")).decode("ascii")
        page = root / "index.html"
        page.write_text(
            "<!doctype html><html><body>"
            f'<img id="sample" src="data:image/svg+xml;base64,{embedded}" alt="OCR text sample">'
            '<input id="answer" type="text" autocomplete="off">'
            '<button id="submit" type="button" onclick="'
            "document.getElementById('result').textContent = "
            "document.getElementById('answer').value === 'HELLO2026' ? 'PASS' : 'FAIL'"
            '">Submit</button>'
            '<output id="result"></output></body></html>',
            encoding="utf-8",
        )

        options = webdriver.FirefoxOptions()
        options.add_argument("-headless")
        driver = webdriver.Firefox(options=options)
        try:
            driver.get(page.resolve().as_uri())
            source = driver.find_element(By.ID, "sample").get_attribute("src")
            if not source.startswith("data:image/svg+xml;base64,"):
                raise RuntimeError("Unexpected image source in local demo form")
            svg_bytes = base64.b64decode(source.split(",", 1)[1], validate=True)
            if len(svg_bytes) > 32_768:
                raise RuntimeError("Local SVG test fixture exceeded size limit")

            png = cairosvg.svg2png(bytestring=svg_bytes)
            image = Image.open(BytesIO(png)).convert("RGB")
            rendered = root / "sample.png"
            image.resize((image.width * 3, image.height * 3), Image.Resampling.LANCZOS).save(rendered)
            completed = subprocess.run(
                ["tesseract", str(rendered), "stdout", "-l", "eng", "--psm", "7"],
                check=True,
                capture_output=True,
                text=True,
                timeout=30,
            )
            recognized = re.sub(r"\s+", "", completed.stdout).strip()
            print("OCR_FORM_RECOGNIZED:", recognized)
            driver.find_element(By.ID, "answer").send_keys(recognized)
            driver.find_element(By.ID, "submit").click()
            form_result = driver.find_element(By.ID, "result").text
            print("OCR_FORM_RESULT:", form_result)
            if recognized != EXPECTED or form_result != "PASS":
                raise SystemExit("OCR form demonstration failed")
            print("OCR_FORM_E2E_PASS")
        finally:
            driver.quit()


if __name__ == "__main__":
    main()
