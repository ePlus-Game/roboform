"""Reproducible, OFFLINE OCR engine comparison on synthetic, labeled text.

Never consumes real CAPTCHA captures, SVG path fixtures, RoboForm browser state,
credentials, or user data. Never submits recognized text anywhere.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from importlib.metadata import version, PackageNotFoundError
import json
import os
from pathlib import Path
import re
import subprocess
import time

FONT_SANS = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONT_SERIF = "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf"
LABELS = ("HELLO", "WORLD", "PYTHON", "CLOUD7", "TECH42", "RADIO9")
STYLES = ("plain", "low_contrast")
OUTPUT = Path("dist/ocr-engine-benchmark")


def normalize(value: object) -> str:
    return re.sub(r"[^A-Z0-9]", "", str(value or "").upper())


def edit_distance(a: str, b: str) -> int:
    """Levenshtein distance for per-image character error rate."""
    previous = list(range(len(b) + 1))
    for i, char_a in enumerate(a, 1):
        current = [i]
        for j, char_b in enumerate(b, 1):
            current.append(min(
                current[j - 1] + 1,
                previous[j] + 1,
                previous[j - 1] + (char_a != char_b),
            ))
        previous = current
    return previous[-1]


def samples(directory: Path):
    from PIL import Image, ImageDraw, ImageFont
    directory.mkdir(parents=True, exist_ok=True)
    output = []
    for style in STYLES:
        for index, label in enumerate(LABELS):
            canvas = Image.new("RGB", (240, 74), "white")
            draw = ImageDraw.Draw(canvas)
            font = ImageFont.truetype(
                FONT_SANS if index % 2 == 0 else FONT_SERIF, 36
            )
            tone = (20, 25, 30) if style == "plain" else (108, 108, 108)
            # Deterministic, ordinary text images: not simulated real CAPTCHAs.
            draw.text((14, 13), label, font=font, fill=tone)
            path = directory / (style + "-" + label.lower() + ".png")
            canvas.save(path)
            output.append({"file": str(path), "label": label, "style": style})
    return output


def make_engines():
    import ddddocr
    from rapidocr import RapidOCR

    dddd = ddddocr.DdddOcr(show_ad=False)
    rapid = RapidOCR()

    def tesseract(path):
        result = subprocess.run(
            ["tesseract", str(path), "stdout", "-l", "eng", "--psm", "7"],
            check=True, timeout=25, capture_output=True, text=True
        )
        return result.stdout.strip()

    def ddddocr_run(path):
        return dddd.classification(Path(path).read_bytes())

    def rapidocr_run(path):
        result = rapid(str(path))
        return "".join(result.txts or ()) if result is not None else ""

    return {
        "Tesseract": tesseract,
        "ddddocr": ddddocr_run,
        "RapidOCR": rapidocr_run,
    }


def benchmark(engine, examples):
    rows = []
    for sample in examples:
        start = time.perf_counter()
        result = engine(sample["file"])
        elapsed_ms = (time.perf_counter() - start) * 1000
        observed = normalize(result)
        label = sample["label"]
        rows.append({
            "sample": Path(sample["file"]).name,
            "style": sample["style"],
            "expected": label,
            "observed": observed,
            "correct": observed == label,
            "edit_distance": edit_distance(label, observed),
            "duration_ms": round(elapsed_ms, 2),
        })
    return rows


def aggregate(rows):
    count = len(rows)
    return {
        "samples": count,
        "exact_matches": sum(r["correct"] for r in rows),
        "exact_match_rate": round(sum(r["correct"] for r in rows) / count, 4),
        "character_error_rate": round(
            sum(r["edit_distance"] for r in rows)
            / sum(len(r["expected"]) for r in rows), 4
        ),
        "mean_inference_ms": round(sum(r["duration_ms"] for r in rows) / count, 2),
    }


def package_version(name):
    try:
        return version(name)
    except PackageNotFoundError:
        return "unknown"


def main():
    parser = argparse.ArgumentParser(description="Offline synthetic text OCR comparison")
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    output = args.output
    cases = samples(output / "samples")
    setup_start = time.perf_counter()
    engines = make_engines()
    init_ms = round((time.perf_counter() - setup_start) * 1000, 2)
    report = {
        "disclaimer": (
            "Synthetic labeled text only. Not a RoboForm CAPTCHA accuracy estimate. "
            "No actual CAPTCHA is decoded or submitted."
        ),
        "case_count": len(cases),
        "labels": list(LABELS),
        "styles": list(STYLES),
        "initialization_ms_combined": init_ms,
        "versions": {
            "pillow": package_version("Pillow"),
            "ddddocr": package_version("ddddocr"),
            "rapidocr": package_version("rapidocr"),
            "onnxruntime": package_version("onnxruntime"),
        },
        "engines": {},
    }
    summary_lines = [
        "### Offline synthetic text OCR benchmark",
        "",
        "Synthetic, labeled images only; NOT measured against RoboForm's CAPTCHA.",
        "All models run locally in the same GitHub Actions job (CPU).",
        "Model initialization is excluded from per-image inference time.",
        "",
        "| Engine | Exact | Character error | Mean ms/image |",
        "|---|---:|---:|---:|",
    ]
    for name, engine in engines.items():
        rows = benchmark(engine, cases)
        result = aggregate(rows)
        report["engines"][name] = {"summary": result, "cases": rows}
        summary_lines.append(
            f"| {name} | {result['exact_matches']}/{result['samples']} "
            f"({100 * result['exact_match_rate']:.1f}%) | "
            f"{100 * result['character_error_rate']:.1f}% | "
            f"{result['mean_inference_ms']:.1f} |"
        )
        print(
            "OCR_BENCH_RESULT: "
            f"engine={name} exact={result['exact_matches']}/{len(rows)} "
            f"cer={result['character_error_rate']} "
            f"mean_ms={result['mean_inference_ms']}"
        )

    summary_lines.extend([
        "",
        "Disclaimer: simple rendered text is much easier than real verification images.",
        "This result does not justify automatic CAPTCHA solving or changing the registration workflow.",
        "",
        "View detailed predictions in the attached JSON report.",
    ])
    output.mkdir(parents=True, exist_ok=True)
    report_path = output / "report.json"
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    if destination := os.environ.get("GITHUB_STEP_SUMMARY"):
        with Path(destination).open("a", encoding="utf-8") as file:
            file.write("\n".join(summary_lines) + "\n")
    print("OCR_BENCH_REPORT:", report_path)
    print("OCR_BENCH_INIT_MS_COMBINED:", init_ms)


if __name__ == "__main__":
    main()
