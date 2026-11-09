"""Optional read-only ddddocr diagnostic for an isolated verification PNG.

No network inference, no form interaction, no challenge submission. The
reported text is an unverified suggestion for a human reviewing the image.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import re
import struct

PNG_MAGIC = bytes((137, 80, 78, 71, 13, 10, 26, 10))


def validate_image(path: Path) -> bytes:
    raw = path.read_bytes()
    if not 100 <= len(raw) <= 512_000 or raw[:8] != PNG_MAGIC:
        raise ValueError("Not a bounded PNG screenshot")
    if len(raw) < 24 or raw[12:16] != b"IHDR":
        raise ValueError("Invalid PNG header")
    width, height = struct.unpack(">II", raw[16:24])
    if not (30 <= width <= 640 and 18 <= height <= 240):
        raise ValueError("Unexpected verification image dimensions")
    return raw


def accepted_hint(candidate: object) -> str | None:
    """Never expose arbitrary OCR output; only a short alphanumeric hint."""
    if not isinstance(candidate, str):
        return None
    if not re.fullmatch(r"[A-Za-z0-9]{1,12}", candidate):
        return None
    return candidate


def recognize(image: Path) -> str | None:
    import ddddocr  # Lazy import: the optional model is not a base dependency.

    raw = validate_image(image)
    engine = ddddocr.DdddOcr(show_ad=False)
    # The model runs locally; the return value is never entered into RoboForm.
    return accepted_hint(engine.classification(raw))


def main() -> None:
    parser = argparse.ArgumentParser(description="Read-only ddddocr hint for human review.")
    parser.add_argument("image", type=Path)
    args = parser.parse_args()
    try:
        hint = recognize(args.image)
    except Exception:
        # Fail independently of Tesseract; do not expose model internals or input.
        print("FIREFOX_DDDDOCR_STATUS: unavailable")
        print("FIREFOX_DDDDOCR_RECOGNIZED_TEXT: [unavailable] (unverified)")
        return

    print("FIREFOX_DDDDOCR_STATUS: " + ("unverified-suggestion" if hint else "no-safe-text"))
    print("FIREFOX_DDDDOCR_RECOGNIZED_TEXT: " + (hint or "[no safe text detected]") + " (unverified)")
    print("FIREFOX_DDDDOCR_CONFIDENCE: N/A (not provided by classification API)")


if __name__ == "__main__":
    main()
