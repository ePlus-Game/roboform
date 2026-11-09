"""Offline compatibility review of AmireNoori/SVG-Captcha-Solver.

Run the pinned upstream solver only on its own published examples. Inspect
the local SVG structurally without solving or submitting any CAPTCHA.
"""
from __future__ import annotations

import argparse
import base64
import importlib.util
import json
import os
from pathlib import Path
import re
import xml.etree.ElementTree as ET

MODEL_PATTERN = re.compile(r"[\d.\s]*")


def svg_structure(path: Path):
    raw = path.read_bytes()
    if not 0 < len(raw) <= 100_000:
        raise ValueError("SVG outside offline size limit")
    root = ET.fromstring(raw)
    if root.tag.rsplit("}", 1)[-1] != "svg":
        raise ValueError("Not an SVG document")
    paths = [el for el in root.iter() if el.tag.rsplit("}", 1)[-1] == "path"]
    eligible = [el for el in paths if not el.get("stroke")]
    signatures = [MODEL_PATTERN.sub("", el.get("d", "")) for el in eligible]
    return len(paths), len(eligible), signatures


def upstream_model(folder: Path):
    spec = importlib.util.spec_from_file_location(
        "pinned_upstream_solver", folder / "SVG_Captcha_Solver.py"
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("Pinned upstream source missing")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    solver = module.SvgCaptchaSolver()
    model = json.loads(base64.b64decode(solver.model, validate=True))
    if not isinstance(model, dict) or not model:
        raise ValueError("Upstream SVG pattern model unavailable")
    return solver, model


def main():
    parser = argparse.ArgumentParser(description="Offline SVG solver research")
    parser.add_argument("--upstream", required=True, type=Path)
    parser.add_argument(
        "--fixture", type=Path, default=Path("test/fixtures/user-provided-ocr.svg")
    )
    args = parser.parse_args()
    solver, model = upstream_model(args.upstream)
    print("SVG_SOLVER_MODE: offline, no registration or CAPTCHA submission")
    print("SVG_SOLVER_MODEL_SIGNATURE_COUNT:", len(model))

    results = []
    for filename in ("captcha1.svg", "captcha2.svg", "captcha3.svg"):
        sample = args.upstream / "examples" / filename
        count, eligible, _ = svg_structure(sample)
        try:
            result = solver.solve_captcha(str(sample))
            valid = isinstance(result, str) and bool(re.fullmatch(r"[A-Za-z0-9]{5}", result))
            status = "five-character-output" if valid else "unexpected-output"
        except (KeyError, IndexError, ValueError, TypeError, ET.ParseError, OSError) as exc:
            valid = False
            status = "exception-" + type(exc).__name__
        results.append(valid)
        print(
            f"SVG_SOLVER_EXAMPLE: {filename} paths={count} "
            f"eligible={eligible} status={status} (accuracy not established)"
        )

    count, eligible, signatures = svg_structure(args.fixture)
    matched = sum(signature in model for signature in signatures)
    print(
        f"SVG_SOLVER_LOCAL_STRUCTURE: paths={count} eligible={eligible} "
        f"matching_patterns={matched}/{len(signatures)}"
    )
    print("SVG_SOLVER_LOCAL_NOTE: structural check only; no code extraction")

    if summary := os.environ.get("GITHUB_STEP_SUMMARY"):
        with Path(summary).open("a", encoding="utf-8") as out:
            out.write(
                "\n### SVG-Captcha-Solver — isolated offline review\n"
                "- Upstream repo pinned to a commit, MIT license\n"
                "- Only published upstream example files were decoded\n"
                "- Upstream results: "
                + ", ".join("FORMAT PASS" if ok else "UNSUPPORTED" for ok in results)
                + "\n"
                f"- Local fixture path-signature matches: {matched}/{len(signatures)} "
                "(no solution generated)\n"
                "- A five-character output does not establish decoding accuracy.\n"
                "- No live browser, OCR-to-CAPTCHA, or form submission changes.\n"
            )
    if not any(results):
        raise SystemExit("Solver did not support any upstream example")


if __name__ == "__main__":
    main()
