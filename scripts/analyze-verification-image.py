"""Read-only OCR quality metrics for one captured verification image.

No recognized text is logged, stored, returned, or submitted to any service.
Runs after Firefox registration stops at an image-code challenge.
"""
from __future__ import annotations

import argparse
import csv
import io
import os
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


def analyze(path: Path) -> tuple[int, int, int, float | None]:
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
    return width, height, count, mean


def main() -> None:
    parser = argparse.ArgumentParser(description="Read-only OCR confidence diagnostics.")
    parser.add_argument("image", type=Path)
    args = parser.parse_args()
    try:
        width, height, count, mean = analyze(args.image)
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as exc:
        print("FIREFOX_OCR_DIAGNOSTIC_FAILED:", type(exc).__name__)
        raise SystemExit(1) from None

    score = f"{mean:.1f}" if mean is not None else "N/A"
    print(f"FIREFOX_OCR_READONLY: image={width}x{height} recognized_groups={count} mean_confidence={score}")
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with Path(summary).open("a", encoding="utf-8") as out:
            out.write(
                "\n### Firefox image-code OCR (read-only)\n"
                f"- Image dimensions: {width} x {height}\n"
                f"- OCR groups: {count}\n"
                f"- Mean Tesseract confidence: {score}\n"
                "- OCR text is not retained or used for verification.\n"
                "- Registration remains unconfirmed until RoboForm reports success.\n"
            )


if __name__ == "__main__":
    main()
