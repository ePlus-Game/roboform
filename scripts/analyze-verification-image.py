"""Read-only OCR diagnostic for an isolated Firefox verification image.

Display a strictly bounded alphanumeric OCR suggestion in CI for human review.
Never enter, submit or confirm a security challenge from OCR results.
"""
from __future__ import annotations

import argparse
import csv
import io
import os
import re
from pathlib import Path
import struct
import subprocess


PNG_MAGIC = bytes((137, 80, 78, 71, 13, 10, 26, 10))


def dimensions(path: Path) -> tuple[int, int]:
    with path.open("rb") as image:
        header = image.read(24)
    if len(header) < 24 or header[:8] != PNG_MAGIC or header[12:16] != b"IHDR":
        raise ValueError("verification artifact is not a valid PNG header")
    width, height = struct.unpack(">II", header[16:24])
    if not (30 <= width <= 640 and 18 <= height <= 240):
        raise ValueError("verification image dimensions exceed expected image-only bounds")
    return width, height


def confidence_metrics(tsv: str) -> tuple[int, float | None]:
    """Discard OCR tokens immediately; retain only aggregate quality metadata."""
    values: list[float] = []
    for row in csv.DictReader(io.StringIO(tsv), delimiter="\t"):
        if row.get("level") != "5" or not row.get("text", "").strip():
            continue
        try:
            confidence = float(row.get("conf", "-1"))
        except (ValueError, TypeError):
            continue
        if 0 <= confidence <= 100:
            values.append(confidence)
    return len(values), (sum(values) / len(values) if values else None)


def recognized_text(tsv: str) -> str | None:
    """Extract a bounded one-line code; never print arbitrary page or form data."""
    chunks = [
        row.get("text", "").strip()
        for row in csv.DictReader(io.StringIO(tsv), delimiter="\t")
        if row.get("level") == "5" and row.get("text", "").strip()
    ]
    candidate = "".join(chunks)
    # Unbounded/whitespace/punctuation OCR could contain sensitive unrelated text.
    if not re.fullmatch(r"[A-Za-z0-9]{1,12}", candidate):
        return None
    return candidate


def ocr_status(group_count: int, suggestion: str | None) -> str:
    """Distinguish missing OCR text from a suggestion rejected by the safety filter.

    Never output raw discarded OCR tokens (they may contain unrelated data).
    """
    if suggestion is not None:
        return "unverified-suggestion"
    if group_count > 0:
        return "filtered-ocr-output"
    return "no-text-groups"


def analyze(path: Path) -> tuple[int, int, int, float | None, str | None]:
    width, height = dimensions(path)
    result = subprocess.run(
        ["tesseract", str(path), "stdout", "--psm", "7", "tsv"],
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError("Tesseract OCR exited without usable diagnostic results")
    count, mean = confidence_metrics(result.stdout)
    return width, height, count, mean, recognized_text(result.stdout)


def main() -> None:
    parser = argparse.ArgumentParser(description="Read-only OCR text and confidence diagnostics.")
    parser.add_argument("image", type=Path)
    args = parser.parse_args()
    try:
        width, height, count, mean, recognized = analyze(args.image)
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as exc:
        print("FIREFOX_OCR_DIAGNOSTIC_FAILED:", type(exc).__name__)
        raise SystemExit(1) from None

    score = f"{mean:.1f}" if mean is not None else "N/A"
    print(f"FIREFOX_OCR_READONLY: image={width}x{height} recognized_groups={count} mean_confidence={score}")
    print(f"FIREFOX_OCR_RECOGNIZED_TEXT: {recognized or '[no safe text detected]'} (unverified)")
    status = ocr_status(count, recognized)
    print(f"FIREFOX_OCR_STATUS: {status}")
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with Path(summary).open("a", encoding="utf-8") as out:
            out.write(
                "\n### Firefox image-code OCR (read-only)\n"
                f"- Image dimensions: {width} x {height}\n"
                f"- OCR groups: {count}\n"
                f"- Mean Tesseract confidence: {score}\n"
                f"- OCR recognized text (unverified): `{recognized or '[no safe text detected]'}`\n"
                f"- OCR status: `{status}` (a filtered result is not an OCR engine failure)\n"
                "- OCR output is displayed for review only, not submitted for verification.\n"
                "- Registration remains unconfirmed until RoboForm reports success.\n"
            )


if __name__ == "__main__":
    main()
